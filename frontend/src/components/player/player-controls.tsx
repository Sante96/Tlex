"use client";

import { RotateCcw, RotateCw, PictureInPicture2 } from "lucide-react";
import { useTranslations } from "next-intl";
import {
  AnimatedPlayPause,
  AnimatedFullscreen,
  AnimatedBack,
  AnimatedEpisodes,
} from "./animated-icons";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { formatTime } from "@/lib/format";
import { PlayerSettingsDropdown } from "./player-settings";
import { VideoSeekbar } from "./video-seekbar";
import { VolumeSlider } from "./volume-slider";
import { ClientRing } from "./client-ring";
import type { StreamClients } from "@/hooks/player/use-stream-clients";
import type { Chapter, MediaStream } from "@/lib/api";

function PlayerTooltip({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="relative group">
      {children}
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2.5 py-1.5 bg-zinc-800 text-white text-xs rounded-lg whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-150 pointer-events-none">
        {label}
      </div>
    </div>
  );
}

interface PlayerControlsProps {
  visible: boolean;
  isPlaying: boolean;
  isLoading: boolean;
  currentTime: number;
  duration: number;
  chapters?: Chapter[] | null;
  chapterWord?: "chapter" | "song";
  /** The Telegram clients streaming this title (the ring next to the volume) */
  clients?: StreamClients | null;
  volume: number;
  isMuted: boolean;
  isFullscreen: boolean;
  title: string;
  subtitle?: string;
  audioTracks: MediaStream[];
  subtitleTracks: MediaStream[];
  selectedAudio: number;
  selectedSubtitle: number | null;
  subtitleOffset: number;
  onTogglePlay: () => void;
  onSeek: (time: number) => void;
  onVolumeChange: (value: number) => void;
  onToggleMute: () => void;
  onToggleFullscreen: () => void;
  /** False where the page can't go fullscreen (iPhone Safari): no button */
  canFullscreen?: boolean;
  /** A click or tap on the empty middle of the picture */
  onSurfaceClick?: () => void;
  onTogglePiP?: () => void;
  onBack: () => void;
  isTV?: boolean;
  onAudioChange: (index: number) => void;
  onSubtitleChange: (index: number | null) => void;
  onSubtitleOffsetChange: (offset: number) => void;
  onSkip: (seconds: number) => void;
  onActivity?: () => void;
  onSettingsOpenChange?: (open: boolean) => void;
  hasEpisodes?: boolean;
  episodePickerOpen?: boolean;
  onToggleEpisodes?: () => void;
  episodesButtonRef?: React.RefObject<HTMLButtonElement | null>;
}

export function PlayerControls({
  visible,
  isPlaying,
  isLoading,
  currentTime,
  duration,
  chapters,
  chapterWord,
  clients,
  volume,
  isMuted,
  isFullscreen,
  title,
  subtitle,
  audioTracks,
  subtitleTracks,
  selectedAudio,
  selectedSubtitle,
  subtitleOffset,
  onTogglePlay,
  onSeek,
  onVolumeChange,
  onToggleMute,
  onToggleFullscreen,
  canFullscreen = true,
  onSurfaceClick,
  onTogglePiP,
  onBack,
  onAudioChange,
  onSubtitleChange,
  onSubtitleOffsetChange,
  onSkip,
  onActivity,
  onSettingsOpenChange,
  isTV,
  hasEpisodes,
  episodePickerOpen,
  onToggleEpisodes,
  episodesButtonRef,
}: PlayerControlsProps) {
  const t = useTranslations();
  // Each part fades by itself: a fade on the whole overlay turned off the play button's
  // blur until it ended (an ancestor's opacity hides what's behind from backdrop-filter)
  const shown = visible ? "opacity-100" : "opacity-0";
  const fade = cn("transition-opacity duration-300", shown);
  return (
    <div
      className={cn(
        "absolute inset-0 flex flex-col z-20",
        !visible && "pointer-events-none",
      )}
    >
      {/* Top bar */}
      <div
        className={cn(
          "flex items-center p-4 bg-linear-to-b from-black/80 to-transparent",
          fade,
        )}
      >
        <button
          onClick={onBack}
          aria-label={t("common.back")}
          className="p-2 rounded-full hover:bg-white/10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80"
        >
          <AnimatedBack className="text-white" />
        </button>
        <div className="flex-1 min-w-0 text-center px-4">
          <h1 className="text-white font-medium text-base truncate drop-shadow-sm">
            {title}
          </h1>
          {subtitle && (
            <p className="text-white/60 text-sm truncate">{subtitle}</p>
          )}
        </div>
        <div className="w-10" />
      </div>

      {/* Center — play/pause + skip (Plex style with blur). Its empty space is the
          picture: it took every click while the controls showed */}
      <div
        className="flex-1 flex items-center justify-center"
        onClick={(e) => e.target === e.currentTarget && onSurfaceClick?.()}
      >
        <div className="flex items-center gap-8">
          {/* Skip backward */}
          <button
            onClick={() => onSkip(-10)}
            aria-label={t("player.back")}
            className={cn(
              "p-3 hover:bg-white/20 rounded-full transition-all hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80",
              shown,
            )}
          >
            <div className="relative drop-shadow-lg">
              <RotateCcw
                className={cn("h-8 w-8 text-white", isLoading && "opacity-50")}
              />
              <span
                className={cn(
                  "absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white mt-0.5",
                  isLoading && "opacity-50",
                )}
              >
                10
              </span>
            </div>
          </button>

          {/* Big play/pause button with integrated loader */}
          <div className="relative">
            {isLoading && (
              <motion.div
                className="absolute -inset-2 rounded-full aspect-square"
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                style={{
                  border: "4px solid rgba(255,255,255,0.2)",
                  borderTopColor: "#e5a00d",
                }}
              />
            )}
            <button
              onClick={onTogglePlay}
              aria-label={isPlaying ? t("player.pause") : t("player.play")}
              className={cn(
                "relative p-5 rounded-full transition-all backdrop-blur-md shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80",
                shown,
                isLoading
                  ? "bg-black/60"
                  : "bg-black/30 hover:bg-black/40 hover:scale-105",
              )}
            >
              <AnimatedPlayPause
                isPlaying={isPlaying}
                size={48}
                className={cn(
                  "drop-shadow-lg",
                  isLoading ? "text-white/50" : "text-white",
                )}
              />
            </button>
          </div>

          {/* Skip forward */}
          <button
            onClick={() => onSkip(10)}
            aria-label={t("player.forward")}
            className={cn(
              "p-3 hover:bg-white/20 rounded-full transition-all hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80",
              shown,
            )}
          >
            <div className="relative drop-shadow-lg">
              <RotateCw
                className={cn("h-8 w-8 text-white", isLoading && "opacity-50")}
              />
              <span
                className={cn(
                  "absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white mt-0.5",
                  isLoading && "opacity-50",
                )}
              >
                10
              </span>
            </div>
          </button>
        </div>
      </div>

      {/* Bottom controls */}
      <div
        className={cn(
          "bg-linear-to-t from-black/80 to-transparent px-4 pb-3 pt-10 space-y-1",
          fade,
        )}
      >
        <VideoSeekbar
          currentTime={currentTime}
          duration={duration}
          chapters={chapters}
          chapterWord={chapterWord}
          onSeek={onSeek}
          onActivity={onActivity}
        />

        {/* Bottom row */}
        <div className="flex items-center justify-between">
          {/* Left — Time + Volume */}
          <div className="flex items-center">
            <div className="text-[13px] text-white/90 font-medium tabular-nums px-2 py-2 rounded-full hover:bg-white/10 transition-colors cursor-default">
              {formatTime(currentTime)} / {formatTime(duration)}
            </div>
            {!isTV && <div className="hidden md:flex">
              <VolumeSlider
                volume={volume}
                isMuted={isMuted}
                onVolumeChange={onVolumeChange}
                onToggleMute={onToggleMute}
              />
            </div>}
            {clients && clients.total > 0 && (
              <div className="px-2 py-1.5">
                {isTV ? (
                  <ClientRing {...clients} />
                ) : (
                  <PlayerTooltip
                    label={t("player.clients", { inUse: clients.inUse, total: clients.total })}
                  >
                    <ClientRing {...clients} />
                  </PlayerTooltip>
                )}
              </div>
            )}
          </div>

          {/* Right — Controls */}
          <div className="flex items-center gap-0.5">
            {hasEpisodes && (
              <PlayerTooltip label={t("player.episodes")}>
                <button
                  ref={episodesButtonRef}
                  onClick={onToggleEpisodes}
                  aria-label={t("player.episodes")}
                  aria-expanded={!!episodePickerOpen}
                  className="p-2 rounded-full hover:bg-white/10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80"
                >
                  <AnimatedEpisodes
                    isOpen={!!episodePickerOpen}
                    className="text-white"
                  />
                </button>
              </PlayerTooltip>
            )}

            <PlayerSettingsDropdown
              audioTracks={audioTracks}
              subtitleTracks={subtitleTracks}
              selectedAudio={selectedAudio}
              selectedSubtitle={selectedSubtitle}
              subtitleOffset={subtitleOffset}
              onAudioChange={onAudioChange}
              onSubtitleChange={onSubtitleChange}
              onSubtitleOffsetChange={onSubtitleOffsetChange}
              onOpenChange={onSettingsOpenChange}
            />

            {onTogglePiP && (
              <PlayerTooltip label={t("player.pip")}>
                <button
                  onClick={onTogglePiP}
                  aria-label={t("player.pip")}
                  className="hidden md:flex p-2 rounded-full hover:bg-white/10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80"
                >
                  <PictureInPicture2 className="h-5 w-5 text-white" />
                </button>
              </PlayerTooltip>
            )}

            {!isTV && canFullscreen && (
              <PlayerTooltip
                label={
                  isFullscreen
                    ? t("player.exitFullscreen")
                    : t("player.fullscreen")
                }
              >
                <button
                  onClick={onToggleFullscreen}
                  aria-label={
                    isFullscreen
                      ? t("player.exitFullscreen")
                      : t("player.fullscreen")
                  }
                  className="p-2 rounded-full hover:bg-white/10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80"
                >
                  <AnimatedFullscreen
                    isFullscreen={isFullscreen}
                    className="text-white"
                  />
                </button>
              </PlayerTooltip>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
