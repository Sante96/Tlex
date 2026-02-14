"use client";

import Image from "next/image";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface HeroBannerProps {
  /** Banner height in px: 432 (series), 374 (movie), 200 (season) */
  height: number;
  /** Poster image URL */
  posterUrl: string | null;
  /** Poster width in px */
  posterWidth?: number;
  /** Poster height in px */
  posterHeight?: number;
  /** Align items: "end" for series/movie, "center" for season */
  align?: "end" | "center";
  /** Alt text for poster */
  posterAlt: string;
  children: React.ReactNode;
}

export function HeroBanner({
  height,
  posterUrl,
  posterWidth = 200,
  posterHeight = 300,
  align = "end",
  posterAlt,
  children,
}: HeroBannerProps) {
  return (
    <div className="relative" style={{ height }}>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{
          duration: 0.4,
          delay: 0.15,
          ease: [0.4, 0, 0.2, 1] as [number, number, number, number],
        }}
        className={cn(
          "relative z-10 flex gap-8 h-full",
          align === "end" ? "items-end" : "items-center",
        )}
        style={{ padding: "0 48px 32px 48px" }}
      >
        {/* Poster */}
        <div
          className="shrink-0 rounded-xl overflow-hidden bg-[#27272a]"
          style={{
            width: posterWidth,
            height: posterHeight,
            boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
          }}
        >
          {posterUrl ? (
            <Image
              src={posterUrl}
              alt={posterAlt}
              width={posterWidth}
              height={posterHeight}
              className="object-cover w-full h-full"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-[#52525b]">
              No Poster
            </div>
          )}
        </div>

        {/* Content slot — text-shadow for readability on backdrop */}
        <div className="flex flex-col gap-4 flex-1 text-shadow">{children}</div>
      </motion.div>
    </div>
  );
}
