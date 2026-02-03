"use client";

import {
  useEffect,
  useRef,
  useCallback,
  useImperativeHandle,
  forwardRef,
  useState,
} from "react";

interface SubtitleRendererProps {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  mediaId: number;
  subtitleTrack: number | null;
  enabled: boolean;
  timeOffset?: number; // Base offset (e.g., streamStartTime / keyframe time)
  targetFps?: number; // Video frame rate for subtitle rendering
  initialManualOffset?: number; // Initial manual offset from saved state
}

// Exposed methods for parent component
export interface SubtitleRendererHandle {
  setManualOffset: (offset: number) => void;
}

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

// Use empty string for relative paths (API calls go through Next.js rewrites)
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

export const SubtitleRenderer = forwardRef<
  SubtitleRendererHandle,
  SubtitleRendererProps
>(function SubtitleRenderer(
  {
    videoRef,
    mediaId,
    subtitleTrack,
    enabled,
    timeOffset = 0,
    targetFps = 24,
    initialManualOffset = 0,
  },
  ref,
) {
  const octopusRef = useRef<SubtitlesOctopus | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const initializingRef = useRef(false);
  const [canvasReady, setCanvasReady] = useState(false);

  // Callback ref to track when canvas is mounted (fixes timing issue)
  const setCanvasRefCallback = useCallback((node: HTMLCanvasElement | null) => {
    canvasRef.current = node;
    setCanvasReady(!!node);
  }, []);
  const manualOffsetRef = useRef(initialManualOffset);
  const rafIdRef = useRef<number | null>(null);
  const timeOffsetRef = useRef(timeOffset); // Keep ref in sync for render loop

  // Track canvas dimensions and position (for letterbox handling)
  const [canvasSize, setCanvasSize] = useState({
    width: 0,
    height: 0,
    offsetX: 0,
    offsetY: 0,
  });

  // Keep refs in sync with props
  useEffect(() => {
    manualOffsetRef.current = initialManualOffset;
  }, [initialManualOffset]);

  useEffect(() => {
    timeOffsetRef.current = timeOffset;
  }, [timeOffset]);

  const getSubtitleUrl = useCallback(
    (track: number) => {
      // Add cache buster to force fresh fetch
      const cacheBuster = Date.now();
      return `${API_BASE_URL}/api/v1/subtitles/${mediaId}?track=${track}&format=ass&_=${cacheBuster}`;
    },
    [mediaId],
  );

  // Central update function - calculates render time and calls JSO
  const updateSubtitles = useCallback(() => {
    const video = videoRef.current;
    const instance = octopusRef.current;

    if (!video || !instance) return;

    // Total render time = video time + keyframe offset + manual slider offset
    const renderTime =
      video.currentTime + timeOffsetRef.current + manualOffsetRef.current;
    instance.setCurrentTime(renderTime);
  }, [videoRef]);

  // Render loop for smooth playback (60fps via requestAnimationFrame)
  const startRenderLoop = useCallback(() => {
    const loop = () => {
      const video = videoRef.current;
      if (!video || video.paused) {
        rafIdRef.current = null;
        return;
      }

      // readyState < 3 = browser doesn't have enough data for current + next frame
      // Skip subtitle rendering to let CPU focus on video decoding (Fast Start)
      if (video.readyState < 3) {
        rafIdRef.current = requestAnimationFrame(loop);
        return;
      }

      updateSubtitles();
      rafIdRef.current = requestAnimationFrame(loop);
    };

    // Start the loop with small delay to let video decoder warm up
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

  // Sync canvas size with actual video content (accounting for letterbox)
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const syncSize = () => {
      const containerRect = video.getBoundingClientRect();
      const videoWidth = video.videoWidth;
      const videoHeight = video.videoHeight;

      if (
        containerRect.width <= 0 ||
        containerRect.height <= 0 ||
        !videoWidth ||
        !videoHeight
      ) {
        return;
      }

      // Calculate actual video dimensions within container (object-fit: contain)
      const containerAspect = containerRect.width / containerRect.height;
      const videoAspect = videoWidth / videoHeight;

      let renderWidth: number,
        renderHeight: number,
        offsetX: number,
        offsetY: number;

      if (videoAspect > containerAspect) {
        // Video is wider - letterbox top/bottom (pillarbox scenario unlikely here)
        renderWidth = containerRect.width;
        renderHeight = containerRect.width / videoAspect;
        offsetX = 0;
        offsetY = (containerRect.height - renderHeight) / 2;
      } else {
        // Video is taller - letterbox left/right (black bars on sides)
        renderHeight = containerRect.height;
        renderWidth = containerRect.height * videoAspect;
        offsetX = (containerRect.width - renderWidth) / 2;
        offsetY = 0;
      }

      setCanvasSize({
        width: Math.round(renderWidth),
        height: Math.round(renderHeight),
        offsetX: Math.round(offsetX),
        offsetY: Math.round(offsetY),
      });

      // Also resize JSO if initialized (with error handling for worker not ready)
      if (octopusRef.current) {
        try {
          octopusRef.current.resize(
            Math.round(renderWidth),
            Math.round(renderHeight),
          );
        } catch {
          // Worker may not be ready yet, ignore
        }
      }
    };

    // Wait for video metadata to load
    const handleLoadedMetadata = () => syncSize();
    video.addEventListener("loadedmetadata", handleLoadedMetadata);

    syncSize();
    const resizeObserver = new ResizeObserver(syncSize);
    resizeObserver.observe(video);

    return () => {
      resizeObserver.disconnect();
      video.removeEventListener("loadedmetadata", handleLoadedMetadata);
    };
  }, [videoRef]);

  const initOctopus = useCallback(async () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    console.log("initOctopus called:", {
      video: !!video,
      canvas: !!canvas,
      enabled,
      subtitleTrack,
      initializing: initializingRef.current,
    });
    if (!video || !canvas || !enabled || subtitleTrack === null) {
      console.log("initOctopus early return: missing requirements");
      return;
    }
    if (initializingRef.current) {
      console.log("initOctopus early return: already initializing");
      return;
    }

    initializingRef.current = true;
    console.log("initOctopus starting...");

    // Cleanup previous instance
    if (octopusRef.current) {
      octopusRef.current.dispose();
      octopusRef.current = null;
    }
    stopRenderLoop();

    try {
      // Fetch available fonts
      console.log("Fetching fonts...");
      const availableFonts: Record<string, string> = {
        default: "/lib/default.woff2",
      };
      try {
        const fontsCacheBuster = Date.now();
        console.log(
          "Fetching fonts from:",
          `${API_BASE_URL}/api/v1/subtitles/${mediaId}/fonts?_=${fontsCacheBuster}`,
        );
        const fontsResponse = await fetch(
          `${API_BASE_URL}/api/v1/subtitles/${mediaId}/fonts?_=${fontsCacheBuster}`,
        );
        console.log("Fonts response status:", fontsResponse.status);
        if (fontsResponse.ok) {
          const fontsData = await fontsResponse.json();
          for (const font of fontsData.fonts || []) {
            const url = `${API_BASE_URL}${font.url}`;
            const filename = font.filename
              .toLowerCase()
              .replace(/\.(ttf|otf|woff|woff2)$/i, "");

            // Register by filename
            availableFonts[filename] = url;

            // Register by internal font names (Family, Full Name, PostScript)
            const fontNames: string[] = font.names || [];
            for (const name of fontNames) {
              if (name) {
                availableFonts[name.toLowerCase()] = url;
              }
            }

            // Also try filename-based aliases
            const baseNameMatch = filename.match(
              /^(.+?)(b|i|z|bold|italic|regular)?$/i,
            );
            if (baseNameMatch) {
              const baseName = baseNameMatch[1].replace(/[-_]$/, "");
              if (baseName !== filename) {
                availableFonts[baseName] = url;
              }
            }

            const spacedName = filename.replace(/[-_]/g, " ");
            if (spacedName !== filename) {
              availableFonts[spacedName] = url;
            }
          }
          console.log("Available fonts:", Object.keys(availableFonts));
        }
      } catch (e) {
        console.warn("Could not fetch fonts, using fallback:", e);
      }

      if (!videoRef.current || !canvasRef.current) {
        console.warn("Video or canvas element no longer available");
        return;
      }

      // Fetch subtitle content first (avoids CORS issues in worker)
      let subContent: string | undefined;
      try {
        const subUrl = getSubtitleUrl(subtitleTrack);
        console.log("Fetching subtitles from:", subUrl);
        const subResponse = await fetch(subUrl);
        if (subResponse.ok) {
          subContent = await subResponse.text();
          console.log("Fetched subtitle content:", subContent.length, "bytes");
        } else {
          console.warn("Failed to fetch subtitles:", subResponse.status);
        }
      } catch (e) {
        console.warn("Error fetching subtitles:", e);
      }

      if (!subContent) {
        console.warn("No subtitle content available");
        initializingRef.current = false;
        return;
      }

      // Dynamic import
      const SubtitlesOctopusModule = await import("libass-wasm");
      const SubtitlesOctopusLib =
        SubtitlesOctopusModule.default || SubtitlesOctopusModule;

      // Re-check canvas after async operations (component might have unmounted)
      const currentCanvas = canvasRef.current;
      if (!currentCanvas) {
        console.warn("Canvas no longer available after async fetch");
        initializingRef.current = false;
        return;
      }

      // DETACHED MODE: video: null, we drive rendering manually
      const options: SubtitlesOctopusOptions = {
        video: null, // Detached mode - we control rendering
        canvas: currentCanvas,
        subContent, // Pass content directly instead of URL (avoids CORS in worker)
        workerUrl: "/lib/subtitles-octopus-worker.js",
        legacyWorkerUrl: "/lib/subtitles-octopus-worker-legacy.js",
        availableFonts,
        targetFps,
        debug: false,
        onReady: () => {
          console.log("SubtitlesOctopus ready (Detached Mode)");
          // Initial render
          updateSubtitles();
        },
        onError: (err: unknown) => {
          console.error("SubtitlesOctopus error:", err);
        },
      };

      console.log("Initializing SubtitlesOctopus (Detached Mode)");
      octopusRef.current = new SubtitlesOctopusLib(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        options as any,
      ) as SubtitlesOctopus;

      // Setup video event listeners for manual sync
      const handlePlay = () => startRenderLoop();
      const handlePause = () => stopRenderLoop();
      const handleSeek = () => updateSubtitles();
      const handleTimeUpdate = () => {
        // Fallback: update on timeupdate if not in RAF loop
        if (rafIdRef.current === null && video && !video.paused) {
          startRenderLoop();
        }
      };

      video.addEventListener("play", handlePlay);
      video.addEventListener("pause", handlePause);
      video.addEventListener("seeking", handleSeek);
      video.addEventListener("seeked", handleSeek);
      video.addEventListener("timeupdate", handleTimeUpdate);

      // Store cleanup function
      const cleanup = () => {
        video.removeEventListener("play", handlePlay);
        video.removeEventListener("pause", handlePause);
        video.removeEventListener("seeking", handleSeek);
        video.removeEventListener("seeked", handleSeek);
        video.removeEventListener("timeupdate", handleTimeUpdate);
      };

      // Attach cleanup to ref for later
      (
        octopusRef as { current: SubtitlesOctopus & { _cleanup?: () => void } }
      ).current._cleanup = cleanup;

      // Start loop if already playing
      if (!video.paused) {
        startRenderLoop();
      }
    } catch (error) {
      console.error("Failed to initialize SubtitlesOctopus:", error);
    } finally {
      initializingRef.current = false;
    }
  }, [
    videoRef,
    enabled,
    subtitleTrack,
    getSubtitleUrl,
    mediaId,
    targetFps,
    updateSubtitles,
    startRenderLoop,
    stopRenderLoop,
  ]);

  // Initialize/cleanup on track change or enable/disable
  // canvasReady ensures we wait for the canvas to be mounted before init
  useEffect(() => {
    console.log("SubtitleRenderer effect:", {
      enabled,
      subtitleTrack,
      canvasReady,
    });
    if (enabled && subtitleTrack !== null && canvasReady) {
      console.log("Calling initOctopus for track:", subtitleTrack);
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
      // Reset initializing flag to allow re-initialization on track change
      initializingRef.current = false;
    };
  }, [enabled, subtitleTrack, canvasReady, initOctopus, stopRenderLoop]);

  // Expose setManualOffset to parent - triggers immediate render
  useImperativeHandle(
    ref,
    () => ({
      setManualOffset: (offset: number) => {
        manualOffsetRef.current = offset;
        // Force immediate render (works even in pause!)
        updateSubtitles();
      },
    }),
    [updateSubtitles],
  );

  // Change track without full reinit
  useEffect(() => {
    if (octopusRef.current && subtitleTrack !== null) {
      octopusRef.current.setTrackByUrl(getSubtitleUrl(subtitleTrack));
      // Re-render after track change
      updateSubtitles();
    }
  }, [subtitleTrack, getSubtitleUrl, updateSubtitles]);

  // Render canvas overlay (positioned over video via CSS in parent)
  if (!enabled) return null;

  return (
    <canvas
      ref={setCanvasRefCallback}
      width={canvasSize.width}
      height={canvasSize.height}
      style={{
        position: "absolute",
        top: canvasSize.offsetY,
        left: canvasSize.offsetX,
        width: canvasSize.width,
        height: canvasSize.height,
        pointerEvents: "none",
        zIndex: 10, // Below controls (controls should be z-20+)
      }}
    />
  );
});
