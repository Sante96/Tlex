"use client";

import { useState, useRef, useCallback } from "react";
import { cn } from "@/lib/utils";
import { formatTime } from "@/lib/format";

interface VideoSeekbarProps {
  currentTime: number;
  duration: number;
  onSeek: (time: number) => void;
  onSeekStart?: () => void; // Called when user starts hovering (for pre-warming)
  className?: string;
}

export function VideoSeekbar({
  currentTime,
  duration,
  onSeek,
  onSeekStart,
  className,
}: VideoSeekbarProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [isHovering, setIsHovering] = useState(false);
  const [hoverPosition, setHoverPosition] = useState(0);
  const [hoverTime, setHoverTime] = useState(0);

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

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

  return (
    <div
      ref={trackRef}
      className={cn("relative w-full cursor-pointer group py-2", className)}
      onMouseEnter={() => {
        setIsHovering(true);
        onSeekStart?.(); // Pre-warm file_id when user hovers
      }}
      onMouseLeave={() => setIsHovering(false)}
      onMouseMove={handleMouseMove}
      onClick={handleClick}
    >
      {/* Hover time tooltip */}
      {isHovering && (
        <div
          className="absolute -top-8 transform -translate-x-1/2 bg-black/90 text-white text-xs px-2 py-1 rounded pointer-events-none z-10 font-mono"
          style={{ left: `${hoverPosition}%` }}
        >
          {formatTime(hoverTime)}
        </div>
      )}

      {/* Track background */}
      <div
        className={cn(
          "relative w-full rounded-full transition-all duration-150 overflow-hidden",
          isHovering ? "h-2" : "h-1",
        )}
      >
        {/* Background (unplayed) */}
        <div className="absolute inset-0 bg-white/30" />

        {/* Hover preview bar */}
        {isHovering && (
          <div
            className="absolute inset-y-0 left-0 bg-white/20"
            style={{ width: `${hoverPosition}%` }}
          />
        )}

        {/* Progress (played) - Plex orange */}
        <div
          className="absolute inset-y-0 left-0 bg-plex-orange transition-all"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Thumb - visible on hover */}
      <div
        className={cn(
          "absolute top-1/2 -translate-y-1/2 -translate-x-1/2 rounded-full bg-plex-orange shadow-lg transition-all duration-150",
          isHovering ? "w-4 h-4 opacity-100" : "w-0 h-0 opacity-0",
        )}
        style={{ left: `${progress}%` }}
      />
    </div>
  );
}
