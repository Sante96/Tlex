"use client";

import { useEffect, useState, useCallback, useRef } from "react";

interface CanvasSize {
  width: number;
  height: number;
  offsetX: number;
  offsetY: number;
}

/**
 * Syncs a canvas overlay with the actual video content area,
 * accounting for letterboxing (object-fit: contain).
 */
export function useCanvasSync(
  videoRef: React.RefObject<HTMLVideoElement | null>,
  resizeCallback?: (width: number, height: number) => void,
) {
  const [canvasReady, setCanvasReady] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [canvasSize, setCanvasSize] = useState<CanvasSize>({
    width: 0,
    height: 0,
    offsetX: 0,
    offsetY: 0,
  });

  const setCanvasRefCallback = useCallback((node: HTMLCanvasElement | null) => {
    canvasRef.current = node;
    setCanvasReady(!!node);
  }, []);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const syncSize = () => {
      const rect = video.getBoundingClientRect();
      const vw = video.videoWidth;
      const vh = video.videoHeight;
      if (rect.width <= 0 || rect.height <= 0 || !vw || !vh) return;

      const containerAspect = rect.width / rect.height;
      const videoAspect = vw / vh;
      let rw: number, rh: number, ox: number, oy: number;

      if (videoAspect > containerAspect) {
        rw = rect.width;
        rh = rect.width / videoAspect;
        ox = 0;
        oy = (rect.height - rh) / 2;
      } else {
        rh = rect.height;
        rw = rect.height * videoAspect;
        ox = (rect.width - rw) / 2;
        oy = 0;
      }

      const finalW = Math.round(rw);
      const finalH = Math.round(rh);
      if (finalW <= 0 || finalH <= 0) return;

      setCanvasSize({
        width: finalW,
        height: finalH,
        offsetX: Math.round(ox),
        offsetY: Math.round(oy),
      });

      resizeCallback?.(finalW, finalH);
    };

    const handleLoadedMetadata = () => syncSize();
    video.addEventListener("loadedmetadata", handleLoadedMetadata);
    syncSize();
    const resizeObserver = new ResizeObserver(syncSize);
    resizeObserver.observe(video);

    return () => {
      resizeObserver.disconnect();
      video.removeEventListener("loadedmetadata", handleLoadedMetadata);
    };
  }, [videoRef, resizeCallback]);

  return { setCanvasRefCallback, canvasRef, canvasReady, canvasSize };
}
