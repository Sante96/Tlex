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
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
      className={outerClass || undefined}
      style={isFluid ? undefined : { width: fixedW }}
    >
      <Link href={href} className="group block">
        <div
          className={`relative bg-[#27272a] rounded-lg overflow-hidden${isFluid ? " aspect-[2/3] w-full" : ""}`}
          style={isFluid ? undefined : { width: fixedW, height: fixedH }}
        >
          {imageUrl ? (
            <Image src={imageUrl} alt={title} fill className="object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-[#52525b] text-sm">
              {title}
            </div>
          )}

          {children}

          {progress !== undefined && progress > 0 && (
            <div className="absolute bottom-0 left-0 right-0 h-1 rounded-b-lg overflow-hidden bg-[#3f3f46]">
              <div
                className="h-full rounded-bl-lg bg-[#e5a00d]"
                style={{ width: `${progress}%` }}
              />
            </div>
          )}
        </div>
        <p className="mt-2 text-sm font-medium text-[#fafafa] truncate">
          {title}
        </p>
        {subtitle && <p className="text-xs text-[#a1a1aa]">{subtitle}</p>}
      </Link>
    </motion.div>
  );
}
