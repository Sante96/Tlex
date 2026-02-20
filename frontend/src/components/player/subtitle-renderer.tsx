"use client";

import { useImperativeHandle, forwardRef } from "react";
import { useSubtitleEngine } from "@/hooks/player/use-subtitle-engine";

interface SubtitleRendererProps {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  mediaId: number;
  subtitleTrack: number | null;
  enabled: boolean;
  visible?: boolean;
  timeOffset?: number;
  targetFps?: number;
  initialManualOffset?: number;
}

export interface SubtitleRendererHandle {
  setManualOffset: (offset: number) => void;
}

export const SubtitleRenderer = forwardRef<
  SubtitleRendererHandle,
  SubtitleRendererProps
>(function SubtitleRenderer(
  {
    videoRef,
    mediaId,
    subtitleTrack,
    enabled,
    visible = true,
    timeOffset = 0,
    targetFps = 24,
    initialManualOffset = 0,
  },
  ref,
) {
  const { setCanvasRefCallback, canvasSize, setManualOffset } =
    useSubtitleEngine({
      videoRef,
      mediaId,
      subtitleTrack,
      enabled,
      timeOffset,
      targetFps,
      initialManualOffset,
    });

  useImperativeHandle(ref, () => ({ setManualOffset }), [setManualOffset]);

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
        zIndex: 10,
        opacity: visible ? 1 : 0,
      }}
    />
  );
});
