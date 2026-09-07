"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { AlertTriangle, Check, Image as ImageIcon, Sparkles, UploadCloud, Video, X } from "lucide-react";
import axios from "axios";

import { useHydrateAuth } from "@/features/auth/useHydrateAuth";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { uploadsApi, createCancelSource, setPendingUploadFile, type UploadProgress } from "@/services/uploads";
import { projectsApi } from "@/services/projects";

const MAX_MB = 500;
const MAX_DURATION_SECONDS = 300;
const IMAGE_EXT = ["png", "jpg", "jpeg", "webp"];
const VIDEO_EXT = ["mp4", "mov", "webm"];
const ALLOWED_EXT = [...IMAGE_EXT, ...VIDEO_EXT];
const POLICY_VERSION = "1.0";

const LEGAL =
  "I confirm that I own this photo or video, or I hold the rights to remove its watermark. I will not use this tool to remove attribution, copyright notices, or watermarks from content I do not have the right to alter.";

const PROHIBITED =
  "Prohibited: removing watermarks from content you do not own or lack the right to modify; stripping attribution from licensed media; circumventing copyright management information. Misuse may violate DMCA §1202 and similar laws.";

function bytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1048576) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1073741824) return `${(n / 1048576).toFixed(1)} MB`;
  return `${(n / 1073741824).toFixed(2)} GB`;
}

function ext(name: string) {
  return name.split(".").pop()?.toLowerCase() || "";
}

type Stage = "select" | "uploading" | "done" | "error";

export default function UploadPage() {
  useHydrateAuth();
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [ownership, setOwnership] = useState(false);
  const [stage, setStage] = useState<Stage>("select");
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [meta, setMeta] = useState<{ duration: number; width: number; height: number; type: string; isImage: boolean } | null>(null);
  const [projectId, setProjectId] = useState("");
  const cancelRef = useRef<ReturnType<typeof createCancelSource> | null>(null);

  async function pick(f: File | null) {
    if (!f) return;
    setError("");
    const e = ext(f.name);
    if (!ALLOWED_EXT.includes(e)) {
      setError(`Unsupported format .${e}. Use PNG, JPG, WebP, MP4, MOV, or WebM.`);
      return;
    }
    if (f.size > MAX_MB * 1048576) {
      setError(`This file is ${bytes(f.size)}. The maximum is ${MAX_MB} MB.`);
      return;
    }

    const isImg = IMAGE_EXT.includes(e);
    const url = URL.createObjectURL(f);

    if (isImg) {
      const img = new Image();
      img.onload = () => {
        URL.revokeObjectURL(url);
        setFile(f);
        setMeta({
          duration: 0,
          width: img.naturalWidth || img.width,
          height: img.naturalHeight || img.height,
          type: f.type || `${e.toUpperCase()} image`,
          isImage: true,
        });
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        setError("This image could not be read. Check the format and try another file.");
      };
      img.src = url;
    } else {
      const video = document.createElement("video");
      video.preload = "metadata";
      video.onloadedmetadata = () => {
        URL.revokeObjectURL(url);
        if (video.duration > MAX_DURATION_SECONDS) {
          setFile(null);
          setMeta(null);
          setError(`This video is ${Math.round(video.duration)} seconds. The maximum is ${MAX_DURATION_SECONDS} seconds.`);
          return;
        }
        setFile(f);
        setMeta({
          duration: video.duration,
          width: video.videoWidth,
          height: video.videoHeight,
          type: f.type || `${e} video`,
          isImage: false,
        });
      };
      video.onerror = () => {
        URL.revokeObjectURL(url);
        setError("This video could not be read. Check the codec and try another file.");
      };
      video.src = url;
    }
  }

  function drop(e: React.DragEvent) {
    e.preventDefault();
    setDrag(false);
    void pick(e.dataTransfer.files?.[0] || null);
  }

  async function start() {
    if (!file || !ownership) return;
    setError("");
    setStage("uploading");
    setProgress({ loaded: 0, total: file.size, percent: 0, bytesPerSecond: 0 });
    const c = createCancelSource();
    cancelRef.current = c;
    try {
      const init = await uploadsApi.initiate({
        filename: file.name,
        total_bytes: file.size,
        content_type: file.type || undefined,
      });
      const done = await uploadsApi.complete(init.upload_id, file, {
        cancelToken: c.token,
        onProgress: setProgress,
      });
      await projectsApi.confirmCompliance(done.project_id, {
        ownership_confirmed: true,
        policy_version: POLICY_VERSION,
      });
      setProjectId(done.project_id);
      setPendingUploadFile(file);
      setStage("done");
      router.push(`/projects/${done.project_id}`);
    } catch (e) {
      if (axios.isCancel(e)) {
        setError("Upload cancelled.");
        setStage("select");
      } else {
        const err = e as { message?: string };
        setError(err?.message || "Upload failed. Please check the file and try again.");
        setStage("error");
      }
    } finally {
      cancelRef.current = null;
    }
  }

  const valid = !!file && !!meta && ownership && stage === "select";

  return (
    <WorkspaceShell
      title="Upload Media"
      eyebrow="New cleanup project"
      actions={
        <Link
          href="/dashboard"
          className="hidden min-h-11 items-center px-2 text-sm text-white/60 hover:text-white sm:inline-flex"
        >
          Back to projects
        </Link>
      }
    >
      <div className="relative mx-auto max-w-4xl px-5 py-8 sm:px-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">Upload Photo or Video</h1>
            <p className="mt-1 text-sm text-white/50">
              Prepare photos or video clips for AI watermark, logo, text, and stamp removal.
            </p>
          </div>
          <div className="hidden items-center gap-2 rounded-xl border border-white/10 bg-white/[.04] p-1.5 sm:flex">
            <span className="flex items-center gap-1.5 rounded-lg bg-white/10 px-2.5 py-1 text-xs font-medium text-white">
              <ImageIcon className="h-3.5 w-3.5 text-cyan-300" /> Photos & Images
            </span>
            <span className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium text-white/60">
              <Video className="h-3.5 w-3.5 text-violet-300" /> Videos
            </span>
          </div>
        </div>

        <div className="mt-6 flex items-start gap-3 rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4 text-sm text-amber-200">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
          <p>{PROHIBITED}</p>
        </div>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={drop}
          onClick={() => stage !== "uploading" && input.current?.click()}
          role="button"
          tabIndex={0}
          aria-label="Choose a photo or video to upload"
          onKeyDown={(e) => {
            if ((e.key === "Enter" || e.key === " ") && stage !== "uploading") input.current?.click();
          }}
          className={`mt-6 flex min-h-64 cursor-pointer items-center justify-center rounded-2xl border-2 border-dashed p-6 text-center transition sm:p-10 ${
            drag
              ? "border-[#4f7cff] bg-[#4f7cff]/10 shadow-[0_0_70px_rgba(79,124,255,.18)]"
              : "border-white/[.12] bg-gradient-to-b from-white/[.04] to-white/[.01] hover:border-[#4f7cff]/40 hover:bg-white/[.05]"
          }`}
        >
          <input
            ref={input}
            type="file"
            accept={ALLOWED_EXT.map((x) => `.${x}`).join(",")}
            className="sr-only"
            onChange={(e) => void pick(e.target.files?.[0] || null)}
          />
          {stage === "uploading" && progress ? (
            <div>
              <p className="font-medium text-white">Uploading {file?.name}</p>
              <div className="mx-auto mt-4 h-2 max-w-md overflow-hidden rounded-full bg-white/10">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6]"
                  style={{ width: `${progress.percent}%` }}
                />
              </div>
              <p className="mt-2 text-sm text-white/55">
                {progress.percent}% · {bytes(progress.loaded)} / {bytes(progress.total)}
              </p>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  cancelRef.current?.cancel();
                }}
                className="mt-4 min-h-11 rounded-xl border border-white/10 px-4 py-2 text-sm text-white/70 hover:bg-white/10"
              >
                Cancel upload
              </button>
            </div>
          ) : file && meta ? (
            <div>
              <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-emerald-400/15 text-emerald-300">
                <Check className="h-7 w-7" />
              </div>
              <p className="mt-3 font-medium text-white">{file.name}</p>
              <p className="mt-1 text-sm text-white/50">
                {bytes(file.size)} · {meta.type}
              </p>
              <p className="mt-3 text-xs text-white/45">
                {meta.width}×{meta.height}
                {meta.isImage ? " · Image mode (instant inpainting)" : ` · ${Math.round(meta.duration)}s video`}
              </p>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setFile(null);
                  setMeta(null);
                  setOwnership(false);
                }}
                className="mt-4 min-h-11 rounded-xl px-3 text-sm text-[#9eb4ff] hover:underline"
              >
                Choose a different file
              </button>
            </div>
          ) : (
            <div>
              <span className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-gradient-to-br from-[#4f7cff]/25 to-[#8b5cf6]/15 text-[#9db9ff] shadow-[0_8px_30px_rgba(79,124,255,.15)]">
                <UploadCloud className="h-8 w-8" />
              </span>
              <p className="mt-4 font-medium text-white sm:hidden">Tap to choose a photo or video</p>
              <p className="mt-4 hidden font-medium text-white sm:block">Drag & drop photos or videos here</p>
              <p className="mt-1 text-sm text-white/50">
                <span className="sm:hidden">Choose PNG, JPG, WebP, MP4, MOV, or WebM</span>
                <span className="hidden sm:inline">or click to browse from your device</span>
              </p>
              <div className="mt-4 flex flex-wrap items-center justify-center gap-1.5 text-xs text-white/40">
                <span className="rounded-md border border-white/10 bg-white/[.04] px-2 py-0.5 text-cyan-300">JPG</span>
                <span className="rounded-md border border-white/10 bg-white/[.04] px-2 py-0.5 text-cyan-300">PNG</span>
                <span className="rounded-md border border-white/10 bg-white/[.04] px-2 py-0.5 text-cyan-300">WEBP</span>
                <span className="mx-1 text-white/20">|</span>
                <span className="rounded-md border border-white/10 bg-white/[.04] px-2 py-0.5 text-violet-300">MP4</span>
                <span className="rounded-md border border-white/10 bg-white/[.04] px-2 py-0.5 text-violet-300">MOV</span>
                <span className="rounded-md border border-white/10 bg-white/[.04] px-2 py-0.5 text-violet-300">WEBM</span>
                <span className="mx-1 text-white/20">·</span>
                <span>max {MAX_MB} MB</span>
              </div>
            </div>
          )}
        </div>

        {error && (
          <div role="alert" className="mt-4 flex gap-2 rounded-xl border border-rose-400/20 bg-rose-500/10 p-4 text-sm text-rose-200">
            <X className="h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        <label className="mt-6 flex min-h-12 cursor-pointer items-start gap-3 rounded-2xl border border-white/[.08] bg-gradient-to-b from-white/[.05] to-white/[.02] p-4 transition hover:border-white/[.16]">
          <input
            type="checkbox"
            checked={ownership}
            onChange={(e) => setOwnership(e.target.checked)}
            disabled={stage === "uploading"}
            className="mt-0.5 h-5 w-5 accent-[#4f7cff]"
          />
          <span className="text-sm leading-6 text-white/75">{LEGAL}</span>
        </label>
        <p className="mt-2 text-xs text-white/35">
          Policy version {POLICY_VERSION} ·{" "}
          <Link href="/terms" className="underline hover:text-white/60">
            Read the full authorized-use policy
          </Link>
        </p>

        {stage === "select" && (
          <>
            <button
              type="button"
              onClick={start}
              disabled={!valid}
              className="mt-6 flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-4 py-3 font-semibold text-white shadow-[0_12px_36px_rgba(109,94,247,.35)] transition hover:brightness-110 hover:shadow-[0_14px_44px_rgba(109,94,247,.5)] disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
            >
              <Sparkles className="h-4 w-4" />
              {valid
                ? meta?.isImage
                  ? "Confirm ownership and start photo cleanup"
                  : "Confirm ownership and upload video"
                : "Select a photo or video and confirm ownership to continue"}
            </button>
            {!valid && (
              <p className="mt-2 text-center text-xs text-white/35">
                Choose a supported image or video and check the ownership confirmation box.
              </p>
            )}
          </>
        )}

        {stage === "error" && (
          <button
            type="button"
            onClick={() => setStage("select")}
            className="mt-6 min-h-11 rounded-xl border border-white/10 px-4 py-2.5 text-sm text-white/75 hover:bg-white/10"
          >
            Try again
          </button>
        )}

        {stage === "done" && projectId && (
          <p className="mt-6 text-sm text-emerald-300">Upload complete. Opening your project workspace…</p>
        )}
      </div>
    </WorkspaceShell>
  );
}