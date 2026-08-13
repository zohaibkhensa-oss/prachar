import { forwardRef, type LabelHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export interface LabelProps extends LabelHTMLAttributes<HTMLLabelElement> {}

export const Label = forwardRef<HTMLLabelElement, LabelProps>(
  ({ className, ...props }, ref) => (
    <label
      ref={ref}
      className={cn(
        "font-mono text-[11px] uppercase tracking-wider text-text-secondary block mb-1.5",
        className,
      )}
      {...props}
    />
  ),
);
Label.displayName = "Label";
