"use client";

import { forwardRef } from "react";
import { cn } from "@/lib/utils";
import { DSButton } from "./button";

interface DSIconButtonProps extends Omit<
  React.ButtonHTMLAttributes<HTMLButtonElement>,
  "onDrag" | "onDragStart" | "onDragEnd" | "onAnimationStart"
> {
  icon: React.ReactNode;
}

export const DSIconButton = forwardRef<HTMLButtonElement, DSIconButtonProps>(
  ({ icon, className, ...props }, ref) => {
    return (
      <DSButton
        ref={ref}
        variant="ghost"
        icon={icon}
        className={cn("w-8 h-8 p-0", className)}
        {...props}
      />
    );
  },
);

DSIconButton.displayName = "DSIconButton";
