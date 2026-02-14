"use client";

import Image from "next/image";

interface DetailPageLayoutProps {
  backdropUrl: string | null;
  children: React.ReactNode;
}

/**
 * Wrapper for detail pages (serie, movie, season).
 * Renders a full-page backdrop image behind ALL content with a gradient overlay.
 * Gradient stops match the design breakpoint exactly.
 */
export function DetailPageLayout({
  backdropUrl,
  children,
}: DetailPageLayoutProps) {
  return (
    <div className="relative min-h-screen">
      {/* Full-page backdrop image — covers entire content area */}
      {backdropUrl && (
        <>
          <div className="absolute inset-0 overflow-hidden">
            <Image
              src={backdropUrl}
              alt=""
              fill
              className="object-cover object-top"
              sizes="100vw"
              priority
            />
          </div>
          {/* Gradient overlay — stops from design breakpoint:
              0%: transparent, 25%: 10% opacity, 50%: 50% opacity, 65%: 80% opacity */}
          <div
            className="absolute inset-0"
            style={{
              background: `linear-gradient(180deg,
                #09090b00 0%,
                #09090b1a 25%,
                #09090b80 50%,
                #09090bcc 65%
              )`,
            }}
          />
        </>
      )}

      {/* Page content on top */}
      <div className="relative z-10">{children}</div>
    </div>
  );
}
