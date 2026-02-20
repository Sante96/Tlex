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
      {/* Backdrop — fixed to viewport, visible through semi-transparent sidebar/nav */}
      {backdropUrl && (
        <div className="fixed inset-0 z-0 overflow-hidden">
          <Image
            src={backdropUrl}
            alt=""
            fill
            className="object-cover object-top"
            sizes="100vw"
            priority
          />
          {/* Gradient overlay */}
          <div
            className="absolute inset-0"
            style={{
              background: `linear-gradient(180deg,
                #09090b40 0%,
                #09090b75 30%,
                #09090b90 50%,
                #09090bcc 65%,
                #09090b 100%
              )`,
            }}
          />
        </div>
      )}

      {/* Page content on top */}
      <div className="relative z-10">{children}</div>
    </div>
  );
}
