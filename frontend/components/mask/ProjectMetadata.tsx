"use client";

import type { VideoProject } from "@/types";
import { cn } from "@/lib/utils";

/** Compact video metadata chips: resolution, codec, duration, fps. */
export function ProjectMetadata({ project, className }: { project: VideoProject; className?: string }) {
  const chips = [
    project.width && project.height ? `${project.width}×${project.height}` : null,
    project.video_codec ? project.video_codec.toUpperCase() : null,
    project.duration != null ? `${project.duration.toFixed(1)}s` : null,
    project.fps != null ? `${project.fps.toFixed(2)} fps` : null,
  ].filter(Boolean) as string[];

  return (
    <div className={cn("flex flex-wrap gap-1.5", className)}>
      {chips.map((c) => (
        <span
          key={c}
          className="rounded-full border border-white/10 bg-white/[.04] px-2.5 py-0.5 text-[11px] text-white/55"
        >
          {c}
        </span>
      ))}
    </div>
  );
}
