import { forwardRef, type LabelHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export interface LabelProps extends LabelHTMLAttributes<HTMLLabelElement> {}

export const Label = forwardRef<HTMLLabelElement, LabelProps>(
  ({ className, ...props }, ref) => (
    <label
      ref={ref}
      className={cn(
        "font-mono text-xs uppercase tracking-wider text-ink/70 block mb-1.5",
        className,
      )}
      {...props}
    />
  ),
);
Label.displayName = "Label";
