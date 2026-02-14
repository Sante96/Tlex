"use client";

import { forwardRef } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

const variants = {
  primary: {
    base: "bg-[#e5a00d] text-black hover:bg-[#d4940c] active:bg-[#b8860b]",
    disabled: "bg-[#e5a00d] text-black opacity-50",
  },
  secondary: {
    base: "bg-[#27272a] text-[#fafafa] hover:bg-[#3f3f46] active:bg-[#52525b]",
    disabled: "bg-[#27272a] text-[#fafafa] opacity-50",
  },
  ghost: {
    base: "bg-transparent text-[#a1a1aa] hover:bg-[#27272a80] hover:text-[#fafafa] active:bg-[#27272a] active:text-[#fafafa]",
    disabled: "bg-transparent text-[#a1a1aa] opacity-50",
  },
  destructive: {
    base: "bg-[#ef4444] text-white hover:bg-[#dc2626] active:bg-[#b91c1c]",
    disabled: "bg-[#ef4444] text-white opacity-50",
  },
} as const;

type ButtonVariant = keyof typeof variants;

interface DSButtonProps extends Omit<
  React.ButtonHTMLAttributes<HTMLButtonElement>,
  "onDrag" | "onDragStart" | "onDragEnd" | "onAnimationStart"
> {
  variant?: ButtonVariant;
  icon?: React.ReactNode;
}

export const DSButton = forwardRef<HTMLButtonElement, DSButtonProps>(
  (
    { variant = "primary", icon, children, className, disabled, ...props },
    ref,
  ) => {
    const v = variants[variant];
    return (
      <motion.button
        ref={ref}
        disabled={disabled}
        whileHover={disabled ? undefined : { scale: 1.02 }}
        whileTap={disabled ? undefined : { scale: 0.98 }}
        transition={{ duration: 0.15 }}
        className={cn(
          "inline-flex items-center justify-center gap-2 h-10 rounded-lg px-4 text-sm font-medium transition-colors cursor-pointer",
          "disabled:cursor-not-allowed",
          disabled ? v.disabled : v.base,
          className,
        )}
        {...props}
      >
        {icon}
        {children}
      </motion.button>
    );
  },
);

DSButton.displayName = "DSButton";
