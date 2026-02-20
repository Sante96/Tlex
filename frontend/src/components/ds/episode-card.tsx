import Image from "next/image";
import { Play, Check, Pencil } from "lucide-react";

interface EpisodeCardProps {
  episodeNumber: number;
  title: string;
  duration?: string;
  overview?: string | null;
  thumbnailUrl: string | null;
  progress?: number;
  isWatched?: boolean;
  onClick?: () => void;
  onEdit?: () => void;
}

export function EpisodeCard({
  episodeNumber,
  title,
  duration,
  overview,
  thumbnailUrl,
  progress,
  isWatched,
  onClick,
  onEdit,
}: EpisodeCardProps) {
  const hasProgress = progress !== undefined && progress > 0;

  return (
    <div
      className="group cursor-pointer relative aspect-video rounded-lg overflow-hidden bg-[#27272a]"
      onClick={onClick}
    >
      {/* Thumbnail */}
      {thumbnailUrl ? (
        <Image src={thumbnailUrl} alt={title} fill className="object-cover" />
      ) : (
        <div className="w-full h-full flex items-center justify-center text-[#52525b] text-lg font-medium">
          E{episodeNumber}
        </div>
      )}

      {/* Edit button — top-left, visible on hover */}
      {onEdit && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onEdit();
          }}
          className="absolute top-2 left-2 w-7 h-7 rounded-full bg-black/60 backdrop-blur-sm flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity z-10 hover:bg-black/80"
        >
          <Pencil className="h-3.5 w-3.5 text-white" />
        </button>
      )}

      {/* Watched badge */}
      {isWatched && (
        <div className="absolute top-2 right-2 w-6 h-6 rounded-full bg-[#e5a00d] flex items-center justify-center z-10">
          <Check className="h-3.5 w-3.5 text-black" strokeWidth={3} />
        </div>
      )}

      {/* Bottom info overlay with gradient */}
      <div
        className="absolute inset-x-0 bottom-0 p-3 pt-10 flex flex-col gap-1"
        style={{
          background:
            "linear-gradient(to top, #09090b 0%, #09090bcc 50%, transparent 100%)",
        }}
      >
        <h3 className="text-sm font-semibold text-white truncate">{title}</h3>
        <div className="flex items-center gap-2 text-xs text-white/70">
          <span>Episodio {episodeNumber}</span>
          {duration && (
            <>
              <span>·</span>
              <span>{duration}</span>
            </>
          )}
        </div>
        {overview && (
          <p className="text-[11px] text-white/60 leading-relaxed line-clamp-2">
            {overview}
          </p>
        )}
      </div>

      {/* Play overlay on hover */}
      <div className="absolute inset-0 bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
        <div className="w-12 h-12 rounded-full bg-black/60 backdrop-blur-sm flex items-center justify-center">
          <Play className="h-5 w-5 text-white fill-white ml-0.5" />
        </div>
      </div>

      {/* Progress bar */}
      {hasProgress && (
        <div className="absolute bottom-0 left-0 right-0 h-1 bg-white/20 z-10">
          <div
            className="h-full bg-[#e5a00d]"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </div>
  );
}
