import { forwardRef, useState } from "react";
import { cn } from "@/lib/utils";

interface DSInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  suffix?: React.ReactNode;
}

export const DSInput = forwardRef<HTMLInputElement, DSInputProps>(
  (
    { label, error, suffix, className, disabled, onFocus, onBlur, ...props },
    ref,
  ) => {
    const [focused, setFocused] = useState(false);

    const borderClass = error
      ? "border-[#ef4444]"
      : focused
        ? "border-[#e5a00d] border-2"
        : "border-[#3f3f46]";

    const labelColor = error
      ? "text-[#ef4444]"
      : focused
        ? "text-[#e5a00d]"
        : "text-[#a1a1aa]";

    return (
      <div
        className={cn(
          "flex flex-col gap-1.5",
          disabled && "opacity-50",
          className,
        )}
      >
        {label && (
          <label className={cn("text-sm font-medium", labelColor)}>
            {label}
          </label>
        )}
        <div className="relative">
          <input
            ref={ref}
            disabled={disabled}
            className={cn(
              "w-full h-10 rounded-lg bg-[#18181b] px-3 text-sm text-[#fafafa] border outline-none transition-colors",
              "placeholder:text-[#52525b]",
              "disabled:cursor-not-allowed",
              borderClass,
              disabled && "border-[#27272a]",
              suffix && "pr-10",
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
            <div className="absolute right-0 top-0 h-full flex items-center pr-3">
              {suffix}
            </div>
          )}
        </div>
        {error && <p className="text-xs text-[#ef4444]">{error}</p>}
      </div>
    );
  },
);

DSInput.displayName = "DSInput";
