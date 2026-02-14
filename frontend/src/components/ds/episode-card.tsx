import Image from "next/image";
import { Play } from "lucide-react";

interface EpisodeCardProps {
  episodeNumber: number;
  title: string;
  duration?: string;
  overview?: string | null;
  thumbnailUrl: string | null;
  progress?: number;
  onClick?: () => void;
}

export function EpisodeCard({
  episodeNumber,
  title,
  duration,
  overview,
  thumbnailUrl,
  progress,
  onClick,
}: EpisodeCardProps) {
  const hasProgress = progress !== undefined && progress > 0;

  return (
    <div
      className="group flex items-center gap-4 h-[120px] rounded-xl p-3 cursor-pointer transition-colors hover:bg-[#27272a]"
      style={{ backgroundColor: "#18181b" }}
      onClick={onClick}
    >
      {/* Thumbnail */}
      <div className="shrink-0 w-[170px] h-24 rounded-lg overflow-hidden relative bg-[#27272a]">
        {thumbnailUrl ? (
          <Image src={thumbnailUrl} alt={title} fill className="object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-[#52525b]">
            E{episodeNumber}
          </div>
        )}

        {/* Play overlay */}
        <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
          <div className="w-10 h-10 rounded-full bg-black/50 flex items-center justify-center">
            <Play className="h-[18px] w-[18px] text-[#fafafa] fill-[#fafafa]" />
          </div>
        </div>

        {/* Progress bar */}
        {hasProgress && (
          <div className="absolute bottom-0 left-2 right-2 h-1 rounded bg-[#3f3f46]">
            <div
              className="h-full rounded bg-[#e5a00d]"
              style={{ width: `${progress}%` }}
            />
          </div>
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0 flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-[#e5a00d]">
            {episodeNumber} ▶
          </span>
          <h3 className="text-base font-medium text-[#fafafa] truncate">
            {title}
          </h3>
        </div>
        {duration && (
          <span className="text-[13px] text-[#71717a]">{duration}</span>
        )}
        {overview && (
          <p className="text-[13px] text-[#a1a1aa] leading-relaxed line-clamp-2">
            {overview}
          </p>
        )}
      </div>
    </div>
  );
}
