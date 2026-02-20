"use client";

import { useEffect, useRef } from "react";
import { updateWatchProgress } from "@/lib/api";

interface UseProgressSavingOptions {
  mediaId: number;
  currentTime: number;
  duration: number;
  isPlaying: boolean;
}

/**
 * Saves watch progress periodically (every 10s while playing),
 * on page unload, and on component unmount.
 */
export function useProgressSaving({
  mediaId,
  currentTime,
  duration,
  isPlaying,
}: UseProgressSavingOptions) {
  const lastSavedRef = useRef(0);
  const currentTimeRef = useRef(currentTime);
  const durationRef = useRef(duration);
  const isPlayingRef = useRef(isPlaying);

  // Keep refs in sync without triggering re-renders
  useEffect(() => {
    currentTimeRef.current = currentTime;
    durationRef.current = duration;
  });

  useEffect(() => {
    isPlayingRef.current = isPlaying;
  }, [isPlaying]);

  // Periodic save every 10s while playing
  useEffect(() => {
    const interval = setInterval(() => {
      const time = currentTimeRef.current;
      const dur = durationRef.current;
      if (
        isPlayingRef.current &&
        time > 0 &&
        dur > 0 &&
        time - lastSavedRef.current >= 10
      ) {
        lastSavedRef.current = time;
        updateWatchProgress(mediaId, Math.floor(time), Math.floor(dur)).catch(
          () => {},
        );
      }
    }, 10000);
    return () => clearInterval(interval);
  }, [mediaId]);

  // Save on beforeunload + cleanup
  useEffect(() => {
    const saveProgress = () => {
      const time = currentTimeRef.current;
      const dur = durationRef.current;
      if (time > 0 && dur > 0) {
        updateWatchProgress(mediaId, Math.floor(time), Math.floor(dur)).catch(
          () => {},
        );
      }
    };

    window.addEventListener("beforeunload", saveProgress);
    return () => {
      window.removeEventListener("beforeunload", saveProgress);
      saveProgress();
    };
  }, [mediaId]);
}
