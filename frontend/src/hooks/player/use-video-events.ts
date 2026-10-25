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
  /** The stream failed (a 5xx, the pool full, Telegram): there's no more data coming */
  onError?: () => void;
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
  onError,
}: VideoEventsProps) {
  const videoMovingRef = useRef(false);
  const isMutedRef = useRef(isMuted);
  const streamStartTimeRef = useRef(streamStartTime);
  const isSeekingRef = useRef(isSeeking);
  const localSeekOffsetRef = useRef(localSeekOffset);
  const onErrorRef = useRef(onError);
  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

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
    // A new stream starts playing by itself; a seek or a rebuffer must keep a pause (every
    // canplay used to call play(), so a paused video restarted after a seek)
    let autoplay = true;

    const resetDetection = () => {
      videoMovingRef.current = false;
      video.muted = true;
      lastFrameTime = -1;
    };

    // Sync point reached — audio/video/subs are aligned
    const markSynced = () => {
      videoMovingRef.current = true;
      video.muted = isMutedRef.current;
      setIsLoading(false);
    };

    // Fake loader: video starts from keyframe BEFORE requested time.
    // We keep spinner visible + audio muted until video.currentTime reaches
    // localSeekOffset (the point where audio/video/subs are in sync).
    // requestVideoFrameCallback gives us frame-accurate detection.
    const trackFrame = () => {
      if ("requestVideoFrameCallback" in video) {
        // One loop at a time: every loadstart (seek) used to start another
        if (frameCallbackId !== null) {
          (video as VFCVideo).cancelVideoFrameCallback(frameCallbackId);
        }
        frameCallbackId = (video as VFCVideo).requestVideoFrameCallback(() => {
          const currentVideoTime = video.currentTime;

          if (
            !videoMovingRef.current &&
            lastFrameTime >= 0 &&
            currentVideoTime > lastFrameTime + 0.01 &&
            currentVideoTime >= localSeekOffsetRef.current
          ) {
            markSynced();
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
      autoplay = true;
    };

    // 'playing' event: clears loading ONLY for rebuffers (after initial sync)
    // During initial sync, videoMovingRef is false so loading stays visible
    const onPlaying = () => {
      if (videoMovingRef.current) {
        setIsLoading(false);
      }
    };

    const onTimeUpdate = () => {
      // Frame callbacks can be missing or stay silent (seen in headless Chrome while
      // the video played): playback moving past the sync point also ends the wait
      if (
        !videoMovingRef.current &&
        !video.paused &&
        video.currentTime > localSeekOffsetRef.current
      ) {
        markSynced();
      }
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
      if (!autoplay) return;
      autoplay = false;
      video.play().catch(() => {
        // Video play failed (likely user interaction required)
      });
    };

    const onWaiting = () => setIsLoading(true);
    // Without this the spinner turned forever after a failed stream
    const onStreamError = () => {
      setIsLoading(false);
      setIsSeeking(false);
      onErrorRef.current?.();
    };
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
    video.addEventListener("error", onStreamError);
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
      video.removeEventListener("error", onStreamError);
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
