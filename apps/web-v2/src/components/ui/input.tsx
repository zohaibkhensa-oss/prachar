import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "w-full bg-paper text-ink border-3 border-ink px-4 py-3 font-body focus:outline-none focus:ring-0 placeholder:text-ink/40",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";
