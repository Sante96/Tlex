"use client";

import { useEffect, useRef, useState, useCallback } from "react";

interface VideoEventsProps {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  streamStartTime: number;
  initialDuration?: number;
  isSeeking: boolean;
  isMuted: boolean;
  setIsPlaying: (playing: boolean) => void;
  setIsLoading: (loading: boolean) => void;
  setIsSeeking: (seeking: boolean) => void;
  setCurrentTime: (time: number) => void;
  setDuration: (duration: number) => void;
}

export function useVideoEvents({
  videoRef,
  streamStartTime,
  initialDuration,
  isSeeking,
  isMuted,
  setIsPlaying,
  setIsLoading,
  setIsSeeking,
  setCurrentTime,
  setDuration,
}: VideoEventsProps) {
  const videoMovingRef = useRef(false);
  const isMutedRef = useRef(isMuted);

  // Keep isMutedRef in sync
  useEffect(() => {
    isMutedRef.current = isMuted;
  }, [isMuted]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    // Reset video moving state when new video loads
    videoMovingRef.current = false;
    // Mute audio during freeze
    video.muted = true;

    // Track actual frame rendering
    let lastFrameTime = -1;
    const trackFrame = () => {
      if ("requestVideoFrameCallback" in video) {
        (
          video as HTMLVideoElement & {
            requestVideoFrameCallback: (cb: () => void) => void;
          }
        ).requestVideoFrameCallback(() => {
          const currentVideoTime = video.currentTime;

          if (
            !videoMovingRef.current &&
            lastFrameTime >= 0 &&
            currentVideoTime > lastFrameTime + 0.01
          ) {
            videoMovingRef.current = true;
            setIsLoading(false);
            video.muted = isMutedRef.current;
          }

          lastFrameTime = currentVideoTime;
          trackFrame();
        });
      }
    };
    trackFrame();

    const onTimeUpdate = () => {
      if (!isSeeking && videoMovingRef.current) {
        setCurrentTime(streamStartTime + video.currentTime);
      }
    };

    const onDurationChange = () => {
      if (!initialDuration && video.duration && isFinite(video.duration)) {
        setDuration(video.duration);
      }
    };

    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);

    const onCanPlay = () => {
      setIsSeeking(false);
      video.play().catch((e) => {
        if (e.name !== "AbortError") {
          console.warn("Video play failed:", e);
        }
      });
    };

    const onWaiting = () => setIsLoading(true);
    const onEnded = () => setIsPlaying(false);

    video.addEventListener("timeupdate", onTimeUpdate);
    video.addEventListener("durationchange", onDurationChange);
    video.addEventListener("play", onPlay);
    video.addEventListener("pause", onPause);
    video.addEventListener("canplay", onCanPlay);
    video.addEventListener("waiting", onWaiting);
    video.addEventListener("ended", onEnded);

    return () => {
      video.removeEventListener("timeupdate", onTimeUpdate);
      video.removeEventListener("durationchange", onDurationChange);
      video.removeEventListener("play", onPlay);
      video.removeEventListener("pause", onPause);
      video.removeEventListener("canplay", onCanPlay);
      video.removeEventListener("waiting", onWaiting);
      video.removeEventListener("ended", onEnded);
    };
  }, [
    streamStartTime,
    initialDuration,
    isSeeking,
    videoRef,
    setIsPlaying,
    setIsLoading,
    setIsSeeking,
    setCurrentTime,
    setDuration,
  ]);
}
