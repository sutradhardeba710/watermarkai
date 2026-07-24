"use client";

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/70 focus-visible:ring-offset-2 focus-visible:ring-offset-[#07080f] disabled:pointer-events-none disabled:opacity-40 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary:
          "bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] text-white shadow-[0_8px_22px_rgba(79,124,255,.24)] hover:brightness-110",
        secondary:
          "border border-white/10 bg-white/[.03] text-white/70 hover:bg-white/[.07] hover:text-white",
        ghost: "text-white/60 hover:bg-white/5 hover:text-white",
        outline:
          "border border-white/10 text-white/70 hover:bg-white/5 hover:text-white",
        accent:
          "border border-cyan-300/25 bg-cyan-300/10 text-cyan-100 hover:bg-cyan-300/15",
        danger:
          "text-rose-300/80 hover:bg-rose-400/10 hover:text-rose-200",
        success:
          "bg-emerald-500 text-[#06120d] hover:bg-emerald-400",
      },
      size: {
        sm: "min-h-11 px-3",
        md: "min-h-11 px-4",
        lg: "min-h-12 px-5",
        icon: "h-11 w-11",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, type, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        type={asChild ? undefined : (type ?? "button")}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { buttonVariants };
