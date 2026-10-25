"use client";

import Link from "next/link";
import Image from "next/image";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface PosterCardProps {
  href: string;
  imageUrl: string | null;
  title: string;
  subtitle?: string;
  /** Width in px. When omitted together with height, card is fluid (w-full, aspect-[2/3]) */
  width?: number;
  /** Height in px. When omitted together with width, card is fluid */
  height?: number;
  /** Optional progress bar 0-100 */
  progress?: number;
  children?: React.ReactNode;
  /** Extra classes for the outer wrapper. When provided in fluid mode, overrides the default w-full */
  className?: string;
}

// The columns of POSTER_GRID (layout/library-page): 3, 4 sm, 5 md, 6 lg, 7 xl, 9 2xl
const POSTER_GRID_SIZES =
  "(min-width: 1536px) 11vw, (min-width: 1280px) 14vw, (min-width: 1024px) 17vw, (min-width: 768px) 20vw, (min-width: 640px) 25vw, 33vw";

export function PosterCard({
  href,
  imageUrl,
  title,
  subtitle,
  width,
  height,
  progress,
  children,
  className,
}: PosterCardProps) {
  const isFluid = width === undefined && height === undefined;
  const fixedW = width ?? 180;
  const fixedH = height ?? 270;
  const outerClass = cn(isFluid ? (className ?? "w-full") : className);

  return (
    <motion.div
      whileHover={{ scale: 1.05, y: -4 }}
      whileFocus={{ scale: 1.05, y: -4 }}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
      className={outerClass || undefined}
      style={isFluid ? undefined : { width: fixedW }}
    >
      <Link href={href} className="group block outline-none focus-visible:outline-none">
        <div
          className={`relative bg-[#27272a] rounded-lg overflow-hidden ring-2 ring-transparent group-focus-visible:ring-plex-orange transition-shadow${isFluid ? " aspect-[2/3] w-full" : ""}`}
          style={isFluid ? undefined : { width: fixedW, height: fixedH }}
        >
          {imageUrl ? (
            <Image
              src={imageUrl}
              alt={title}
              fill
              // Without sizes the browser takes the variant as wide as the screen
              sizes={isFluid ? POSTER_GRID_SIZES : `${fixedW}px`}
              className="object-cover"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-[#52525b] text-sm">
              {title}
            </div>
          )}

          {children}

          {progress !== undefined && progress > 0 && (
            <div className="absolute bottom-0 left-0 right-0 h-1 rounded-b-lg overflow-hidden bg-[#3f3f46]">
              <div
                className="h-full rounded-bl-lg bg-plex-orange"
                style={{ width: `${progress}%` }}
              />
            </div>
          )}
        </div>
        <p className="mt-2 text-sm font-medium text-[#fafafa] truncate leading-snug">
          {title}
        </p>
        {subtitle && <p className="text-xs text-[#71717a] truncate">{subtitle}</p>}
      </Link>
    </motion.div>
  );
}
