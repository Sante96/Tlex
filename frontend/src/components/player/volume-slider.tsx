"use client";

import { useState, useRef, useCallback } from "react";
import { cn } from "@/lib/utils";
import { AnimatedVolume } from "./animated-icons";

const HANDLE_SIZE = 12;
const TRACK_WIDTH = 44;
const SLIDER_WIDTH = TRACK_WIDTH + HANDLE_SIZE;

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
  const sliderRef = useRef<HTMLDivElement>(null);
  const [hovering, setHovering] = useState(false);
  const [dragging, setDragging] = useState(false);

  const displayVolume = isMuted ? 0 : volume;
  const handleLeft = displayVolume * TRACK_WIDTH;
  const expanded = hovering || dragging;

  const volumeFromEvent = useCallback(
    (clientX: number) => {
      if (!sliderRef.current) return;
      const rect = sliderRef.current.getBoundingClientRect();
      const offset = HANDLE_SIZE / 2;
      onVolumeChange(
        Math.max(0, Math.min(1, (clientX - rect.left - offset) / TRACK_WIDTH)),
      );
    },
    [onVolumeChange],
  );

  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragging(true);
      volumeFromEvent(e.clientX);

      const onMove = (ev: MouseEvent) => volumeFromEvent(ev.clientX);
      const onUp = () => {
        setDragging(false);
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      };
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },
    [volumeFromEvent],
  );

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full transition-colors",
        expanded ? "bg-white/10" : "hover:bg-white/10",
        className,
      )}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => {
        setDragging(false);
        setHovering(false);
      }}
    >
      <button onClick={onToggleMute} className="p-2 flex-shrink-0">
        <AnimatedVolume
          volume={volume}
          isMuted={isMuted}
          className="text-white"
        />
      </button>

      {/* Clip wrapper — hides slider when collapsed, tall enough for handle */}
      <div
        className="overflow-hidden transition-[width,margin] duration-150 ease-out"
        style={{
          width: expanded ? SLIDER_WIDTH : 0,
          marginRight: expanded ? 8 : 0,
          height: 36,
        }}
      >
        <div
          ref={sliderRef}
          className="relative flex items-center cursor-pointer"
          style={{ width: SLIDER_WIDTH, height: 36, touchAction: "none" }}
          onMouseDown={onMouseDown}
        >
          {/* Track */}
          <div
            className="absolute top-1/2 -translate-y-1/2 h-[3px] rounded-full bg-white/25"
            style={{ left: HANDLE_SIZE / 2, right: HANDLE_SIZE / 2 }}
          />
          {/* Fill */}
          <div
            className="absolute top-1/2 -translate-y-1/2 h-[3px] rounded-full bg-plex-orange"
            style={{ left: HANDLE_SIZE / 2, width: handleLeft }}
          />
          {/* Handle */}
          <div
            className="absolute top-1/2 rounded-full bg-white"
            style={{
              left: handleLeft,
              width: HANDLE_SIZE,
              height: HANDLE_SIZE,
              marginTop: -(HANDLE_SIZE / 2),
            }}
          />
        </div>
      </div>
    </span>
  );
}
