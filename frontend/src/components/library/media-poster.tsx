"use client";

import Image from "next/image";
import Link from "next/link";
import { Play, MoreVertical } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { MediaItem } from "@/lib/api";
import { getTmdbImageUrl } from "@/lib/format";

interface MediaPosterProps {
  media: MediaItem;
  showTitle?: boolean;
}

export function MediaPoster({ media, showTitle = true }: MediaPosterProps) {
  const posterUrl = getTmdbImageUrl(media.poster_path, "w500");

  const year = media.release_date
    ? new Date(media.release_date).getFullYear()
    : null;

  const subtitle =
    media.media_type === "EPISODE"
      ? `S${media.season_number || 1} · E${media.episode_number || 1}`
      : year?.toString();

  return (
    <Link href={`/media/${media.id}`} className="group block">
      {/* Poster container */}
      <motion.div
        className="relative aspect-[2/3] bg-zinc-800 rounded-md overflow-hidden"
        whileHover={{ scale: 1.03, y: -4 }}
        transition={{ type: "spring", stiffness: 400, damping: 25 }}
      >
        {posterUrl ? (
          <Image
            src={posterUrl}
            alt={media.title}
            fill
            className="object-cover transition-transform duration-300 group-hover:scale-105"
            sizes="(max-width: 640px) 50vw, (max-width: 1024px) 25vw, 16vw"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-zinc-600 text-sm">
            No Poster
          </div>
        )}

        {/* Hover overlay */}
        <div
          className={cn(
            "absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100",
            "transition-opacity duration-200 flex items-center justify-center",
          )}
        >
          {/* Play button */}
          <div className="w-12 h-12 rounded-full bg-white/90 flex items-center justify-center">
            <Play className="w-6 h-6 text-black fill-black ml-0.5" />
          </div>

          {/* More menu button */}
          <button
            className="absolute top-2 right-2 w-8 h-8 rounded-full bg-black/50 flex items-center justify-center hover:bg-black/70"
            onClick={(e) => {
              e.preventDefault();
              // TODO: Open context menu
            }}
          >
            <MoreVertical className="w-4 h-4 text-white" />
          </button>
        </div>

        {/* Watch progress indicator (top-left dot) */}
        {media.watch_progress && media.watch_progress > 0 && (
          <div className="absolute top-2 left-2 w-3 h-3 rounded-full bg-plex-orange" />
        )}

        {/* Unwatched episodes badge (top-right) */}
        {media.unwatched_count && media.unwatched_count > 0 && (
          <div className="absolute top-2 right-2 bg-plex-orange text-black text-xs font-bold px-1.5 py-0.5 rounded">
            {media.unwatched_count}
          </div>
        )}
      </motion.div>

      {/* Title and subtitle */}
      {showTitle && (
        <div className="mt-2 space-y-0.5">
          <h3 className="text-sm font-medium text-white truncate">
            {media.title}
          </h3>
          {subtitle && (
            <p className="text-xs text-muted-foreground">{subtitle}</p>
          )}
        </div>
      )}
    </Link>
  );
}
