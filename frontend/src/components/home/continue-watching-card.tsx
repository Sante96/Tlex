"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { Play } from "lucide-react";
import { FadeImage } from "@/components/ui/fade-image";
import { cn } from "@/lib/utils";
import { cleanEpisodeTitle, formatDuration, getTmdbImageUrl } from "@/lib/format";
import type { ContinueWatchingItem } from "@/lib/api";

/**
 * A title being watched, as a landscape card: the episode's still (a movie's backdrop),
 * the progress, and which episode and how much is left. The posters said neither.
 */
export function ContinueWatchingCard({
  item,
  className,
}: {
  item: ContinueWatchingItem;
  className?: string;
}) {
  const t = useTranslations();
  const still = getTmdbImageUrl(item.still_path ?? item.backdrop_path, "w780");
  const episode =
    item.season_number && item.episode_number
      ? `S${item.season_number} · E${item.episode_number} · ${cleanEpisodeTitle(item.title)}`
      : null;
  const remaining = item.duration_seconds - item.position_seconds;
  const left = remaining > 60 ? formatDuration(remaining) : null;
  const details = [episode, left && t("home.timeLeft", { time: left })].filter(Boolean).join(" · ");

  return (
    <Link href={`/watch/${item.id}`} className={cn("group block outline-none", className)}>
      <div className="relative aspect-video rounded-lg overflow-hidden bg-[#27272a] ring-2 ring-transparent group-focus-visible:ring-plex-orange transition-shadow">
        {still && (
          <FadeImage
            src={still}
            alt=""
            fill
            sizes="(min-width: 1280px) 22vw, (min-width: 1024px) 30vw, (min-width: 768px) 45vw, 260px"
            className="object-cover transition-transform duration-300 group-hover:scale-105"
          />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
        {/* Play: on hover (mouse) and focus (D-pad) */}
        <div className="absolute inset-0 flex items-center justify-center bg-black/0 group-hover:bg-black/30 group-focus-visible:bg-black/30 transition-colors">
          <Play className="h-10 w-10 text-white fill-white opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100 transition-opacity" />
        </div>
        <div className="absolute inset-x-0 bottom-0 h-1 bg-white/20">
          <div
            className="h-full bg-plex-orange"
            style={{ width: `${Math.min(100, item.progress_percent)}%` }}
          />
        </div>
      </div>
      <p className="mt-2 text-sm font-medium text-[#fafafa] truncate">
        {item.series_title || item.title}
      </p>
      {details && <p className="text-xs text-[#a1a1aa] truncate">{details}</p>}
    </Link>
  );
}
