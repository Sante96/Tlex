import { cn } from "@/lib/utils";

const levels = {
  primary: "bg-[#18181b] border-[#27272a]",
  secondary: "bg-[#1f1f23] border-[#27272a]",
  tertiary: "bg-[#27272a] border-[#3f3f46]",
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
        "rounded-xl border p-5 flex flex-col gap-3",
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
