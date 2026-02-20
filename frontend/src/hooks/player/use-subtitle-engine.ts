"use client";

import { useEffect, useRef, useCallback } from "react";
import {
  fetchAvailableFonts,
  fetchSubtitleContent,
  getSubtitleUrl,
} from "./subtitle-fetchers";
import { useCanvasSync } from "./use-canvas-sync";

interface SubtitlesOctopusOptions {
  video?: HTMLVideoElement | null;
  canvas?: HTMLCanvasElement;
  subUrl?: string;
  subContent?: string;
  workerUrl: string;
  legacyWorkerUrl?: string;
  fonts?: string[];
  availableFonts?: Record<string, string>;
  timeOffset?: number;
  onReady?: () => void;
  onError?: (error: Error) => void;
  debug?: boolean;
  renderMode?: "js-blend" | "wasm-blend" | "lossy";
  targetFps?: number;
}

declare class SubtitlesOctopus {
  constructor(options: SubtitlesOctopusOptions);
  timeOffset?: number;
  setTrackByUrl(url: string): void;
  setTrack(content: string): void;
  setCurrentTime(time: number): void;
  freeTrack(): void;
  dispose(): void;
  resize(width?: number, height?: number, top?: number, left?: number): void;
}

interface UseSubtitleEngineOptions {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  mediaId: number;
  subtitleTrack: number | null;
  enabled: boolean;
  timeOffset: number;
  targetFps: number;
  initialManualOffset: number;
}

export function useSubtitleEngine({
  videoRef,
  mediaId,
  subtitleTrack,
  enabled,
  timeOffset,
  targetFps,
  initialManualOffset,
}: UseSubtitleEngineOptions) {
  const octopusRef = useRef<SubtitlesOctopus | null>(null);
  const initializingRef = useRef(false);
  const manualOffsetRef = useRef(initialManualOffset);
  const rafIdRef = useRef<number | null>(null);
  const timeOffsetRef = useRef(timeOffset);

  // Canvas sync (letterbox-aware sizing + ResizeObserver)
  const resizeOctopus = useCallback((w: number, h: number) => {
    try {
      octopusRef.current?.resize(w, h);
    } catch {
      // Worker may not be ready yet
    }
  }, []);

  const { setCanvasRefCallback, canvasRef, canvasReady, canvasSize } =
    useCanvasSync(videoRef, resizeOctopus);

  // Keep refs in sync with props
  useEffect(() => {
    manualOffsetRef.current = initialManualOffset;
  }, [initialManualOffset]);

  useEffect(() => {
    timeOffsetRef.current = timeOffset;
  }, [timeOffset]);

  // Central update: calculates render time and calls JSO
  const updateSubtitles = useCallback(() => {
    const video = videoRef.current;
    const instance = octopusRef.current;
    if (!video || !instance) return;
    const renderTime =
      video.currentTime + timeOffsetRef.current + manualOffsetRef.current;
    instance.setCurrentTime(renderTime);
  }, [videoRef]);

  // Render loop (60fps via requestAnimationFrame)
  const startRenderLoop = useCallback(() => {
    const loop = () => {
      const video = videoRef.current;
      if (!video || video.paused) {
        rafIdRef.current = null;
        return;
      }
      if (video.readyState < 3) {
        rafIdRef.current = requestAnimationFrame(loop);
        return;
      }
      updateSubtitles();
      rafIdRef.current = requestAnimationFrame(loop);
    };
    if (rafIdRef.current === null) {
      setTimeout(() => {
        rafIdRef.current = requestAnimationFrame(loop);
      }, 100);
    }
  }, [videoRef, updateSubtitles]);

  const stopRenderLoop = useCallback(() => {
    if (rafIdRef.current !== null) {
      cancelAnimationFrame(rafIdRef.current);
      rafIdRef.current = null;
    }
  }, []);

  // Initialize SubtitlesOctopus
  const initOctopus = useCallback(async () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !enabled || subtitleTrack === null) return;
    if (initializingRef.current) return;
    initializingRef.current = true;

    // Cleanup previous instance
    if (octopusRef.current) {
      octopusRef.current.dispose();
      octopusRef.current = null;
    }
    stopRenderLoop();

    try {
      const availableFonts = await fetchAvailableFonts(mediaId);
      if (!videoRef.current || !canvasRef.current) return;

      const subContent = await fetchSubtitleContent(mediaId, subtitleTrack);
      if (!subContent) {
        initializingRef.current = false;
        return;
      }

      const SubtitlesOctopusModule = await import("libass-wasm");
      const SubtitlesOctopusLib =
        SubtitlesOctopusModule.default || SubtitlesOctopusModule;

      const currentCanvas = canvasRef.current;
      if (!currentCanvas) {
        initializingRef.current = false;
        return;
      }

      const options: SubtitlesOctopusOptions = {
        video: null,
        canvas: currentCanvas,
        subContent,
        workerUrl: "/lib/subtitles-octopus-worker.js",
        legacyWorkerUrl: "/lib/subtitles-octopus-worker-legacy.js",
        availableFonts,
        targetFps,
        debug: false,
        onReady: () => updateSubtitles(),
        onError: () => {},
      };

      octopusRef.current = new SubtitlesOctopusLib(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        options as any,
      ) as SubtitlesOctopus;

      // Video event listeners for manual sync
      const handlePlay = () => startRenderLoop();
      const handlePause = () => stopRenderLoop();
      const handleSeek = () => updateSubtitles();
      const handleTimeUpdate = () => {
        if (rafIdRef.current === null && video && !video.paused) {
          startRenderLoop();
        }
      };

      video.addEventListener("play", handlePlay);
      video.addEventListener("pause", handlePause);
      video.addEventListener("seeking", handleSeek);
      video.addEventListener("seeked", handleSeek);
      video.addEventListener("timeupdate", handleTimeUpdate);

      const cleanup = () => {
        video.removeEventListener("play", handlePlay);
        video.removeEventListener("pause", handlePause);
        video.removeEventListener("seeking", handleSeek);
        video.removeEventListener("seeked", handleSeek);
        video.removeEventListener("timeupdate", handleTimeUpdate);
      };

      (
        octopusRef as {
          current: SubtitlesOctopus & { _cleanup?: () => void };
        }
      ).current._cleanup = cleanup;

      if (!video.paused) startRenderLoop();
    } catch {
      // Failed to initialize SubtitlesOctopus
    } finally {
      initializingRef.current = false;
    }
  }, [
    videoRef,
    canvasRef,
    enabled,
    subtitleTrack,
    mediaId,
    targetFps,
    updateSubtitles,
    startRenderLoop,
    stopRenderLoop,
  ]);

  // Lifecycle: init/cleanup on track change or enable/disable
  useEffect(() => {
    if (enabled && subtitleTrack !== null && canvasReady) {
      initOctopus();
    } else if (octopusRef.current) {
      const instance = octopusRef.current as SubtitlesOctopus & {
        _cleanup?: () => void;
      };
      instance._cleanup?.();
      instance.dispose();
      octopusRef.current = null;
      stopRenderLoop();
    }

    return () => {
      if (octopusRef.current) {
        const instance = octopusRef.current as SubtitlesOctopus & {
          _cleanup?: () => void;
        };
        instance._cleanup?.();
        instance.dispose();
        octopusRef.current = null;
      }
      stopRenderLoop();
      initializingRef.current = false;
    };
  }, [enabled, subtitleTrack, canvasReady, initOctopus, stopRenderLoop]);

  // Change track without full reinit
  useEffect(() => {
    if (octopusRef.current && subtitleTrack !== null) {
      octopusRef.current.setTrackByUrl(getSubtitleUrl(mediaId, subtitleTrack));
      updateSubtitles();
    }
  }, [subtitleTrack, mediaId, updateSubtitles]);

  // Manual offset setter (triggers immediate render)
  const setManualOffset = useCallback(
    (offset: number) => {
      manualOffsetRef.current = offset;
      updateSubtitles();
    },
    [updateSubtitles],
  );

  return { setCanvasRefCallback, canvasSize, setManualOffset };
}
