"use client";

import { useState, useRef, useCallback } from "react";
import { Volume2, VolumeX, Volume1 } from "lucide-react";
import { cn } from "@/lib/utils";

interface VolumeSliderProps {
  volume: number;
  isMuted: boolean;
  onVolumeChange: (value: number) => void;
  onToggleMute: () => void;
  className?: string;
}

export function VolumeSlider({
  volume,
  isMuted,
  onVolumeChange,
  onToggleMute,
  className,
}: VolumeSliderProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [isHovering, setIsHovering] = useState(false);

  const displayVolume = isMuted ? 0 : volume;
  const progress = displayVolume * 100;

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      e.stopPropagation();
      if (!trackRef.current) return;
      const rect = trackRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const percentage = Math.max(0, Math.min(1, x / rect.width));
      onVolumeChange(percentage);
    },
    [onVolumeChange],
  );

  const handleDrag = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (e.buttons !== 1 || !trackRef.current) return;
      e.stopPropagation();
      const rect = trackRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const percentage = Math.max(0, Math.min(1, x / rect.width));
      onVolumeChange(percentage);
    },
    [onVolumeChange],
  );

  const VolumeIcon =
    isMuted || volume === 0 ? VolumeX : volume < 0.5 ? Volume1 : Volume2;

  return (
    <div
      className={cn("flex items-center", className)}
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      {/* Volume icon button */}
      <button
        onClick={onToggleMute}
        className="p-2 hover:bg-white/20 rounded-full transition-colors"
      >
        <VolumeIcon className="h-5 w-5 text-white" />
      </button>

      {/* Slider track container */}
      <div
        ref={trackRef}
        className={cn(
          "relative h-8 cursor-pointer flex items-center transition-[width,opacity] duration-150 ease-out",
          isHovering ? "w-20 opacity-100 ml-1" : "w-0 opacity-0 ml-0",
        )}
        onClick={handleClick}
        onMouseMove={handleDrag}
      >
        {/* Track background */}
        <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-1 rounded-full bg-white/30" />

        {/* Progress (filled) - Plex orange */}
        <div
          className="absolute top-1/2 -translate-y-1/2 left-0 h-1 rounded-full bg-plex-orange"
          style={{ width: `${progress}%` }}
        />

        {/* Thumb */}
        <div
          className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-white shadow-md"
          style={{ left: `calc(${progress}% - 6px)` }}
        />
      </div>
    </div>
  );
}
