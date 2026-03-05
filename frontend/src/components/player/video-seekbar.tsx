"use client";

import { useState, useRef, useCallback } from "react";
import { cn } from "@/lib/utils";
import { formatTime } from "@/lib/format";

const SEEK_STEP = 10; // seconds per arrow key press

interface VideoSeekbarProps {
  currentTime: number;
  duration: number;
  onSeek: (time: number) => void;
  onSeekStart?: () => void; // Called when user starts hovering (for pre-warming)
  onActivity?: () => void; // Called on any interaction to keep controls visible
  className?: string;
}

export function VideoSeekbar({
  currentTime,
  duration,
  onSeek,
  onSeekStart,
  onActivity,
  className,
}: VideoSeekbarProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [isHovering, setIsHovering] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const [hoverPosition, setHoverPosition] = useState(0);
  const [hoverTime, setHoverTime] = useState(0);
  const [pendingTime, setPendingTime] = useState<number | null>(null);

  // When focused, display pending position; otherwise real position
  const displayTime = pendingTime ?? currentTime;
  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;
  const displayProgress = duration > 0 ? (displayTime / duration) * 100 : 0;
  const isActive = isHovering || isFocused;

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!trackRef.current || duration <= 0) return;
      const rect = trackRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const percentage = Math.max(0, Math.min(1, x / rect.width));
      setHoverPosition(percentage * 100);
      setHoverTime(percentage * duration);
    },
    [duration],
  );

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!trackRef.current || duration <= 0) return;
      const rect = trackRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const percentage = Math.max(0, Math.min(1, x / rect.width));
      onSeek(percentage * duration);
    },
    [duration, onSeek],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (duration <= 0) return;
      const base = pendingTime ?? currentTime;
      switch (e.key) {
        case "ArrowLeft":
          e.preventDefault();
          e.stopPropagation();
          onActivity?.();
          setPendingTime(Math.max(0, base - SEEK_STEP));
          break;
        case "ArrowRight":
          e.preventDefault();
          e.stopPropagation();
          onActivity?.();
          setPendingTime(Math.min(duration, base + SEEK_STEP));
          break;
        case "Enter":
          e.preventDefault();
          e.stopPropagation();
          if (pendingTime !== null) {
            onSeek(pendingTime);
            setPendingTime(null);
          }
          break;
        case "Escape":
          e.preventDefault();
          setPendingTime(null);
          (e.currentTarget as HTMLElement).blur();
          break;
      }
    },
    [duration, currentTime, pendingTime, onSeek, onActivity],
  );

  const tooltipLeft = isFocused
    ? `${displayProgress}%`
    : isHovering
      ? `${hoverPosition}%`
      : null;

  const tooltipTime = isFocused ? displayTime : hoverTime;

  return (
    <div
      ref={trackRef}
      tabIndex={0}
      data-seekbar="true"
      className={cn(
        "relative w-full cursor-pointer group py-2",
        "outline-none focus-visible:ring-2 focus-visible:ring-white/60 focus-visible:ring-offset-1 focus-visible:ring-offset-transparent rounded-sm",
        className,
      )}
      onMouseEnter={() => {
        setIsHovering(true);
        onSeekStart?.();
      }}
      onMouseLeave={() => setIsHovering(false)}
      onMouseMove={handleMouseMove}
      onClick={handleClick}
      onFocus={() => setIsFocused(true)}
      onBlur={() => {
        setIsFocused(false);
        setPendingTime(null);
      }}
      onKeyDown={handleKeyDown}
    >
      {/* Time tooltip — on hover or when focused with pending position */}
      {tooltipLeft !== null && (
        <div
          className="absolute -top-8 transform -translate-x-1/2 bg-black/90 text-white text-xs px-2 py-1 rounded pointer-events-none z-10 font-mono"
          style={{ left: tooltipLeft }}
        >
          {formatTime(tooltipTime)}
        </div>
      )}

      {/* Track background */}
      <div
        className={cn(
          "relative w-full rounded-full transition-all duration-150 overflow-hidden",
          isActive ? "h-2" : "h-1",
        )}
      >
        {/* Background (unplayed) */}
        <div className="absolute inset-0 bg-white/30" />

        {/* Hover preview bar (mouse only) */}
        {isHovering && !isFocused && (
          <div
            className="absolute inset-y-0 left-0 bg-white/20"
            style={{ width: `${hoverPosition}%` }}
          />
        )}

        {/* Real progress (played) - always visible */}
        <div
          className="absolute inset-y-0 left-0 bg-plex-orange transition-all"
          style={{ width: `${progress}%` }}
        />

        {/* Pending seek bar — shown in focus mode */}
        {isFocused && pendingTime !== null && (
          <div
            className={cn(
              "absolute inset-y-0 left-0 transition-all",
              displayProgress > progress ? "bg-white/50" : "bg-black/40",
            )}
            style={{
              left: `${Math.min(progress, displayProgress)}%`,
              width: `${Math.abs(displayProgress - progress)}%`,
            }}
          />
        )}
      </div>

      {/* Thumb — visible on hover or focus */}
      <div
        className={cn(
          "absolute top-1/2 -translate-y-1/2 -translate-x-1/2 rounded-full shadow-lg transition-all duration-150",
          isActive ? "w-4 h-4 opacity-100" : "w-0 h-0 opacity-0",
          isFocused && pendingTime !== null
            ? "bg-white scale-125"
            : "bg-plex-orange",
        )}
        style={{ left: `${displayProgress}%` }}
      />

      {/* Focus hint label */}
      {isFocused && pendingTime !== null && (
        <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 text-[10px] text-white/50 pointer-events-none whitespace-nowrap">
          ← → sposta · Enter conferma · Esc annulla
        </div>
      )}
    </div>
  );
}
