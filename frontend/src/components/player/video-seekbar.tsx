"use client";

import { useState, useRef, useCallback } from "react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { formatTime } from "@/lib/format";
import type { Chapter } from "@/lib/api";

const SEEK_STEP = 10; // seconds per arrow key press
const CHAPTER_GAP_PX = 2;

interface VideoSeekbarProps {
  currentTime: number;
  duration: number;
  /** Two or more: the bar is split into one segment per chapter, as on YouTube */
  chapters?: Chapter[] | null;
  /** What a chapter is called on the bar: a concert's are songs ("Brano 12") */
  chapterWord?: "chapter" | "song";
  onSeek: (time: number) => void;
  onActivity?: () => void; // Called on any interaction to keep controls visible
  className?: string;
}

export function VideoSeekbar({
  currentTime,
  duration,
  chapters,
  chapterWord = "chapter",
  onSeek,
  onActivity,
  className,
}: VideoSeekbarProps) {
  const t = useTranslations();
  const trackRef = useRef<HTMLDivElement>(null);
  const [isHovering, setIsHovering] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const [hoverPosition, setHoverPosition] = useState(0);
  const [hoverTime, setHoverTime] = useState(0);
  const [pendingTime, setPendingTime] = useState<number | null>(null);
  // Where a finger or the mouse is dragging the thumb: seeks on release, not on every move
  const [dragTime, setDragTime] = useState<number | null>(null);

  // When focused, display pending position; otherwise real position
  const displayTime = dragTime ?? pendingTime ?? currentTime;
  const progress = duration > 0 ? ((dragTime ?? currentTime) / duration) * 100 : 0;
  const displayProgress = duration > 0 ? (displayTime / duration) * 100 : 0;
  const isDragging = dragTime !== null;
  const isActive = isHovering || isFocused || isDragging;

  const timeAt = (clientX: number) => {
    const rect = trackRef.current!.getBoundingClientRect();
    return Math.max(0, Math.min(1, (clientX - rect.left) / rect.width)) * duration;
  };

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (duration <= 0 || e.button !== 0) return;
    // Keep receiving the moves when the finger slides off the thin track
    e.currentTarget.setPointerCapture(e.pointerId);
    setDragTime(timeAt(e.clientX));
    onActivity?.();
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (duration <= 0) return;
    const time = timeAt(e.clientX);
    setHoverPosition((time / duration) * 100);
    setHoverTime(time);
    if (isDragging) {
      setDragTime(time);
      onActivity?.();
    }
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDragging) return;
    setDragTime(null);
    onSeek(timeAt(e.clientX));
    // The click focused the bar, and focus is the keyboard's (remote's) mode: the tooltip
    // and the enlarged chapter followed the playhead instead of the mouse, and the
    // arrows moved a pending seek instead of skipping, until the controls hid
    e.currentTarget.blur();
  };

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      // Ctrl+arrows go chapter by chapter (the player's hotkeys)
      if (duration <= 0 || e.ctrlKey) return;
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

  const tooltipPosition =
    isFocused || isDragging ? displayProgress : isHovering ? hoverPosition : null;

  const tooltipTime = isFocused || isDragging ? displayTime : hoverTime;

  const segmented = !!chapters && chapters.length > 1 && duration > 0;
  // The spans of time the bar is drawn in: one per chapter (the last one reaches the
  // end of the bar), or the whole title. Before the duration is known: an empty bar
  const total = duration > 0 ? duration : 1;
  const spans = segmented
    ? chapters.map((c, i) => (i === chapters.length - 1 ? { ...c, end: duration } : c))
    : [{ start: 0, end: total, title: null }];
  // The chapter under the mouse, under the dragged thumb, or at the keyboard's position
  const activeChapter =
    segmented && tooltipPosition !== null
      ? Math.max(0, spans.filter((s) => s.start <= tooltipTime).length - 1)
      : -1;
  const pct = (time: number) => (time / total) * 100;

  return (
    <div
      ref={trackRef}
      tabIndex={0}
      data-seekbar="true"
      className={cn(
        // touch-none: a horizontal drag scrubs instead of scrolling or swiping
        "relative w-full cursor-pointer group py-2 touch-none",
        "outline-none focus-visible:ring-2 focus-visible:ring-white/60 focus-visible:ring-offset-1 focus-visible:ring-offset-transparent rounded-sm",
        className,
      )}
      onPointerEnter={(e) => e.pointerType === "mouse" && setIsHovering(true)}
      onPointerLeave={() => setIsHovering(false)}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={() => setDragTime(null)}
      onFocus={() => setIsFocused(true)}
      onBlur={() => {
        setIsFocused(false);
        setPendingTime(null);
      }}
      onKeyDown={handleKeyDown}
    >
      {/* Time tooltip — on hover or when focused with pending position. Slides across
          its own width along the bar, so near the edges it stays on screen */}
      {tooltipPosition !== null && (
        <div
          className="absolute -top-8 bg-black/90 text-white text-xs px-2 py-1 rounded pointer-events-none z-10 font-mono whitespace-nowrap"
          style={{ left: `${tooltipPosition}%`, transform: `translateX(-${tooltipPosition}%)` }}
        >
          {activeChapter >= 0 &&
            `${spans[activeChapter].title ?? t(`player.${chapterWord}`, { n: activeChapter + 1 })} · `}
          {formatTime(tooltipTime)}
        </div>
      )}

      {/* Track: one segment per chapter, each filled with its own share of the time */}
      <div className="relative h-2.5">
        {spans.map((span, i) => {
          // How much of this span a time covers, in % of the span
          const fill = (time: number) =>
            Math.max(0, Math.min(1, (time - span.start) / (span.end - span.start))) * 100;
          const played = fill(dragTime ?? currentTime);
          const pending = fill(displayTime);
          const width = pct(span.end - span.start);
          return (
            <div
              key={span.start}
              className={cn(
                "absolute top-1/2 -translate-y-1/2 rounded-full overflow-hidden transition-[height] duration-150",
                i === activeChapter ? "h-2.5" : isActive ? (segmented ? "h-1.5" : "h-2") : "h-1",
              )}
              style={{
                left: `${pct(span.start)}%`,
                // The gap comes out of the segment's end: times keep their place on the bar
                width:
                  i < spans.length - 1 ? `calc(${width}% - ${CHAPTER_GAP_PX}px)` : `${width}%`,
              }}
            >
              {/* Background (unplayed) */}
              <div className="absolute inset-0 bg-white/30" />

              {/* Hover preview bar (mouse only) */}
              {isHovering && !isFocused && !isDragging && (
                <div
                  className="absolute inset-y-0 left-0 bg-white/20"
                  style={{ width: `${fill(hoverTime)}%` }}
                />
              )}

              {/* Real progress (played) - always visible */}
              <div
                className={cn(
                  "absolute inset-y-0 left-0 bg-plex-orange",
                  !isDragging && "transition-all",
                )}
                style={{ width: `${played}%` }}
              />

              {/* Pending seek bar — shown in focus mode */}
              {isFocused && pendingTime !== null && (
                <div
                  className={cn(
                    "absolute inset-y-0 left-0 transition-all",
                    displayProgress > progress ? "bg-white/50" : "bg-black/40",
                  )}
                  style={{
                    left: `${Math.min(played, pending)}%`,
                    width: `${Math.abs(pending - played)}%`,
                  }}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Thumb — visible on hover or focus */}
      <div
        className={cn(
          "absolute top-1/2 -translate-y-1/2 -translate-x-1/2 rounded-full shadow-lg duration-150",
          isDragging ? "transition-[width,height,opacity]" : "transition-all",
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
          {t("player.seekHint")}
        </div>
      )}
    </div>
  );
}
