"use client";

import { ChevronLeft, ChevronRight, Pause, Play, SkipBack, SkipForward, Volume2, VolumeX } from "lucide-react";

import { Button } from "@/components/ui/button";
import { InfoTip, TooltipProvider } from "@/components/ui/tooltip";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { useMaskWorkspace } from "@/features/mask/useMaskWorkspace";
import { cn } from "@/lib/utils";

type Ws = ReturnType<typeof useMaskWorkspace>;

const SPEEDS = [0.5, 1, 1.5, 2];

function fmt(t: number) {
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  const cs = Math.floor((t * 100) % 100);
  return `${m}:${String(s).padStart(2, "0")}.${String(cs).padStart(2, "0")}`;
}

export function PlaybackControls({ ws }: { ws: Ws }) {
  const { playing, togglePlay, seek, stepFrame, duration, currentTime, muted, toggleMute, playbackRate, changeRate } = ws;

  return (
    <TooltipProvider delayDuration={150}>
      <div className="flex flex-wrap items-center gap-1.5">
        <InfoTip label="Jump to start"><Button variant="secondary" size="icon" aria-label="Jump to start" onClick={() => seek(0)}><SkipBack className="h-4 w-4" /></Button></InfoTip>
        <InfoTip label="Previous frame"><Button variant="secondary" size="icon" aria-label="Previous frame" onClick={() => stepFrame(-1)}><ChevronLeft className="h-4 w-4" /></Button></InfoTip>
        <InfoTip label={playing ? "Pause" : "Play"}>
          <Button variant="primary" size="icon" aria-label={playing ? "Pause video" : "Play video"} onClick={togglePlay}>
            {playing ? <Pause className="h-4 w-4 fill-current" /> : <Play className="ml-0.5 h-4 w-4 fill-current" />}
          </Button>
        </InfoTip>
        <InfoTip label="Next frame"><Button variant="secondary" size="icon" aria-label="Next frame" onClick={() => stepFrame(1)}><ChevronRight className="h-4 w-4" /></Button></InfoTip>
        <InfoTip label="Jump to end"><Button variant="secondary" size="icon" aria-label="Jump to end" onClick={() => seek(duration)}><SkipForward className="h-4 w-4" /></Button></InfoTip>

        <span className="ml-1 font-mono text-xs tabular-nums text-white/70">
          {fmt(currentTime)} <span className="text-white/30">/</span> {fmt(duration)}
        </span>

        <div className="ml-auto flex items-center gap-1.5">
          <InfoTip label={muted ? "Unmute" : "Mute"}>
            <Button variant="secondary" size="icon" aria-label={muted ? "Unmute" : "Mute"} onClick={toggleMute}>
              {muted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
            </Button>
          </InfoTip>
          <DropdownMenu>
            <InfoTip label="Playback speed">
              <DropdownMenuTrigger asChild>
                <Button variant="secondary" size="sm" className="min-w-14 font-mono text-xs" aria-label="Playback speed">
                  {playbackRate}×
                </Button>
              </DropdownMenuTrigger>
            </InfoTip>
            <DropdownMenuContent align="end">
              {SPEEDS.map((s) => (
                <DropdownMenuItem
                  key={s}
                  onSelect={() => changeRate(s)}
                  className={cn(playbackRate === s && "text-cyan-200")}
                >
                  {s}× {s === 1 && "(normal)"}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </TooltipProvider>
  );
}
