"use client";

import { RotateCcw, RotateCw } from "lucide-react";
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
import type { MediaStream } from "@/lib/api";

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
  onBack: () => void;
  onAudioChange: (index: number) => void;
  onSubtitleChange: (index: number | null) => void;
  onSubtitleOffsetChange: (offset: number) => void;
  onSkip: (seconds: number) => void;
  onSeekStart?: () => void;
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
  onBack,
  onAudioChange,
  onSubtitleChange,
  onSubtitleOffsetChange,
  onSkip,
  onSeekStart,
  onSettingsOpenChange,
  hasEpisodes,
  episodePickerOpen,
  onToggleEpisodes,
  episodesButtonRef,
}: PlayerControlsProps) {
  return (
    <div
      className={cn(
        "absolute inset-0 flex flex-col transition-opacity duration-300 z-20",
        visible ? "opacity-100" : "opacity-0 pointer-events-none",
      )}
    >
      {/* Top bar */}
      <div className="flex items-center p-4 bg-gradient-to-b from-black/80 to-transparent">
        <button
          onClick={onBack}
          className="p-2 rounded-full hover:bg-white/10 transition-colors"
        >
          <AnimatedBack className="text-white" />
        </button>
        <div className="flex-1 text-center px-4">
          <h1 className="text-white font-medium text-base truncate drop-shadow-sm">
            {title}
          </h1>
          {subtitle && (
            <p className="text-white/60 text-sm truncate">{subtitle}</p>
          )}
        </div>
        <div className="w-10" />
      </div>

      {/* Center — play/pause + skip (Plex style with blur) */}
      <div className="flex-1 flex items-center justify-center">
        <div className="flex items-center gap-8">
          {/* Skip backward */}
          <button
            onClick={() => onSkip(-10)}
            className="p-3 hover:bg-white/20 rounded-full transition-all hover:scale-110"
            disabled={isLoading}
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
              disabled={isLoading}
              className={cn(
                "relative p-5 rounded-full transition-all backdrop-blur-md shadow-lg",
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
            className="p-3 hover:bg-white/20 rounded-full transition-all hover:scale-110"
            disabled={isLoading}
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
      <div className="bg-gradient-to-t from-black/80 to-transparent px-4 pb-3 pt-10 space-y-1">
        <VideoSeekbar
          currentTime={currentTime}
          duration={duration}
          onSeek={onSeek}
          onSeekStart={onSeekStart}
        />

        {/* Bottom row */}
        <div className="flex items-center justify-between">
          {/* Left — Time + Volume */}
          <div className="flex items-center">
            <div className="text-[13px] text-white/90 font-medium tabular-nums px-2 py-2 rounded-full hover:bg-white/10 transition-colors cursor-default">
              {formatTime(currentTime)} / {formatTime(duration)}
            </div>
            <VolumeSlider
              volume={volume}
              isMuted={isMuted}
              onVolumeChange={onVolumeChange}
              onToggleMute={onToggleMute}
            />
          </div>

          {/* Right — Controls */}
          <div className="flex items-center gap-0.5">
            {hasEpisodes && (
              <PlayerTooltip label="Episodi">
                <button
                  ref={episodesButtonRef}
                  onClick={onToggleEpisodes}
                  className="p-2 rounded-full hover:bg-white/10 transition-colors"
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

            <PlayerTooltip
              label={isFullscreen ? "Esci da schermo intero" : "Schermo intero"}
            >
              <button
                onClick={onToggleFullscreen}
                className="p-2 rounded-full hover:bg-white/10 transition-colors"
              >
                <AnimatedFullscreen
                  isFullscreen={isFullscreen}
                  className="text-white"
                />
              </button>
            </PlayerTooltip>
          </div>
        </div>
      </div>
    </div>
  );
}
