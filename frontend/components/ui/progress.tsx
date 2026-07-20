"use client";

import * as React from "react";
import * as ProgressPrimitive from "@radix-ui/react-progress";

import { cn } from "@/lib/utils";

export const Progress = React.forwardRef<
  React.ElementRef<typeof ProgressPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root> & { value?: number }
>(({ className, value = 0, ...props }, ref) => (
  <ProgressPrimitive.Root
    ref={ref}
    className={cn("relative h-1.5 w-full overflow-hidden rounded-full bg-white/10", className)}
    {...props}
  >
    <ProgressPrimitive.Indicator
      className="h-full rounded-full bg-gradient-to-r from-[#4f7cff] via-cyan-400 to-[#6d5ef7] transition-[width] duration-300 motion-reduce:transition-none"
      style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
    />
  </ProgressPrimitive.Root>
));
Progress.displayName = ProgressPrimitive.Root.displayName;
