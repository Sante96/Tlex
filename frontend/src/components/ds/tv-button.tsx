"use client";

import { forwardRef } from "react";
import { cn } from "@/lib/utils";

const variants = {
  primary: {
    base: "bg-[#e5a00d] text-black focus:ring-[#e5a00d]",
    disabled: "bg-[#e5a00d] text-black opacity-50",
  },
  secondary: {
    base: "bg-[#27272a] text-[#fafafa] focus:ring-[#71717a]",
    disabled: "bg-[#27272a] text-[#fafafa] opacity-50",
  },
  ghost: {
    base: "bg-transparent text-[#a1a1aa] focus:ring-[#71717a]",
    disabled: "bg-transparent text-[#a1a1aa] opacity-50",
  },
} as const;

type TVButtonVariant = keyof typeof variants;

interface TVButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: TVButtonVariant;
  icon?: React.ReactNode;
}

export const TVButton = forwardRef<HTMLButtonElement, TVButtonProps>(
  (
    { variant = "primary", icon, children, className, disabled, ...props },
    ref,
  ) => {
    const v = variants[variant];
    return (
      <button
        ref={ref}
        disabled={disabled}
        className={cn(
          "inline-flex items-center justify-center gap-3 h-14 rounded-xl px-8 text-lg font-semibold transition-all cursor-pointer outline-none",
          "focus:ring-4 focus:ring-offset-2 focus:ring-offset-black",
          "active:scale-95",
          "disabled:cursor-not-allowed",
          disabled ? v.disabled : v.base,
          className,
        )}
        {...props}
      >
        {icon}
        {children}
      </button>
    );
  },
);

TVButton.displayName = "TVButton";
