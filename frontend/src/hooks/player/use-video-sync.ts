"use client";

import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { getStreamUrl, warmStream } from "@/lib/api";

interface VideoSyncState {
  videoUrl: string | undefined;
  streamStartTime: number;
  localSeekOffset: number;
  /** Read the start time headers off the stream's response */
  applyStreamHeaders: (headers: Headers) => void;
}

export function useVideoSync(
  mediaId: number,
  selectedAudio: number,
  seekTime: number,
  initialPosition: number,
  seekId = 0,
): VideoSyncState {
  const [isWarmed, setIsWarmed] = useState(false);
  const [streamStartTime, setStreamStartTime] = useState(initialPosition);
  const [localSeekOffset, setLocalSeekOffset] = useState(0);
  const warmedIdRef = useRef<number | null>(null);

  // Pre-warm Telegram file_id cache on mount.
  // Guard by mediaId instead of boolean so StrictMode cleanup+remount doesn't double-fire.
  useEffect(() => {
    if (warmedIdRef.current === mediaId) return;
    warmedIdRef.current = mediaId;
    warmStream(mediaId).then(() => setIsWarmed(true));
  }, [mediaId]);

  // Memoize URL string to avoid spurious effect re-triggers
  const videoUrl = useMemo(
    () =>
      isWarmed
        ? getStreamUrl(mediaId, { audio: selectedAudio, t: seekTime, seek: seekId })
        : undefined,
    [isWarmed, mediaId, selectedAudio, seekTime, seekId],
  );

  // The stream starts at the keyframe before the requested time: X-Stream-Start-Time is
  // where (subtitles and the clock count from it), and the requested time minus it is how
  // far to play before showing the picture. A HEAD request used to fetch these on every
  // seek: a second keyframe lookup, and when the GET won the race the player synced to
  // the previous stream's offset.
  const applyStreamHeaders = useCallback(
    (headers: Headers) => {
      const start = parseFloat(headers.get("X-Stream-Start-Time") ?? "");
      const requested = parseFloat(headers.get("X-Requested-Time") ?? "");
      if (Number.isFinite(start)) {
        setStreamStartTime(start);
        setLocalSeekOffset(Number.isFinite(requested) ? Math.max(0, requested - start) : 0);
      } else {
        setStreamStartTime(seekTime);
        setLocalSeekOffset(0);
      }
    },
    [seekTime],
  );

  return { videoUrl, streamStartTime, localSeekOffset, applyStreamHeaders };
}
