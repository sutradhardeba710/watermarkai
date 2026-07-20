"use client";

import { useCallback, useRef, useState } from "react";

import { detectionApi } from "@/services/detection";
import { masksApi } from "@/services/masks";
import { pollJob } from "@/services/process";
import { ApiError } from "@/services/api";
import type { WatermarkCandidate } from "@/types";

export type DetectPhase = "idle" | "scanning" | "candidates" | "empty" | "error";

export interface DetectConfidence {
  label: "Strong match" | "Possible match" | "Low confidence";
  tone: "strong" | "possible" | "low";
}

export function confidenceOf(candidate: WatermarkCandidate): DetectConfidence {
  // Backend confidence is a 0..5 score (see candidates page). Map to plain terms.
  const pct = (candidate.confidence / 5) * 100;
  if (pct >= 70) return { label: "Strong match", tone: "strong" };
  if (pct >= 40) return { label: "Possible match", tone: "possible" };
  return { label: "Low confidence", tone: "low" };
}

/**
 * Inline AI detection. Mirrors the working /candidates flow (analyze → pollJob
 * → listCandidates → approve) but keeps the user inside the mask workspace.
 * Never starts paid processing; approval simply promotes a candidate to a
 * WatermarkMask, which the caller then loads via masksApi.get to paint it.
 */
export function useAiDetection(projectId: string) {
  const [phase, setPhase] = useState<DetectPhase>("idle");
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState("Queued");
  const [candidates, setCandidates] = useState<WatermarkCandidate[]>([]);
  const [notes, setNotes] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const run = useCallback(
    async (rerun = false) => {
      if (phase === "scanning") return;
      setPhase("scanning");
      setError(null);
      setCandidates([]);
      setProgress(0);
      setStage("Queued");
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const queued = await detectionApi.analyze(projectId, rerun);
        const finished = await pollJob(
          queued.job_id,
          (status) => {
            setProgress(status.progress);
            setStage((status.current_stage || status.status).replace(/_/g, " "));
          },
          { signal: controller.signal },
        );
        if (finished.status !== "completed") {
          throw new Error(finished.error_message || "AI detection did not complete.");
        }
        const list = await detectionApi.listCandidates(projectId);
        setCandidates(list.candidates);
        setNotes(list.notes ?? null);
        setProgress(100);
        if (list.candidates.length === 0) {
          setPhase("empty");
        } else {
          setPhase("candidates");
        }
      } catch (reason) {
        if ((reason as Error)?.name === "AbortError") return;
        const apiError = reason as ApiError;
        setError(apiError?.message || "We couldn't complete AI detection.");
        setPhase("error");
      }
    },
    [phase, projectId],
  );

  const approve = useCallback(
    async (candidate: WatermarkCandidate) => {
      setApprovingId(candidate.id);
      setError(null);
      try {
        await detectionApi.approve(candidate.id);
        const mask = await masksApi.get(projectId);
        setPhase("idle");
        setCandidates([]);
        return mask;
      } catch (reason) {
        const apiError = reason as ApiError;
        setError(apiError?.message || "Unable to apply this suggestion.");
        return null;
      } finally {
        setApprovingId(null);
      }
    },
    [projectId],
  );

  const reject = useCallback((candidateId: string) => {
    setCandidates((prev) => {
      const next = prev.filter((c) => c.id !== candidateId);
      if (next.length === 0) setPhase("empty");
      return next;
    });
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setPhase("idle");
  }, []);

  const dismiss = useCallback(() => {
    setPhase("idle");
    setError(null);
  }, []);

  return {
    phase,
    progress,
    stage,
    candidates,
    notes,
    error,
    approvingId,
    run,
    approve,
    reject,
    cancel,
    dismiss,
  };
}
