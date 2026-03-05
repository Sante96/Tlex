"use client";

import { useEffect } from "react";

interface VideoHotkeysProps {
  togglePlay: () => void;
  toggleFullscreen: () => void;
  toggleMute: () => void;
  skip: (seconds: number) => void;
  onActivity?: () => void;
}

export function useVideoHotkeys({
  togglePlay,
  toggleFullscreen,
  toggleMute,
  skip,
  onActivity,
}: VideoHotkeysProps) {
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return;

      onActivity?.();
      switch (e.key) {
        case " ":
        case "k":
        case "Enter":
          e.preventDefault();
          togglePlay();
          break;
        case "MediaPlayPause":
        case "MediaPlay":
        case "MediaPause":
          togglePlay();
          break;
        case "f":
          toggleFullscreen();
          break;
        case "m":
          toggleMute();
          break;
        case "ArrowLeft":
          // Let the seekbar handle arrow keys when it's focused
          if ((e.target as HTMLElement)?.dataset?.seekbar) break;
          skip(-10);
          break;
        case "ArrowRight":
          if ((e.target as HTMLElement)?.dataset?.seekbar) break;
          skip(10);
          break;
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [togglePlay, toggleFullscreen, toggleMute, skip, onActivity]);
}
