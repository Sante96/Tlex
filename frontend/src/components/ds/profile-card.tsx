import { cn } from "@/lib/utils";
import Image from "next/image";

interface DSProfileCardProps {
  name: string;
  avatarUrl?: string | null;
  active?: boolean;
  isAdd?: boolean;
  onClick?: () => void;
}

export function DSProfileCard({
  name,
  avatarUrl,
  active,
  isAdd,
  onClick,
}: DSProfileCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex flex-col items-center gap-2 w-[120px] cursor-pointer group"
    >
      <div
        className={cn(
          "w-20 h-20 rounded-xl overflow-hidden transition-colors",
          active
            ? "ring-[3px] ring-[#e5a00d]"
            : isAdd
              ? "border-2 border-dashed border-[#3f3f46]"
              : "border-2 border-[#3f3f46] group-hover:border-[#e5a00d]",
        )}
        style={{ backgroundColor: "#27272a" }}
      >
        {avatarUrl ? (
          <Image
            src={avatarUrl}
            alt={name}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-[#52525b] text-xl font-bold">
            {isAdd ? "+" : name.charAt(0).toUpperCase()}
          </div>
        )}
      </div>
      <span className="text-sm font-medium text-[#fafafa] text-center">
        {name}
      </span>
    </button>
  );
}
