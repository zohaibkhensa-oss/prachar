import { type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type Variant = "yellow" | "ink" | "paper" | "blue" | "grey";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: Variant;
}

const variants: Record<Variant, string> = {
  yellow: "bg-yellow text-ink border-3 border-ink",
  ink: "bg-ink text-paper border-3 border-ink",
  paper: "bg-paper text-ink border-3 border-ink",
  blue: "bg-blue text-paper border-3 border-ink",
  grey: "bg-grey text-paper border-3 border-ink",
};

export function Badge({ className, variant = "ink", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center font-mono text-xs uppercase tracking-wider px-2 py-0.5",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
