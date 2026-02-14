import Image from "next/image";
import { cn } from "@/lib/utils";

interface DSAvatarProps {
  letter: string;
  src?: string;
  size?: number;
  className?: string;
}

export function DSAvatar({ letter, src, size = 36, className }: DSAvatarProps) {
  return (
    <div
      className={cn(
        "relative flex items-center justify-center rounded-full overflow-hidden",
        "bg-[#e5a00d] text-black text-sm font-semibold",
        "hover:ring-2 hover:ring-[#e5a00d80] transition-shadow cursor-pointer",
        className,
      )}
      style={{ width: size, height: size, borderRadius: size / 2 }}
    >
      {src ? (
        <Image
          src={src}
          alt={letter}
          fill
          className="object-cover"
          sizes={`${size}px`}
        />
      ) : (
        letter.charAt(0).toUpperCase()
      )}
    </div>
  );
}
