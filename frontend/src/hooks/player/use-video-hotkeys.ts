"use client";

import { useEffect } from "react";

interface VideoHotkeysProps {
  togglePlay: () => void;
  toggleFullscreen: () => void;
  toggleMute: () => void;
  skip: (seconds: number) => void;
}

export function useVideoHotkeys({
  togglePlay,
  toggleFullscreen,
  toggleMute,
  skip,
}: VideoHotkeysProps) {
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return;

      switch (e.key) {
        case " ":
        case "k":
          e.preventDefault();
          togglePlay();
          break;
        case "f":
          toggleFullscreen();
          break;
        case "m":
          toggleMute();
          break;
        case "ArrowLeft":
          skip(-10);
          break;
        case "ArrowRight":
          skip(10);
          break;
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [togglePlay, toggleFullscreen, toggleMute, skip]);
}
