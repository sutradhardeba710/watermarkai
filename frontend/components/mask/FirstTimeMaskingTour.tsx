"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, X } from "lucide-react";

import { Button } from "@/components/ui/button";

const STORAGE_KEY = "vwa_mask_tour_seen";

const STEPS = [
  { title: "Your video canvas", body: "This is your video. Zoom, pan, and step through frames to inspect the area you want to remove." },
  { title: "Selection tools", body: "Start with AI Detect for an automatic suggestion, or draw the area yourself with Rectangle, Polygon, or Brush." },
  { title: "Mask adjustments", body: "Fine-tune the selection — expand or shrink it, soften the edges, and steady it across frames." },
  { title: "Review the timeline", body: "Scrub through the video and check the mask still covers the watermark at several timestamps." },
  { title: "Save and continue", body: "Save your mask, generate a free preview, then continue when you're happy with the result." },
];

/**
 * Optional first-run guided tour. Skippable and shown once (localStorage).
 * Deliberately a lightweight centered card rather than a permanent overlay.
 */
export function FirstTimeMaskingTour({ forceOpen, onClose }: { forceOpen?: boolean; onClose?: () => void }) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (forceOpen) {
      setOpen(true);
      setStep(0);
      return;
    }
    try {
      if (!window.localStorage.getItem(STORAGE_KEY)) setOpen(true);
    } catch {
      /* ignore */
    }
  }, [forceOpen]);

  const finish = () => {
    try {
      window.localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* ignore */
    }
    setOpen(false);
    onClose?.();
  };

  const current = STEPS[step];
  const isLast = step === STEPS.length - 1;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[60] grid place-items-end bg-black/40 p-4 backdrop-blur-[2px] sm:place-items-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="tour-title"
            className="w-full max-w-sm rounded-3xl border border-white/10 bg-[#10121f] p-6 text-white shadow-2xl"
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 20, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="flex items-start justify-between">
              <span className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-2.5 py-0.5 text-[11px] font-medium text-cyan-100">
                Step {step + 1} of {STEPS.length}
              </span>
              <button
                type="button"
                onClick={finish}
                aria-label="Skip tour"
                className="grid h-11 w-11 place-items-center rounded-xl text-white/40 hover:bg-white/5 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <h2 id="tour-title" className="mt-3 text-lg font-semibold">{current.title}</h2>
            <p className="mt-2 text-sm leading-6 text-white/55">{current.body}</p>

            <div className="mt-5 flex items-center justify-between">
              <div className="flex gap-1.5">
                {STEPS.map((_, i) => (
                  <span key={i} className={`h-1.5 rounded-full transition-all ${i === step ? "w-5 bg-cyan-300" : "w-1.5 bg-white/15"}`} />
                ))}
              </div>
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={finish}>Skip</Button>
                <Button variant="primary" size="sm" onClick={() => (isLast ? finish() : setStep((s) => s + 1))}>
                  {isLast ? "Get started" : <>Next <ArrowRight className="h-4 w-4" /></>}
                </Button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
