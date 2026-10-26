import { cn } from "@/lib/utils";

interface ActionButtonProps {
  /** "primary" = orange bg, black text. "secondary" = glass bg, white text */
  variant?: "primary" | "secondary";
  icon?: React.ReactNode;
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
  /** Focused on mount: the choice the TV remote starts on */
  autoFocus?: boolean;
}

export function ActionButton({
  variant = "primary",
  icon,
  children,
  onClick,
  className,
  autoFocus,
}: ActionButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      autoFocus={autoFocus}
      className={cn(
        "inline-flex items-center gap-2 h-11 rounded-[10px] text-[15px] transition-all duration-150",
        variant === "primary"
          ? "px-6 font-semibold text-black bg-plex-orange hover:bg-[#f0b429] active:bg-[#c89200] shadow-lg shadow-plex-orange/20 hover:shadow-plex-orange/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-plex-orange focus-visible:ring-offset-2 focus-visible:ring-offset-black"
          : "px-5 font-medium text-[#fafafa] bg-white/10 backdrop-blur-md border border-white/15 hover:bg-white/20 hover:border-white/25 active:bg-white/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-plex-orange focus-visible:ring-offset-2 focus-visible:ring-offset-black",
        className,
      )}
    >
      {icon}
      {children}
    </button>
  );
}
