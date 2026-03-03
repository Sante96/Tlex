import { cn } from "@/lib/utils";

const levels = {
  primary: "bg-[rgba(10,10,10,0.55)] border-white/[0.06]",
  secondary: "bg-white/[0.04] border-white/[0.06]",
  tertiary: "bg-white/[0.06] border-white/[0.08]",
} as const;

type CardLevel = keyof typeof levels;

interface DSCardProps {
  level?: CardLevel;
  title?: string;
  description?: string;
  icon?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}

export function DSCard({
  level = "primary",
  title,
  description,
  icon,
  className,
  children,
}: DSCardProps) {
  return (
    <div
      className={cn(
        "rounded-xl border p-5 flex flex-col gap-3 backdrop-blur-sm shadow-[0_8px_32px_rgba(0,0,0,0.4)]",
        levels[level],
        className,
      )}
    >
      {(title || icon) && (
        <div className="flex items-center gap-3">
          {icon}
          <div className="flex flex-col gap-1">
            {title && (
              <h3 className="text-base font-semibold text-[#fafafa]">
                {title}
              </h3>
            )}
            {description && (
              <p className="text-sm text-[#a1a1aa]">{description}</p>
            )}
          </div>
        </div>
      )}
      {children}
    </div>
  );
}
