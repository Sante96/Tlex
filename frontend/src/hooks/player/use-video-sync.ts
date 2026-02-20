"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { getStreamUrl, warmStream } from "@/lib/api";

interface VideoSyncState {
  videoUrl: string | undefined;
  streamStartTime: number;
  localSeekOffset: number;
  isWarmed: boolean;
}

export function useVideoSync(
  mediaId: number,
  selectedAudio: number,
  seekTime: number,
  initialPosition: number,
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
        ? getStreamUrl(mediaId, { audio: selectedAudio, t: seekTime })
        : undefined,
    [isWarmed, mediaId, selectedAudio, seekTime],
  );

  // Fetch stream headers for subtitle sync and local seek calculation
  useEffect(() => {
    if (!videoUrl) return;

    const fetchStreamHeaders = async () => {
      try {
        const response = await fetch(videoUrl, { method: "HEAD" });
        const startTime = response.headers.get("X-Stream-Start-Time");
        const requestedTime = response.headers.get("X-Requested-Time");

        if (startTime) {
          const start = parseFloat(startTime);
          setStreamStartTime(start);

          // Calculate local seek offset (measured from start of the streamed chunk)
          if (requestedTime) {
            const requested = parseFloat(requestedTime);
            // If requested > start, we need to seek forward in the player
            // But we already set currentTime to seekTime in the player state?
            // The issue is: video.currentTime starts at 0 for the NEW stream.
            // But the stream actually represents time X to Y.
            // If we request time T, and we get back a stream starting at T' (keyframe before T),
            // then we need to seek to T - T' in the video element relative to 0?
            // Wait, the logic in original file was:

            // "Calculate local seek offset (target - start)"
            // "setLocalSeekOffset(offset > 0 ? offset : 0);"

            const offset = requested - start;
            setLocalSeekOffset(offset > 0 ? offset : 0);
          }
        } else {
          setStreamStartTime(seekTime);
          setLocalSeekOffset(0);
        }
      } catch {
        setStreamStartTime(seekTime);
        setLocalSeekOffset(0);
      }
    };
    fetchStreamHeaders();
  }, [videoUrl, seekTime]);

  return { videoUrl, streamStartTime, localSeekOffset, isWarmed };
}
