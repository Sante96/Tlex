"use client";

import {
  Play,
  Pause,
  Maximize,
  Minimize,
  ChevronLeft,
  RotateCcw,
  RotateCw,
} from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { formatTime } from "@/lib/format";
import { PlayerSettingsDropdown } from "./player-settings";
import { VideoSeekbar } from "./video-seekbar";
import { VolumeSlider } from "./volume-slider";
import type { MediaStream } from "@/lib/api";

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
}: PlayerControlsProps) {
  return (
    <div
      className={cn(
        "absolute inset-0 flex flex-col transition-opacity duration-300 z-20",
        visible ? "opacity-100" : "opacity-0 pointer-events-none",
      )}
    >
      {/* Top bar - Plex style with centered title */}
      <div className="flex items-center p-4 bg-gradient-to-b from-black/90 via-black/50 to-transparent">
        <button
          onClick={onBack}
          className="p-2 hover:bg-white/20 rounded-full transition-colors"
        >
          <ChevronLeft className="h-7 w-7 text-white" />
        </button>
        <div className="flex-1 text-center px-4">
          <h1 className="text-white font-semibold text-lg truncate">{title}</h1>
          {subtitle && (
            <p className="text-zinc-400 text-sm truncate">{subtitle}</p>
          )}
        </div>
        <div className="w-11" /> {/* Spacer to center title */}
      </div>

      {/* Center - Large play/pause button with integrated loader (Plex style) */}
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
            {/* Outer spinning ring when loading - using Framer Motion */}
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
              {isPlaying ? (
                <Pause
                  className={cn(
                    "h-12 w-12 drop-shadow-lg",
                    isLoading ? "text-white/50" : "text-white",
                  )}
                />
              ) : (
                <Play
                  className={cn(
                    "h-12 w-12 ml-1 drop-shadow-lg",
                    isLoading
                      ? "text-white/50 fill-white/50"
                      : "text-white fill-white",
                  )}
                />
              )}
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

      {/* Bottom controls - Plex style */}
      <div className="bg-gradient-to-t from-black/90 via-black/50 to-transparent px-4 pb-4 pt-8 space-y-1">
        {/* Progress bar - Plex style seekbar */}
        <VideoSeekbar
          currentTime={currentTime}
          duration={duration}
          onSeek={onSeek}
          onSeekStart={onSeekStart}
        />

        {/* Bottom row: time left, volume, settings, fullscreen */}
        <div className="flex items-center justify-between">
          {/* Left - Time */}
          <div className="text-sm text-white font-medium min-w-[120px]">
            {formatTime(currentTime)} / {formatTime(duration)}
          </div>

          {/* Right - Controls */}
          <div className="flex items-center gap-1">
            {/* Volume - Plex style */}
            <VolumeSlider
              volume={volume}
              isMuted={isMuted}
              onVolumeChange={onVolumeChange}
              onToggleMute={onToggleMute}
            />

            {/* Settings Dropdown */}
            <PlayerSettingsDropdown
              audioTracks={audioTracks}
              subtitleTracks={subtitleTracks}
              selectedAudio={selectedAudio}
              selectedSubtitle={selectedSubtitle}
              subtitleOffset={subtitleOffset}
              onAudioChange={onAudioChange}
              onSubtitleChange={onSubtitleChange}
              onSubtitleOffsetChange={onSubtitleOffsetChange}
            />

            {/* Fullscreen */}
            <button
              onClick={onToggleFullscreen}
              className="p-2 hover:bg-white/20 rounded-full transition-colors"
            >
              {isFullscreen ? (
                <Minimize className="h-5 w-5 text-white" />
              ) : (
                <Maximize className="h-5 w-5 text-white" />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
