"use client";

import { useImperativeHandle, forwardRef } from "react";
import { useSubtitleEngine } from "@/hooks/player/use-subtitle-engine";

interface SubtitleRendererProps {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  mediaId: number;
  subtitleTrack: number | null;
  /** A PGS track (Blu-ray pictures) rather than a text one */
  pgs?: boolean;
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
    pgs = false,
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
      pgs,
      enabled,
      timeOffset,
      targetFps,
      initialManualOffset,
    });

  useImperativeHandle(ref, () => ({ setManualOffset }), [setManualOffset]);

  if (!enabled) return null;

  return (
    <canvas
      // Its own canvas per kind of track: libpgs sizes it to the subtitle's screen
      // (1920x1080, scaled by the CSS size below), libass to the screen's pixels
      key={pgs ? "pgs" : "ass"}
      ref={setCanvasRefCallback}
      width={pgs ? undefined : canvasSize.pixelWidth}
      height={pgs ? undefined : canvasSize.pixelHeight}
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
