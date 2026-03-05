"use client";

/**
 * TVBackground — cinematic dark background for TV pages.
 * Uses multi-stop radial gradients + SVG grain overlay to eliminate CSS banding.
 * Lightweight CSS-only, no WebGL/canvas.
 */
export function TVBackground() {
  return (
    <div className="fixed inset-0 z-0" aria-hidden="true">
      {/* Base: multi-stop radial gradients to reduce banding */}
      <div
        className="absolute inset-0"
        style={{
          background: `
            radial-gradient(ellipse 80% 60% at 30% 55%, #1c1300 0%, #130e00 18%, #0d0900 35%, #09090b 55%, #09090b 100%),
            radial-gradient(ellipse 60% 50% at 72% 42%, #110d00 0%, #0c0900 22%, #09090b 45%, transparent 70%)
          `,
        }}
      />
      {/* Grain overlay — eliminates banding via dithering */}
      <div
        className="absolute inset-0 opacity-[0.055]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
          backgroundRepeat: "repeat",
          backgroundSize: "200px 200px",
        }}
      />
    </div>
  );
}
