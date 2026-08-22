import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type Variant = "yellow" | "ink" | "paper" | "ghost" | "primary" | "secondary" | "danger";
type Size = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const variants: Record<Variant, string> = {
  // New neon-black variants
  primary:
    "bg-accent text-white font-body font-semibold rounded-lg hover:shadow-glow hover:brightness-110 active:scale-[0.98]",
  secondary:
    "bg-bg-elevated text-text font-body font-medium rounded-lg border border-white/[0.08] hover:bg-bg-hover hover:border-white/[0.12] active:scale-[0.98]",
  danger:
    "bg-danger/10 text-danger font-body font-medium rounded-lg border border-danger/20 hover:bg-danger/20 active:scale-[0.98]",
  // Legacy aliases (map to new styles)
  yellow: "bg-accent text-white font-body font-semibold rounded-lg hover:shadow-glow hover:brightness-110 active:scale-[0.98]",
  ink: "bg-bg-elevated text-text font-body font-medium rounded-lg border border-white/[0.08] hover:bg-bg-hover hover:border-white/[0.12] active:scale-[0.98]",
  paper: "bg-bg-elevated text-text font-body font-medium rounded-lg border border-white/[0.08] hover:bg-bg-hover hover:border-white/[0.12] active:scale-[0.98]",
  ghost:
    "bg-transparent text-text-secondary font-body font-medium rounded-lg hover:bg-white/[0.04] hover:text-text active:scale-[0.98]",
};

const sizes: Record<Size, string> = {
  sm: "px-3 py-1.5 text-xs min-h-[36px]",
  md: "px-4 py-2.5 text-sm min-h-[40px]",
  lg: "px-6 py-3 text-base min-h-[44px]",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center gap-2 transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  ),
);
Button.displayName = "Button";
