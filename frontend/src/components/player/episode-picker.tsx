"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Image from "next/image";
import { AnimatePresence, motion } from "framer-motion";
import {
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Play,
  Check,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getSeriesDetails, type SeasonInfo } from "@/lib/api";
import {
  getTmdbImageUrl,
  formatDuration,
  cleanEpisodeTitle,
} from "@/lib/format";

interface EpisodePickerProps {
  open: boolean;
  seriesId: number;
  currentMediaId: number;
  currentSeason: number;
  onClose: () => void;
  onEpisodeSelect: (mediaId: number) => void;
  toggleButtonRef?: React.RefObject<HTMLButtonElement | null>;
}

export function EpisodePicker({
  open,
  seriesId,
  currentMediaId,
  currentSeason,
  onClose,
  onEpisodeSelect,
  toggleButtonRef,
}: EpisodePickerProps) {
  const [seasons, setSeasons] = useState<SeasonInfo[]>([]);
  const [activeSeason, setActiveSeason] = useState(currentSeason);
  const [loading, setLoading] = useState(true);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  // Fetch series data
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    getSeriesDetails(seriesId)
      .then((data) => {
        if (cancelled) return;
        setSeasons(data.seasons);
        setActiveSeason(currentSeason);
      })
      .catch(() => {})
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [open, seriesId, currentSeason]);

  // Scroll state check (same pattern as HorizontalScroll)
  const checkScroll = useCallback(() => {
    const el = scrollRef.current;
    if (el) {
      setCanScrollLeft(el.scrollLeft > 0);
      setCanScrollRight(el.scrollLeft < el.scrollWidth - el.clientWidth - 1);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(checkScroll, 50);
    const el = scrollRef.current;
    if (!el) return () => clearTimeout(timer);
    el.addEventListener("scroll", checkScroll);
    window.addEventListener("resize", checkScroll);
    return () => {
      clearTimeout(timer);
      el.removeEventListener("scroll", checkScroll);
      window.removeEventListener("resize", checkScroll);
    };
  }, [checkScroll, loading, activeSeason]);

  // Scroll current episode into center view when picker opens or season changes
  useEffect(() => {
    if (loading || !open) return;
    const el = scrollRef.current;
    if (!el) return;
    const currentEl = el.querySelector(
      '[data-current="true"]',
    ) as HTMLElement | null;
    if (!currentEl) return;
    const scrollLeft =
      currentEl.offsetLeft - el.clientWidth / 2 + currentEl.offsetWidth / 2;
    el.scrollLeft = Math.max(0, scrollLeft);
    checkScroll();
  }, [loading, open, activeSeason, checkScroll]);

  const scroll = (direction: "left" | "right") => {
    const el = scrollRef.current;
    if (el) {
      el.scrollBy({
        left:
          direction === "left" ? -el.clientWidth * 0.8 : el.clientWidth * 0.8,
        behavior: "smooth",
      });
    }
  };

  // Close on click outside
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        panelRef.current?.contains(target) ||
        toggleButtonRef?.current?.contains(target)
      )
        return;
      onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open, onClose, toggleButtonRef]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  const currentSeasonData = seasons.find(
    (s) => s.season_number === activeSeason,
  );

  const handleEpisodeClick = useCallback(
    (mediaId: number) => {
      if (mediaId === currentMediaId) {
        onClose();
        return;
      }
      onEpisodeSelect(mediaId);
    },
    [currentMediaId, onClose, onEpisodeSelect],
  );

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          ref={panelRef}
          className="absolute top-0 left-0 right-0 z-30"
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -20, opacity: 0 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
        >
          <div
            className="mx-4 mt-4 rounded-2xl shadow-[0_8px_32px_rgba(0,0,0,0.5)] backdrop-blur-xs"
            style={{ backgroundColor: "rgba(10, 10, 10, 0.6)" }}
          >
            {/* Header: season dropdown (left) + scroll chevrons (right) */}
            <div className="flex items-center justify-between px-4 py-2.5">
              {/* Season dropdown */}
              <div className="relative">
                <button
                  onClick={() => setDropdownOpen((v) => !v)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[13px] font-medium text-white hover:bg-white/[0.08] transition-colors"
                >
                  Stagione {activeSeason}
                  <ChevronDown
                    className={cn(
                      "h-4 w-4 text-zinc-400 transition-transform",
                      dropdownOpen && "rotate-180",
                    )}
                  />
                </button>

                {dropdownOpen && (
                  <div
                    className="absolute top-full left-0 mt-1 min-w-[160px] rounded-xl overflow-hidden shadow-lg backdrop-blur-xl z-40"
                    style={{ backgroundColor: "rgba(20, 20, 20, 0.95)" }}
                  >
                    {seasons.map((season) => (
                      <button
                        key={season.season_number}
                        onClick={() => {
                          setActiveSeason(season.season_number);
                          setDropdownOpen(false);
                        }}
                        className={cn(
                          "flex items-center w-full px-4 py-2.5 text-[13px] transition-colors",
                          activeSeason === season.season_number
                            ? "text-plex-orange bg-plex-orange/10"
                            : "text-white hover:bg-white/[0.08]",
                        )}
                      >
                        Stagione {season.season_number}
                        <span className="ml-auto text-[11px] text-zinc-500">
                          {season.episodes_count} ep
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Scroll chevrons (always rendered, disabled when can't scroll) */}
              <div className="flex items-center gap-1">
                <button
                  onClick={() => scroll("left")}
                  disabled={!canScrollLeft}
                  className={cn(
                    "w-8 h-8 flex items-center justify-center rounded-full transition-colors",
                    canScrollLeft
                      ? "hover:bg-white/10 text-zinc-400"
                      : "text-white/10 cursor-default",
                  )}
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <button
                  onClick={() => scroll("right")}
                  disabled={!canScrollRight}
                  className={cn(
                    "w-8 h-8 flex items-center justify-center rounded-full transition-colors",
                    canScrollRight
                      ? "hover:bg-white/10 text-zinc-400"
                      : "text-white/10 cursor-default",
                  )}
                >
                  <ChevronRight className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Horizontal episode strip with edge fade masks */}
            <div className="relative">
              {/* Left fade mask (visible only when scrolled) */}
              <div
                className="absolute left-0 top-0 bottom-0 w-16 z-10 pointer-events-none rounded-bl-2xl transition-opacity duration-200"
                style={{
                  opacity: canScrollLeft ? 1 : 0,
                  background:
                    "linear-gradient(to right, rgba(10,10,10,1) 0%, rgba(10,10,10,0.6) 40%, transparent 100%)",
                }}
              />
              {/* Right fade mask (visible only when more content) */}
              <div
                className="absolute right-0 top-0 bottom-0 w-16 z-10 pointer-events-none rounded-br-2xl transition-opacity duration-200"
                style={{
                  opacity: canScrollRight ? 1 : 0,
                  background:
                    "linear-gradient(to left, rgba(10,10,10,1) 0%, rgba(10,10,10,0.6) 40%, transparent 100%)",
                }}
              />

              <div
                ref={scrollRef}
                className="flex gap-3.5 px-5 pb-4 pt-1 overflow-x-auto scrollbar-hide"
                style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}
              >
                {loading ? (
                  <div className="flex items-center justify-center w-full py-8">
                    <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-plex-orange" />
                  </div>
                ) : !currentSeasonData?.episodes.length ? (
                  <div className="w-full text-center py-8 text-zinc-500 text-sm">
                    Nessun episodio
                  </div>
                ) : (
                  currentSeasonData.episodes.map((ep) => {
                    const isCurrent = ep.id === currentMediaId;
                    const progress = ep.watch_progress;
                    const progressPct = progress?.progress_percent ?? 0;
                    const isCompleted = progress?.is_completed ?? false;
                    const thumb = getTmdbImageUrl(ep.still_path, "w500");

                    return (
                      <EpisodeThumb
                        key={ep.id}
                        episodeNumber={ep.episode_number}
                        title={cleanEpisodeTitle(ep.title)}
                        duration={formatDuration(ep.duration_seconds)}
                        thumbnailUrl={thumb}
                        progressPercent={progressPct}
                        isCompleted={isCompleted}
                        isCurrent={isCurrent}
                        onClick={() => handleEpisodeClick(ep.id)}
                      />
                    );
                  })
                )}
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function EpisodeThumb({
  episodeNumber,
  title,
  duration,
  thumbnailUrl,
  progressPercent,
  isCompleted,
  isCurrent,
  onClick,
}: {
  episodeNumber: number | null;
  title: string;
  duration: string | null;
  thumbnailUrl: string | null;
  progressPercent: number;
  isCompleted: boolean;
  isCurrent: boolean;
  onClick: () => void;
}) {
  return (
    <button
      data-current={isCurrent ? "true" : undefined}
      onClick={onClick}
      className={cn(
        "flex-shrink-0 w-80 rounded-xl overflow-hidden transition-all group cursor-pointer",
        isCurrent && "ring-2 ring-plex-orange",
      )}
    >
      <div className="relative aspect-video bg-zinc-800 rounded-xl overflow-hidden">
        {thumbnailUrl ? (
          <Image
            src={thumbnailUrl}
            alt=""
            fill
            sizes="320px"
            className="object-cover"
            unoptimized
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-zinc-600 text-sm font-medium">
            E{episodeNumber}
          </div>
        )}

        {/* Watched badge */}
        {isCompleted && (
          <div className="absolute top-2 right-2 w-6 h-6 rounded-full bg-plex-orange flex items-center justify-center z-10">
            <Check className="h-3.5 w-3.5 text-black" strokeWidth={3} />
          </div>
        )}

        {/* Bottom gradient + info (same style as EpisodeCard) */}
        <div
          className="absolute inset-x-0 bottom-0 px-3 pb-2 pt-10 flex flex-col gap-0.5 text-left"
          style={{
            background:
              "linear-gradient(to top, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.55) 55%, transparent 100%)",
          }}
        >
          <h3 className="text-[13px] font-semibold text-white truncate leading-tight">
            {title}
          </h3>
          <div className="flex items-center gap-1.5 text-[11px] text-white/60">
            <span>Episodio {episodeNumber}</span>
            {duration && (
              <>
                <span className="text-white/30">·</span>
                <span>{duration}</span>
              </>
            )}
          </div>
        </div>

        {/* Play hover overlay */}
        {!isCurrent && (
          <div className="absolute inset-0 bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
            <div className="w-10 h-10 rounded-full bg-black/50 backdrop-blur-sm flex items-center justify-center">
              <Play className="h-5 w-5 text-white fill-white ml-0.5" />
            </div>
          </div>
        )}

        {/* Now playing indicator */}
        {isCurrent && (
          <div className="absolute inset-0 bg-black/20 flex items-center justify-center">
            <div className="flex gap-[3px] items-end h-4">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="w-[3px] bg-plex-orange rounded-full animate-pulse"
                  style={{
                    height: `${8 + i * 4}px`,
                    animationDelay: `${i * 150}ms`,
                  }}
                />
              ))}
            </div>
          </div>
        )}

        {/* Progress bar */}
        {progressPercent > 0 && !isCompleted && (
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-white/20 z-10">
            <div
              className="h-full bg-plex-orange"
              style={{ width: `${Math.min(progressPercent, 100)}%` }}
            />
          </div>
        )}
      </div>
    </button>
  );
}
