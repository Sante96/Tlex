import { cn } from "@/lib/utils";

interface ActionButtonProps {
  /** "primary" = orange bg, black text. "secondary" = glass bg, white text */
  variant?: "primary" | "secondary";
  icon?: React.ReactNode;
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
}

export function ActionButton({
  variant = "primary",
  icon,
  children,
  onClick,
  className,
}: ActionButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-2 h-11 rounded-[10px] text-[15px] transition-all duration-150",
        variant === "primary"
          ? "px-6 font-semibold text-black bg-[#e5a00d] hover:bg-[#f0b429] active:bg-[#c89200] shadow-lg shadow-[#e5a00d]/20 hover:shadow-[#e5a00d]/30"
          : "px-5 font-medium text-[#fafafa] bg-white/10 backdrop-blur-md border border-white/15 hover:bg-white/20 hover:border-white/25 active:bg-white/5",
        className,
      )}
    >
      {icon}
      {children}
    </button>
  );
}
