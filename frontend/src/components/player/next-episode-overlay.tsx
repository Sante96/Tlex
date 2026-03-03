"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useTranslations } from "next-intl";
import Image from "next/image";
import { AnimatePresence, motion } from "framer-motion";
import { Play, X } from "lucide-react";
import { DSButton } from "@/components/ds/button";
import { type NextEpisode } from "@/lib/api";
import {
  getTmdbImageUrl,
  formatDuration,
  cleanEpisodeTitle,
} from "@/lib/format";

const COUNTDOWN_SECONDS = 30;

function getAutoplayPref(): boolean {
  if (typeof window === "undefined") return true;
  return localStorage.getItem("pref_autoplay_next") !== "false";
}

interface NextEpisodeOverlayProps {
  nextEpisode: NextEpisode | null;
  visible: boolean;
  isPlaying: boolean;
  isEnded: boolean;
  onPlay: () => void;
  onCancel: () => void;
}

export function NextEpisodeOverlay({
  nextEpisode,
  visible,
  isPlaying,
  isEnded,
  onPlay,
  onCancel,
}: NextEpisodeOverlayProps) {
  const t = useTranslations();
  const [countdown, setCountdown] = useState(COUNTDOWN_SECONDS);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onPlayRef = useRef(onPlay);
  useEffect(() => {
    onPlayRef.current = onPlay;
  }, [onPlay]);
  const isPlayingRef = useRef(isPlaying);
  useEffect(() => {
    isPlayingRef.current = isPlaying;
  }, [isPlaying]);
  const isEndedRef = useRef(isEnded);
  useEffect(() => {
    isEndedRef.current = isEnded;
  }, [isEnded]);

  // Countdown timer — uses interval callback for all state updates
  useEffect(() => {
    if (!visible || !nextEpisode) return;
    if (!getAutoplayPref()) return; // autoplay disabled by user preference

    let remaining = COUNTDOWN_SECONDS;

    // First tick immediately to show the initial countdown
    const tick = () => {
      // Hold countdown if user paused, but NOT if video has ended naturally
      if (!isPlayingRef.current && !isEndedRef.current) return;
      setCountdown(remaining);
      if (remaining <= 0) {
        clearInterval(intervalRef.current!);
        onPlayRef.current();
        return;
      }
      remaining -= 1;
    };

    // Show initial value via first scheduled tick (0ms delay)
    const initTimer = setTimeout(tick, 0);
    intervalRef.current = setInterval(tick, 1000);

    return () => {
      clearTimeout(initTimer);
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [visible, nextEpisode]);

  const handleCancel = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    onCancel();
  }, [onCancel]);

  if (!nextEpisode) return null;

  const thumbUrl = getTmdbImageUrl(nextEpisode.still_path, "original");
  const title = cleanEpisodeTitle(nextEpisode.title);
  const duration = formatDuration(nextEpisode.duration_seconds);
  const epLabel = `S${nextEpisode.season_number || 1} · E${nextEpisode.episode_number || 1}`;

  // Countdown progress (1 = full, 0 = done)
  const progress = countdown / COUNTDOWN_SECONDS;

  const ringR = 28;
  const ringCirc = 2 * Math.PI * ringR;

  return (
    <AnimatePresence>
      {visible && (
        <>
          {/* ── Desktop: right panel ── */}
          <motion.div
            className="hidden md:flex absolute right-0 top-0 bottom-0 w-[38%] z-30 flex-col items-center justify-center gap-5 px-8"
            style={{ backgroundColor: "#0a0a0a" }}
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: 0.45, ease: [0.4, 0, 0.2, 1] }}
          >
            <div className="absolute left-0 top-0 bottom-0 w-px bg-white/5" />
            <button
              onClick={handleCancel}
              className="absolute top-4 right-4 p-2 rounded-full bg-white/5 hover:bg-white/10 transition-colors"
            >
              <X className="h-4 w-4 text-white/60" />
            </button>
            <p className="text-[11px] font-medium tracking-widest uppercase text-zinc-500">
              {t("player.nextEpisode")}
            </p>
            <button
              onClick={onPlay}
              className="w-full rounded-xl overflow-hidden aspect-video relative group"
            >
              {thumbUrl ? (
                <Image
                  src={thumbUrl}
                  alt={title}
                  fill
                  sizes="40vw"
                  className="object-cover"
                  unoptimized
                />
              ) : (
                <div className="w-full h-full bg-zinc-800 flex items-center justify-center text-zinc-600 text-sm">
                  {epLabel}
                </div>
              )}
              <div className="absolute inset-0 bg-black/20 group-hover:bg-black/40 transition-colors flex items-center justify-center">
                <div className="w-12 h-12 rounded-full bg-black/50 backdrop-blur-sm flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                  <Play className="h-6 w-6 text-white fill-white ml-0.5" />
                </div>
              </div>
            </button>
            <div className="w-full">
              <p className="text-[13px] text-zinc-400">{epLabel}</p>
              <h3 className="text-[16px] font-semibold text-white mt-0.5 line-clamp-2">
                {title}
              </h3>
              {duration && (
                <p className="text-[12px] text-zinc-500 mt-0.5">{duration}</p>
              )}
            </div>
            <button
              onClick={onPlay}
              className="relative flex items-center justify-center w-[72px] h-[72px] group"
            >
              <svg
                width="72"
                height="72"
                className="-rotate-90 absolute inset-0"
              >
                <circle
                  cx="36"
                  cy="36"
                  r={ringR}
                  fill="none"
                  stroke="rgba(255,255,255,0.08)"
                  strokeWidth="3"
                />
                <circle
                  cx="36"
                  cy="36"
                  r={ringR}
                  fill="none"
                  stroke="#e5a00d"
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeDasharray={ringCirc}
                  strokeDashoffset={ringCirc * (1 - progress)}
                  style={{ transition: "stroke-dashoffset 1s linear" }}
                />
              </svg>
              <span className="text-[22px] font-bold text-white group-hover:scale-110 transition-transform">
                {countdown}
              </span>
            </button>
            <DSButton
              variant="primary"
              icon={<Play className="h-4 w-4 fill-black" />}
              onClick={onPlay}
              className="w-full"
            >
              {t("player.playNow")}
            </DSButton>
          </motion.div>

          {/* ── Mobile: bottom sheet ── */}
          <motion.div
            className="md:hidden absolute bottom-0 left-0 right-0 z-30 px-4 pb-8 pt-6"
            style={{
              background:
                "linear-gradient(to top, rgba(10,10,10,0.98) 60%, transparent)",
            }}
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
          >
            {/* Label row */}
            <div className="flex items-center justify-between mb-3">
              <p className="text-[10px] font-semibold tracking-widest uppercase text-zinc-500">
                Prossimo episodio
              </p>
              <button
                onClick={handleCancel}
                className="p-1.5 rounded-full bg-white/5"
              >
                <X className="h-3.5 w-3.5 text-white/50" />
              </button>
            </div>

            {/* Content row */}
            <div className="flex items-center gap-3">
              {/* Thumbnail */}
              <button
                onClick={onPlay}
                className="shrink-0 w-32 rounded-lg overflow-hidden aspect-video relative"
              >
                {thumbUrl ? (
                  <Image
                    src={thumbUrl}
                    alt={title}
                    fill
                    sizes="128px"
                    className="object-cover"
                    unoptimized
                  />
                ) : (
                  <div className="w-full h-full bg-zinc-800 flex items-center justify-center text-zinc-600 text-xs">
                    {epLabel}
                  </div>
                )}
              </button>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <p className="text-[11px] text-zinc-400 mb-0.5">{epLabel}</p>
                <h3 className="text-[15px] font-semibold text-white leading-tight line-clamp-2">
                  {title}
                </h3>
                {duration && (
                  <p className="text-[11px] text-zinc-500 mt-0.5">{duration}</p>
                )}
              </div>

              {/* Countdown ring + play */}
              <div className="flex flex-col items-center gap-2 shrink-0">
                {getAutoplayPref() && (
                  <button
                    onClick={onPlay}
                    className="relative flex items-center justify-center w-11 h-11"
                  >
                    <svg
                      width="44"
                      height="44"
                      className="-rotate-90 absolute inset-0"
                    >
                      <circle
                        cx="22"
                        cy="22"
                        r={18}
                        fill="none"
                        stroke="rgba(255,255,255,0.08)"
                        strokeWidth="2.5"
                      />
                      <circle
                        cx="22"
                        cy="22"
                        r={18}
                        fill="none"
                        stroke="#e5a00d"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeDasharray={2 * Math.PI * 18}
                        strokeDashoffset={2 * Math.PI * 18 * (1 - progress)}
                        style={{ transition: "stroke-dashoffset 1s linear" }}
                      />
                    </svg>
                    <span className="text-[12px] font-bold text-white">
                      {countdown}
                    </span>
                  </button>
                )}
                <button
                  onClick={onPlay}
                  className="h-9 px-3 rounded-lg bg-[#e5a00d] text-black text-xs font-semibold flex items-center gap-1"
                >
                  <Play className="h-3 w-3 fill-black" />
                  {t("media.play")}
                </button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
