"use client";

import Image from "next/image";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { useIsMobile } from "@/lib/breakpoints";

interface HeroBannerProps {
  /** Banner height in px on desktop: 432 (series), 374 (movie) */
  height: number;
  /** Poster image URL */
  posterUrl: string | null;
  /** Poster width in px (desktop) */
  posterWidth?: number;
  /** Poster height in px (desktop) */
  posterHeight?: number;
  /** Align items: "end" for series/movie, "center" for season */
  align?: "end" | "center";
  /** Alt text for poster */
  posterAlt: string;
  /**
   * Mobile only: content shown beside the poster (title, year, meta).
   * When provided, `children` is rendered full-width below the poster row.
   * On desktop, mobileInfoSlot + children are rendered together in the content column.
   */
  mobileInfoSlot?: React.ReactNode;
  children: React.ReactNode;
}

export function HeroBanner({
  height,
  posterUrl,
  posterWidth = 200,
  posterHeight = 300,
  align = "end",
  posterAlt,
  mobileInfoSlot,
  children,
}: HeroBannerProps) {
  const isMobile = useIsMobile();

  const MOBILE_W = 90;
  const MOBILE_H = 135;

  const posterEl = (
    <div
      className="shrink-0 rounded-xl overflow-hidden bg-[#27272a]"
      style={{
        width: isMobile ? MOBILE_W : posterWidth,
        height: isMobile ? MOBILE_H : posterHeight,
        boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
      }}
    >
      {posterUrl ? (
        <Image
          src={posterUrl}
          alt={posterAlt}
          width={isMobile ? MOBILE_W : posterWidth}
          height={isMobile ? MOBILE_H : posterHeight}
          className="object-cover w-full h-full"
        />
      ) : (
        <div className="w-full h-full flex items-center justify-center text-[#52525b]">
          No Poster
        </div>
      )}
    </div>
  );

  return (
    <div className="relative" style={isMobile ? undefined : { height }}>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{
          duration: 0.4,
          delay: 0.15,
          ease: [0.4, 0, 0.2, 1] as [number, number, number, number],
        }}
        className="relative z-10 h-full"
      >
        {isMobile ? (
          /* ── Mobile layout ── */
          <div className="flex flex-col gap-4 px-4 pt-5 pb-4 text-shadow">
            {/* Row: poster + info (title / meta) */}
            <div className="flex flex-row items-end gap-3">
              {posterEl}
              {mobileInfoSlot ? (
                <div className="flex flex-col gap-1.5 flex-1 min-w-0">
                  {mobileInfoSlot}
                </div>
              ) : (
                /* No slot: fallback — render children beside poster */
                <div className="flex flex-col gap-2 flex-1 min-w-0">
                  {children}
                </div>
              )}
            </div>
            {/* Full-width: buttons + overview */}
            {mobileInfoSlot && (
              <div className="flex flex-col gap-3">{children}</div>
            )}
          </div>
        ) : (
          /* ── Desktop layout ── */
          <div
            className={cn(
              "flex flex-row gap-8 h-full",
              align === "end" ? "items-end" : "items-center",
            )}
            style={{ padding: "0 48px 32px 48px" }}
          >
            {posterEl}
            <div className="flex flex-col gap-4 flex-1 text-shadow min-w-0">
              {mobileInfoSlot}
              {children}
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
}
