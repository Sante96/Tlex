"use client";

import { useEffect } from "react";

interface VideoHotkeysProps {
  togglePlay: () => void;
  toggleFullscreen: () => void;
  toggleMute: () => void;
  skip: (seconds: number) => void;
  onActivity?: () => void;
  /** The controls are on screen */
  controlsVisible: boolean;
  isTV: boolean;
}

// Keys that belong to the element that has them: typing, the subtitle-sync slider
const OWN_KEYS = "input, textarea, select, [contenteditable], [role='slider']";
const CONTROLS = "button, a, [role='button'], [role='menuitem'], [role='option']";

export function useVideoHotkeys({
  togglePlay,
  toggleFullscreen,
  toggleMute,
  skip,
  onActivity,
  controlsVisible,
  isTV,
}: VideoHotkeysProps) {
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      // Handled already (Radix only prevents the default of a slider's arrows), a
      // shortcut of the browser's (Ctrl+F), or typing
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return;
      if (target?.closest?.(OWN_KEYS)) return;

      const onControl = !!target?.closest?.(CONTROLS);
      if (e.key === " " || e.key === "Enter") {
        if (onControl && !controlsVisible) {
          // OK on a hidden control: show the controls instead of pressing a button
          // nobody can see
          e.preventDefault();
          onActivity?.();
          return;
        }
        // A visible focused button (Back, settings, an episode): let it be pressed
        if (onControl) {
          onActivity?.();
          return;
        }
      }

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
        case "ArrowRight":
          // The seekbar handles its own arrows. On the TV, arrows over visible controls
          // move the focus (spatial navigation): skipping too sought on every press while
          // walking to Settings or along the episode strip
          if (target?.dataset?.seekbar) break;
          if (isTV && onControl && controlsVisible) break;
          skip(e.key === "ArrowLeft" ? -10 : 10);
          break;
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [togglePlay, toggleFullscreen, toggleMute, skip, onActivity, controlsVisible, isTV]);
}
