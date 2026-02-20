"use client";

import { useEffect, useRef } from "react";

interface VideoEventsProps {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  streamStartTime: number;
  localSeekOffset: number;
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
  localSeekOffset,
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
  const streamStartTimeRef = useRef(streamStartTime);
  const isSeekingRef = useRef(isSeeking);
  const localSeekOffsetRef = useRef(localSeekOffset);

  // Keep refs in sync with props (no effect re-runs)
  useEffect(() => {
    isMutedRef.current = isMuted;
  }, [isMuted]);
  useEffect(() => {
    streamStartTimeRef.current = streamStartTime;
  }, [streamStartTime]);
  useEffect(() => {
    isSeekingRef.current = isSeeking;
  }, [isSeeking]);
  useEffect(() => {
    localSeekOffsetRef.current = localSeekOffset;
  }, [localSeekOffset]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    type VFCVideo = HTMLVideoElement & {
      requestVideoFrameCallback: (cb: () => void) => number;
      cancelVideoFrameCallback: (id: number) => void;
    };

    let lastFrameTime = -1;
    let frameCallbackId: number | null = null;

    const resetDetection = () => {
      videoMovingRef.current = false;
      video.muted = true;
      lastFrameTime = -1;
    };

    // Fake loader: video starts from keyframe BEFORE requested time.
    // We keep spinner visible + audio muted until video.currentTime reaches
    // localSeekOffset (the point where audio/video/subs are in sync).
    // requestVideoFrameCallback gives us frame-accurate detection.
    const trackFrame = () => {
      if ("requestVideoFrameCallback" in video) {
        frameCallbackId = (video as VFCVideo).requestVideoFrameCallback(() => {
          const currentVideoTime = video.currentTime;

          if (
            !videoMovingRef.current &&
            lastFrameTime >= 0 &&
            currentVideoTime > lastFrameTime + 0.01 &&
            currentVideoTime >= localSeekOffsetRef.current
          ) {
            // Sync point reached — audio/video/subs are aligned
            videoMovingRef.current = true;
            video.muted = isMutedRef.current;
            setIsLoading(false);
          }

          lastFrameTime = currentVideoTime;
          trackFrame();
        });
      }
    };

    // Reset detection when video source changes (new stream loaded)
    const onLoadStart = () => {
      resetDetection();
      trackFrame();
    };

    // 'playing' event: clears loading ONLY for rebuffers (after initial sync)
    // During initial sync, videoMovingRef is false so loading stays visible
    const onPlaying = () => {
      if (videoMovingRef.current) {
        setIsLoading(false);
      }
      // Fallback for browsers without requestVideoFrameCallback
      if (!("requestVideoFrameCallback" in video) && !videoMovingRef.current) {
        const checkSync = () => {
          const v = videoRef.current;
          if (!v) return;
          if (v.currentTime >= localSeekOffsetRef.current && !v.paused) {
            videoMovingRef.current = true;
            v.muted = isMutedRef.current;
            setIsLoading(false);
          } else if (!v.paused) {
            setTimeout(checkSync, 50);
          }
        };
        checkSync();
      }
    };

    const onTimeUpdate = () => {
      if (!isSeekingRef.current && videoMovingRef.current) {
        setCurrentTime(streamStartTimeRef.current + video.currentTime);
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
      video.play().catch(() => {
        // Video play failed (likely user interaction required)
      });
    };

    const onWaiting = () => setIsLoading(true);
    const onEnded = () => setIsPlaying(false);

    // Initial setup
    resetDetection();
    trackFrame();

    video.addEventListener("loadstart", onLoadStart);
    video.addEventListener("playing", onPlaying);
    video.addEventListener("timeupdate", onTimeUpdate);
    video.addEventListener("durationchange", onDurationChange);
    video.addEventListener("play", onPlay);
    video.addEventListener("pause", onPause);
    video.addEventListener("canplay", onCanPlay);
    video.addEventListener("waiting", onWaiting);
    video.addEventListener("ended", onEnded);

    return () => {
      // Cancel pending frame callback
      if (frameCallbackId !== null && "cancelVideoFrameCallback" in video) {
        (video as VFCVideo).cancelVideoFrameCallback(frameCallbackId);
      }
      video.removeEventListener("loadstart", onLoadStart);
      video.removeEventListener("playing", onPlaying);
      video.removeEventListener("timeupdate", onTimeUpdate);
      video.removeEventListener("durationchange", onDurationChange);
      video.removeEventListener("play", onPlay);
      video.removeEventListener("pause", onPause);
      video.removeEventListener("canplay", onCanPlay);
      video.removeEventListener("waiting", onWaiting);
      video.removeEventListener("ended", onEnded);
    };
  }, [
    videoRef,
    initialDuration,
    setIsPlaying,
    setIsLoading,
    setIsSeeking,
    setCurrentTime,
    setDuration,
  ]);
}
