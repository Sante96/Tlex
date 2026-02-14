import { cn } from "@/lib/utils";

interface ActionButtonProps {
  /** "primary" = orange bg, black text. "secondary" = #27272a bg, white text */
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
        "inline-flex items-center gap-2 h-11 rounded-[10px] text-[15px] transition-colors",
        variant === "primary"
          ? "px-6 font-semibold text-black bg-[#e5a00d] hover:bg-[#d4920c]"
          : "px-5 font-medium text-[#fafafa] bg-[#27272a] hover:bg-[#3f3f46]",
        className,
      )}
    >
      {icon}
      {children}
    </button>
  );
}
