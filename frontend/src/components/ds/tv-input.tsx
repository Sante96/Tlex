"use client";

import { forwardRef, useState } from "react";
import { cn } from "@/lib/utils";

interface TVInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  suffix?: React.ReactNode;
}

export const TVInput = forwardRef<HTMLInputElement, TVInputProps>(
  (
    { label, error, suffix, className, disabled, onFocus, onBlur, ...props },
    ref,
  ) => {
    const [focused, setFocused] = useState(false);

    const borderClass = error
      ? "border-[#ef4444] border-2"
      : focused
        ? "border-[#e5a00d] border-2 ring-4 ring-[#e5a00d]/30"
        : "border-[#3f3f46]";

    const labelColor = error
      ? "text-[#ef4444]"
      : focused
        ? "text-[#e5a00d]"
        : "text-[#a1a1aa]";

    return (
      <div
        className={cn(
          "flex flex-col gap-2",
          disabled && "opacity-50",
          className,
        )}
      >
        {label && (
          <label className={cn("text-base font-medium", labelColor)}>
            {label}
          </label>
        )}
        <div className="relative">
          <input
            ref={ref}
            disabled={disabled}
            suppressHydrationWarning
            className={cn(
              "w-full h-14 rounded-xl bg-[#18181b] px-4 text-lg text-[#fafafa] border outline-none transition-all",
              "placeholder:text-[#52525b]",
              "disabled:cursor-not-allowed",
              borderClass,
              disabled && "border-[#27272a]",
              suffix && "pr-14",
            )}
            onFocus={(e) => {
              setFocused(true);
              onFocus?.(e);
            }}
            onBlur={(e) => {
              setFocused(false);
              onBlur?.(e);
            }}
            {...props}
          />
          {suffix && (
            <div className="absolute right-0 top-0 h-full flex items-center pr-4">
              {suffix}
            </div>
          )}
        </div>
        {error && <p className="text-sm text-[#ef4444]">{error}</p>}
      </div>
    );
  },
);

TVInput.displayName = "TVInput";
