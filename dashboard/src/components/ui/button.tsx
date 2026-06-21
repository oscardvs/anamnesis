import * as React from "react";

import { Slot } from "radix-ui";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/cn";

const button = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg font-medium " +
    "transition-[transform,background-color,color,box-shadow] duration-200 ease-[var(--ease-fluid)] " +
    "select-none outline-none focus-visible:ring-2 focus-visible:ring-accent/60 " +
    "active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 " +
    "[&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary:
          "bg-accent text-accent-contrast hover:bg-accent-strong shadow-[0_1px_2px_rgba(0,0,0,0.18)]",
        secondary: "bezel bg-surface-2 text-text hover:bg-elevated",
        outline: "bezel bg-transparent text-text hover:bg-highlight",
        ghost: "bg-transparent text-muted hover:bg-highlight hover:text-text",
        danger: "bg-transparent text-danger hover:bg-del-tint",
      },
      size: {
        sm: "h-8 px-3 text-xs [&_svg]:size-3.5",
        md: "h-9 px-4 text-sm [&_svg]:size-4",
        lg: "h-10 px-5 text-sm [&_svg]:size-4",
        icon: "size-9 [&_svg]:size-4",
        "icon-sm": "size-8 [&_svg]:size-4",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof button> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild, ...props }, ref) => {
    const Comp = asChild ? Slot.Root : "button";
    return <Comp ref={ref} className={cn(button({ variant, size }), className)} {...props} />;
  },
);
Button.displayName = "Button";

export { button as buttonVariants };
