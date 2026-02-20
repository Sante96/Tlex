"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { getNextEpisode, type NextEpisode } from "@/lib/api";

const SHOW_OVERLAY_BEFORE_END = 30; // seconds before end to show overlay

interface UseNextEpisodeOptions {
  mediaId: number;
  isEpisode: boolean;
  currentTime: number;
  duration: number;
}

export function useNextEpisode({
  mediaId,
  isEpisode,
  currentTime,
  duration,
}: UseNextEpisodeOptions) {
  const [nextEpisode, setNextEpisode] = useState<NextEpisode | null>(null);
  const [cancelledAt, setCancelledAt] = useState<number | null>(null);
  const fetchedRef = useRef(false);

  // Fetch next episode data once
  useEffect(() => {
    if (!isEpisode || fetchedRef.current) return;
    fetchedRef.current = true;
    getNextEpisode(mediaId).then(setNextEpisode);
  }, [mediaId, isEpisode]);

  // Derive overlay visibility from current playback state
  const showNextOverlay = useMemo(() => {
    if (!nextEpisode || duration <= 0 || currentTime <= 0) return false;
    const remaining = duration - currentTime;
    // Show from 30s before end. Do NOT hide when remaining hits 0 — the video
    // ending is not a reason to hide; the countdown timer should fire onPlay.
    const nearEnd = remaining <= SHOW_OVERLAY_BEFORE_END;
    if (!nearEnd) return false;
    // If user cancelled, only re-show if they seeked back past the threshold
    if (cancelledAt !== null && currentTime >= cancelledAt) return false;
    return true;
  }, [nextEpisode, duration, currentTime, cancelledAt]);

  const cancelNextOverlay = useCallback(() => {
    setCancelledAt(currentTime);
  }, [currentTime]);

  return { nextEpisode, showNextOverlay, cancelNextOverlay };
}
