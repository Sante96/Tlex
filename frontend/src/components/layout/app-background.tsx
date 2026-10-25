"use client";

import dynamic from "next/dynamic";
import { TVBackground } from "@/components/ds";
import { useIsTV } from "@/hooks/use-platform";
import { useIsMobile } from "@/lib/breakpoints";

const MeshGradient = dynamic(
  () => import("@paper-design/shaders-react").then((m) => ({ default: m.MeshGradient })),
  { ssr: false },
);

/**
 * The page background, behind everything: the animated WebGL shader on desktop; the CSS
 * one on the TV and on phones, where the shader kept the GPU (and the battery) busy.
 */
export function AppBackground() {
  const isTV = useIsTV();
  const isMobile = useIsMobile();

  return (
    <div className="fixed inset-0 -z-10">
      {isTV || isMobile ? (
        <TVBackground />
      ) : (
        <>
          <MeshGradient
            style={{ width: "100%", height: "100%" }}
            colors={["#09090b", "#1c1500", "#09090b"]}
            distortion={1}
            swirl={0.1}
            grainMixer={0}
            grainOverlay={0}
            speed={0.25}
          />
          <div className="absolute inset-0" style={{ backgroundColor: "rgba(9,9,11,0.45)" }} />
        </>
      )}
    </div>
  );
}
