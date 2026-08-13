import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "w-full bg-bg-surface text-text rounded-lg px-4 py-2.5 text-sm font-body",
        "border border-white/[0.06] transition-all duration-200",
        "placeholder:text-text-muted",
        "focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";
