import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type Variant = "yellow" | "ink" | "paper" | "ghost";
type Size = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const variants: Record<Variant, string> = {
  yellow:
    "bg-yellow text-ink border-3 border-ink uppercase font-display tracking-wide hover:bg-yellow-dark",
  ink: "bg-ink text-yellow border-3 border-ink uppercase font-display tracking-wide hover:bg-ink/80",
  paper:
    "bg-paper text-ink border-3 border-ink uppercase font-display tracking-wide hover:bg-paper/80",
  ghost:
    "bg-transparent text-ink border-3 border-transparent uppercase font-display tracking-wide hover:border-ink",
};

const sizes: Record<Size, string> = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-6 py-3 text-sm",
  lg: "px-8 py-4 text-base",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "yellow", size = "md", ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center transition-colors disabled:opacity-50 disabled:cursor-not-allowed",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  ),
);
Button.displayName = "Button";
