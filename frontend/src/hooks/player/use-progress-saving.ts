"use client";

import { useCallback, useEffect, useRef } from "react";
import { saveWatchProgressOnExit, updateWatchProgress } from "@/lib/api";

interface UseProgressSavingOptions {
  mediaId: number;
  currentTime: number;
  duration: number;
  isPlaying: boolean;
}

/**
 * Saves watch progress periodically (every 10s while playing), when the page is
 * hidden or closed, and on component unmount.
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
  // Moved on to the next title: every save from now on (the unmount's too) says finished
  const finishedRef = useRef(false);

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
        !finishedRef.current &&
        isPlayingRef.current &&
        time > 0 &&
        dur > 0 &&
        // abs: after seeking back from 50:00 to 10:00 keep saving, not from 50:10 on
        Math.abs(time - lastSavedRef.current) >= 10
      ) {
        lastSavedRef.current = time;
        updateWatchProgress(mediaId, Math.floor(time), Math.floor(dur)).catch(
          () => {},
        );
      }
    }, 10000);
    return () => clearInterval(interval);
  }, [mediaId]);

  // Save when the tab is hidden or closed (mobile browsers often never fire
  // beforeunload, and an async axios call there may never be sent) + on unmount
  useEffect(() => {
    const current = () => {
      const dur = durationRef.current;
      const time = finishedRef.current ? dur : currentTimeRef.current;
      return time > 0 && dur > 0
        ? { position: Math.floor(time), duration: Math.floor(dur) }
        : null;
    };
    const saveOnExit = () => {
      const p = current();
      if (p) {
        lastSavedRef.current = p.position;
        saveWatchProgressOnExit(mediaId, p.position, p.duration);
      }
    };
    const onVisibilityChange = () => {
      if (document.visibilityState === "hidden") saveOnExit();
    };

    window.addEventListener("pagehide", saveOnExit);
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      window.removeEventListener("pagehide", saveOnExit);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      const p = current();
      if (p) updateWatchProgress(mediaId, p.position, p.duration).catch(() => {});
    };
  }, [mediaId]);

  /** Next episode, a recommended film: this title counts as watched */
  const markFinished = useCallback(() => {
    const dur = Math.floor(durationRef.current);
    if (dur <= 0 || finishedRef.current) return;
    finishedRef.current = true;
    updateWatchProgress(mediaId, dur, dur).catch(() => {});
  }, [mediaId]);

  return { markFinished };
}
