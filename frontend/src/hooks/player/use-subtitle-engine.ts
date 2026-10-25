"use client";

import { useEffect, useRef, useCallback } from "react";
import type { PgsRenderer } from "libpgs";
import { fetchAvailableFonts, fetchSubtitleFile } from "./subtitle-fetchers";
import { useCanvasSync } from "./use-canvas-sync";

// libpgs exports its renderer only, not the enum of its modes
type PgsRendererMode = NonNullable<ConstructorParameters<typeof PgsRenderer>[0]["mode"]>;

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

/** What the render loop drives: libass for a text track, libpgs for a PGS one */
interface SubtitleInstance {
  setCurrentTime(time: number): void;
  resize?(width: number, height: number): void;
  dispose(): void;
  _cleanup?: () => void;
}

interface UseSubtitleEngineOptions {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  mediaId: number;
  subtitleTrack: number | null;
  /** The track is PGS (Blu-ray pictures): libpgs draws it, from the .sup */
  pgs: boolean;
  enabled: boolean;
  timeOffset: number;
  targetFps: number;
  initialManualOffset: number;
}

export function useSubtitleEngine({
  videoRef,
  mediaId,
  subtitleTrack,
  pgs,
  enabled,
  timeOffset,
  targetFps,
  initialManualOffset,
}: UseSubtitleEngineOptions) {
  const octopusRef = useRef<SubtitleInstance | null>(null);
  // Bumped by every init and dispose: an init that resumes after its track changed
  // (fonts/subtitle fetches are slow) sees it's stale and creates nothing
  const generationRef = useRef(0);
  const manualOffsetRef = useRef(initialManualOffset);
  const rafIdRef = useRef<number | null>(null);
  const rafTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const timeOffsetRef = useRef(timeOffset);

  // Canvas sync (letterbox-aware sizing + ResizeObserver)
  const resizeOctopus = useCallback((w: number, h: number) => {
    try {
      octopusRef.current?.resize?.(w, h);
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
      rafTimerRef.current = setTimeout(() => {
        rafTimerRef.current = null;
        rafIdRef.current = requestAnimationFrame(loop);
      }, 100);
    }
  }, [videoRef, updateSubtitles]);

  const stopRenderLoop = useCallback(() => {
    if (rafTimerRef.current !== null) {
      clearTimeout(rafTimerRef.current);
      rafTimerRef.current = null;
    }
    if (rafIdRef.current !== null) {
      cancelAnimationFrame(rafIdRef.current);
      rafIdRef.current = null;
    }
  }, []);

  // Also invalidates any init still in flight
  const disposeOctopus = useCallback(() => {
    generationRef.current++;
    const instance = octopusRef.current;
    if (instance) {
      instance._cleanup?.();
      instance.dispose();
      octopusRef.current = null;
    }
    stopRenderLoop();
  }, [stopRenderLoop]);

  // Initialize SubtitlesOctopus
  const initOctopus = useCallback(async () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !enabled || subtitleTrack === null) return;
    disposeOctopus();
    const generation = ++generationRef.current;
    const isStale = () => generation !== generationRef.current;

    try {
      if (pgs) {
        const file = await fetchSubtitleFile(mediaId, subtitleTrack, "sup", isStale);
        const buffer = file && (await file.arrayBuffer());
        if (!buffer || isStale()) return;

        const { PgsRenderer } = await import("libpgs");
        const pgsCanvas = canvasRef.current;
        if (isStale() || !pgsCanvas) return;

        const renderer = new PgsRenderer({
          canvas: pgsCanvas,
          workerUrl: "/lib/libpgs.worker.js",
          // Decoded in a worker, drawn here: the all-in-worker mode takes the canvas over
          // for good, and the next PGS track couldn't draw on it
          mode: "workerWithoutOffscreenCanvas" as PgsRendererMode,
        });
        await renderer.loadFromBuffer(buffer);
        if (isStale()) {
          renderer.dispose();
          return;
        }
        octopusRef.current = {
          setCurrentTime: (time) => renderer.renderAtTimestamp(time),
          dispose: () => {
            renderer.dispose();
            // The next track's renderer doesn't know what this one left drawn
            pgsCanvas.getContext("2d")?.clearRect(0, 0, pgsCanvas.width, pgsCanvas.height);
          },
        };
        updateSubtitles();
      } else {
        const availableFonts = await fetchAvailableFonts(mediaId);
        if (isStale() || !videoRef.current || !canvasRef.current) return;

        const file = await fetchSubtitleFile(mediaId, subtitleTrack, "ass", isStale);
        const subContent = file && (await file.text());
        if (!subContent || isStale()) return;

        const SubtitlesOctopusModule = await import("libass-wasm");
        const SubtitlesOctopusLib =
          SubtitlesOctopusModule.default || SubtitlesOctopusModule;

        const currentCanvas = canvasRef.current;
        if (isStale() || !currentCanvas) return;

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
      }

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

      octopusRef.current._cleanup = cleanup;

      if (!video.paused) startRenderLoop();
    } catch {
      // Failed to initialize SubtitlesOctopus
    }
  }, [
    videoRef,
    canvasRef,
    enabled,
    subtitleTrack,
    pgs,
    mediaId,
    targetFps,
    updateSubtitles,
    startRenderLoop,
    stopRenderLoop,
    disposeOctopus,
  ]);

  // Lifecycle: init/cleanup on track change or enable/disable
  useEffect(() => {
    if (enabled && subtitleTrack !== null && canvasReady) {
      initOctopus();
    } else {
      disposeOctopus();
    }

    return disposeOctopus;
  }, [enabled, subtitleTrack, canvasReady, initOctopus, disposeOctopus]);

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
