"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { getNextEpisode, getRecommendations, type MediaItem, type NextEpisode } from "@/lib/api";

// Without a credits point (set by hand, a chapter, the series): this long before the end
const SHOW_OVERLAY_BEFORE_END = 30;

interface UseNextEpisodeOptions {
  mediaId: number;
  isEpisode: boolean;
  /** A film: Up next offers films of the library */
  isMovie: boolean;
  currentTime: number;
  duration: number;
  /** Where the credits start (seconds) */
  creditsStart?: number | null;
}

export function useNextEpisode({
  mediaId,
  isEpisode,
  isMovie,
  currentTime,
  duration,
  creditsStart,
}: UseNextEpisodeOptions) {
  const [nextEpisode, setNextEpisode] = useState<NextEpisode | null>(null);
  const [recommendations, setRecommendations] = useState<MediaItem[]>([]);
  const [cancelledAt, setCancelledAt] = useState<number | null>(null);
  // TEMPORARY, while Up next is redone: ?endcard shows it from the start
  const [preview] = useState(
    () => typeof window !== "undefined" && new URLSearchParams(location.search).has("endcard"),
  );
  const fetchedRef = useRef(false);

  // What comes next, once
  useEffect(() => {
    if (fetchedRef.current) return;
    if (isEpisode) {
      fetchedRef.current = true;
      getNextEpisode(mediaId).then(setNextEpisode);
    } else if (isMovie) {
      fetchedRef.current = true;
      getRecommendations(mediaId).then(setRecommendations);
    }
  }, [mediaId, isEpisode, isMovie]);

  const hasNext = !!nextEpisode || recommendations.length > 0;

  // Derive overlay visibility from current playback state
  const showNextOverlay = useMemo(() => {
    if (preview && hasNext && cancelledAt === null) return true;
    if (!hasNext || duration <= 0 || currentTime <= 0) return false;
    // From the credits on. Do NOT hide when the video ends: the countdown plays the next
    const from = creditsStart ?? duration - SHOW_OVERLAY_BEFORE_END;
    if (currentTime < from) return false;
    // If user cancelled, only re-show if they seeked back past the threshold
    if (cancelledAt !== null && currentTime >= cancelledAt) return false;
    return true;
  }, [hasNext, duration, currentTime, cancelledAt, preview, creditsStart]);

  const cancelNextOverlay = useCallback(() => {
    setCancelledAt(currentTime);
  }, [currentTime]);

  return { nextEpisode, recommendations, showNextOverlay, cancelNextOverlay };
}
