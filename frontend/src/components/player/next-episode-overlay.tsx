"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import Image from "next/image";
import { AnimatePresence, motion } from "framer-motion";
import { Play } from "lucide-react";
import { type MediaItem, type NextEpisode } from "@/lib/api";
import { useProfile } from "@/contexts/profile-context";
import { cleanEpisodeTitle, getTmdbImageUrl } from "@/lib/format";
import { useIsLandscape } from "@/lib/breakpoints";
import { useIsTV } from "@/hooks/use-platform";

const COUNTDOWN_SECONDS = 15;

// The two buttons' shared look
const BUTTON =
  "h-10 sm:h-11 tv-1080:h-14 px-4 sm:px-6 rounded-md whitespace-nowrap text-sm sm:text-base tv-1080:text-xl font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-black";
const CREDITS_BUTTON = "bg-black/40 text-white border border-white/60 hover:bg-white/15 backdrop-blur-sm";

interface NextEpisodeOverlayProps {
  nextEpisode: NextEpisode | null;
  /** After a film: films of the library (when there's no next episode) */
  recommendations?: MediaItem[];
  onPick?: (mediaId: number) => void;
  visible: boolean;
  isPlaying: boolean;
  isEnded: boolean;
  onPlay: () => void;
  onCancel: () => void;
}

/**
 * Up next, over the credits, Netflix's way: its title and two buttons in the bottom right
 * corner, over its picture (UpNextBackdrop, under the shrunken video). With autoplay on (the profile's Settings), the next
 * episode's button fills over the countdown and plays it when full; paused, it waits.
 * "Watch the credits" stays.
 */
export function NextEpisodeOverlay({
  nextEpisode,
  recommendations = [],
  onPick,
  visible,
  ...card
}: NextEpisodeOverlayProps) {
  return (
    <AnimatePresence>
      {visible && nextEpisode ? (
        <UpNextCard key="up-next" nextEpisode={nextEpisode} {...card} />
      ) : visible && recommendations.length > 0 && onPick ? (
        <RecommendationsCard
          key="recommendations"
          recommendations={recommendations}
          onPick={onPick}
          onCancel={card.onCancel}
        />
      ) : null}
    </AnimatePresence>
  );
}

/** Mounted when it shows: its countdown starts full */
function UpNextCard({
  nextEpisode,
  isPlaying,
  isEnded,
  onPlay,
  onCancel,
}: Omit<NextEpisodeOverlayProps, "visible" | "recommendations" | "onPick"> & {
  nextEpisode: NextEpisode;
}) {
  const t = useTranslations();
  const landscape = useIsLandscape();
  // The TV remote starts on it; not with a keyboard, where Space plays and pauses
  const isTV = useIsTV();
  const autoplay = useProfile().profile?.preferences?.autoplay_next !== false;
  const [countdown, setCountdown] = useState(COUNTDOWN_SECONDS);
  const onPlayRef = useRef(onPlay);
  const runningRef = useRef(isPlaying || isEnded);
  useEffect(() => {
    onPlayRef.current = onPlay;
    // Held while paused, but not once the video has ended by itself
    runningRef.current = isPlaying || isEnded;
  }, [onPlay, isPlaying, isEnded]);

  useEffect(() => {
    if (!autoplay) return;
    let remaining = COUNTDOWN_SECONDS;
    const timer = setInterval(() => {
      if (!runningRef.current) return;
      remaining -= 1;
      setCountdown(remaining);
      if (remaining <= 0) {
        clearInterval(timer);
        onPlayRef.current();
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [autoplay]);

  const filled = ((COUNTDOWN_SECONDS - countdown) / COUNTDOWN_SECONDS) * 100;

  const title = `S${nextEpisode.season_number || 1} · E${nextEpisode.episode_number || 1} · ${cleanEpisodeTitle(nextEpisode.title)}`;
  // Upright: its picture in the card, under the video that moved up (no backdrop)
  const still = landscape
    ? null
    : getTmdbImageUrl(nextEpisode.still_path ?? nextEpisode.backdrop_path, "w780");
  const buttons = (
    <div className="flex items-center gap-2 sm:gap-3">
      <button
        type="button"
        onClick={onCancel}
        className={`${BUTTON} ${landscape ? "" : "flex-1 px-2"} ${CREDITS_BUTTON}`}
      >
        {t("player.watchCredits")}
      </button>
      {/* Orange, filling darker over the countdown */}
      <button
        type="button"
        autoFocus={isTV}
        onClick={onPlay}
        className={`${BUTTON} ${landscape ? "" : "flex-1 px-2"} relative overflow-hidden bg-plex-orange text-black hover:bg-[#f0b429]`}
      >
        {autoplay && (
          <span
            aria-hidden
            className="absolute inset-y-0 left-0 bg-[#b8860b]"
            style={{ width: `${filled}%`, transition: "width 1s linear" }}
          />
        )}
        <span className="relative flex items-center justify-center gap-2">
          <Play className="h-4 w-4 tv-1080:h-6 tv-1080:w-6 fill-current" />
          {t("player.nextEpisode")}
        </span>
      </button>
    </div>
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 16 }}
      transition={{ duration: 0.3, delay: 0.2 }}
      role="group"
      aria-label={t("player.nextEpisode")}
      className={
        landscape
          ? // Above the control bar, over the next episode's picture
            "absolute z-30 right-3 sm:right-8 bottom-24 sm:bottom-28 flex flex-col items-end gap-3 tv-1080:gap-4 text-right"
          : // Right under the video, moved up to 7% from the top (a 16:9 picture, full width)
            "absolute z-30 inset-x-4 top-[calc(7%+56.25vw+2rem)] mx-auto max-w-md flex flex-col gap-3"
      }
    >
      {still && (
        <div className="relative aspect-video rounded-xl overflow-hidden bg-zinc-900">
          <Image src={still} alt="" fill sizes="28rem" className="object-cover" unoptimized />
        </div>
      )}
      <div className={landscape ? "text-shadow" : ""}>
        <p className="text-xs sm:text-sm tv-1080:text-lg text-white/75">{t("player.nextEpisode")}</p>
        <p className="text-base sm:text-xl tv-1080:text-3xl font-bold text-white">{title}</p>
      </div>
      {buttons}
    </motion.div>
  );
}

/**
 * Up next's picture over the whole player, under the video: there as the video shrinks
 * into the corner (no black in between). Only sideways: upright, the video moves up and
 * the card below holds the picture.
 */
export function UpNextBackdrop({ image, visible }: { image: string | null; visible: boolean }) {
  return (
    <AnimatePresence>
      {visible && image && (
        <motion.div
          key="up-next-backdrop"
          aria-hidden
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.5 }}
          className="absolute inset-0 pointer-events-none"
        >
          <Image src={image} alt="" fill sizes="100vw" className="object-cover" unoptimized />
          {/* Dark low down and on the left: the title, the buttons and the controls read on it */}
          <div className="absolute inset-0 bg-linear-to-t from-black/85 via-black/20 to-black/30" />
          <div className="absolute inset-0 bg-linear-to-r from-black/60 via-transparent to-transparent" />
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/**
 * After a film: films of the library (none plays by itself), and back to the credits.
 * Sideways two or three cards beside the shrunken video; upright a row under it.
 */
function RecommendationsCard({
  recommendations,
  onPick,
  onCancel,
}: {
  recommendations: MediaItem[];
  onPick: (mediaId: number) => void;
  onCancel: () => void;
}) {
  const t = useTranslations();
  const landscape = useIsLandscape();
  const isTV = useIsTV();
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 16 }}
      transition={{ duration: 0.3, delay: 0.2 }}
      role="group"
      aria-label={t("player.youMightLike")}
      className={
        landscape
          ? "absolute z-30 right-3 sm:right-8 bottom-24 sm:bottom-28 flex flex-col items-end gap-3 tv-1080:gap-4"
          : "absolute z-30 inset-x-4 top-[calc(7%+56.25vw+2rem)] mx-auto max-w-md flex flex-col gap-3"
      }
    >
      <p className="text-sm sm:text-base tv-1080:text-2xl font-semibold text-white text-shadow">
        {t("player.youMightLike")}
      </p>
      <div
        className={
          landscape
            ? // Two beside the video until lg, three from there
              "flex gap-3 [&>*:nth-child(n+4)]:hidden max-lg:[&>*:nth-child(3)]:hidden"
            : "flex gap-3 overflow-x-auto scrollbar-hide -mx-4 px-4"
        }
      >
        {recommendations.map((film, i) => {
          const picture = getTmdbImageUrl(film.backdrop_path ?? film.poster_path, "w780");
          return (
            <button
              key={film.id}
              type="button"
              autoFocus={isTV && i === 0}
              onClick={() => onPick(film.id)}
              className="group shrink-0 w-36 lg:w-40 xl:w-52 tv-1080:w-64 text-left focus-visible:outline-none"
            >
              <span className="relative block aspect-video rounded-lg overflow-hidden bg-zinc-900 ring-2 ring-white/10 group-hover:ring-white/50 group-focus-visible:ring-plex-orange transition-shadow">
                {picture && (
                  <Image src={picture} alt="" fill sizes="16rem" className="object-cover" unoptimized />
                )}
                <span className="absolute inset-0 flex items-center justify-center bg-black/0 group-hover:bg-black/30 transition-colors">
                  <Play className="h-7 w-7 text-white fill-white opacity-0 group-hover:opacity-100 transition-opacity" />
                </span>
              </span>
              <span className="mt-1.5 block text-sm tv-1080:text-lg font-medium text-white truncate text-shadow">
                {film.title}
              </span>
            </button>
          );
        })}
      </div>
      <button type="button" onClick={onCancel} className={`${BUTTON} ${CREDITS_BUTTON}`}>
        {t("player.watchCredits")}
      </button>
    </motion.div>
  );
}
