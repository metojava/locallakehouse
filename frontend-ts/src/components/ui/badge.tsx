import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium leading-5 transition-colors",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary/15 text-primary ring-1 ring-inset ring-primary/25",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground",
        outline: "border-border text-muted-foreground",
        destructive:
          "border-transparent bg-destructive/15 text-red-400 ring-1 ring-inset ring-destructive/25",
        success:
          "border-transparent bg-emerald-500/15 text-emerald-400 ring-1 ring-inset ring-emerald-500/25",
        warning:
          "border-transparent bg-amber-500/15 text-amber-400 ring-1 ring-inset ring-amber-500/25",
        info: "border-transparent bg-sky-500/15 text-sky-400 ring-1 ring-inset ring-sky-500/25",
        violet:
          "border-transparent bg-violet-500/15 text-violet-400 ring-1 ring-inset ring-violet-500/25",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
