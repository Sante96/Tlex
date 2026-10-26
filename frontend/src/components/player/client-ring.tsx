"use client";

import { cn } from "@/lib/utils";

const SIZE = 28;
const RADIUS = 11;
const STROKE = 3;
// Degrees left empty between two segments
const GAP = 8;

interface ClientRingProps {
  /** Clients this title's stream holds now */
  inUse: number;
  /** Clients in the whole pool */
  total: number;
  /** Data is arriving: the spinner inside turns */
  downloading: boolean;
  className?: string;
}

/** An arc of the ring, from one angle to another (0° at the top, clockwise) */
function arc(from: number, to: number): string {
  const point = (deg: number) => {
    const rad = ((deg - 90) * Math.PI) / 180;
    return `${SIZE / 2 + RADIUS * Math.cos(rad)} ${SIZE / 2 + RADIUS * Math.sin(rad)}`;
  };
  return `M ${point(from)} A ${RADIUS} ${RADIUS} 0 ${to - from > 180 ? 1 : 0} 1 ${point(to)}`;
}

/**
 * The Telegram clients streaming this title: one segment per client of the pool, the
 * ones in use lit; a spinner inside while data is arriving.
 */
export function ClientRing({ inUse, total, downloading, className }: ClientRingProps) {
  const segments = Math.max(total, 1);
  const step = 360 / segments;
  const gap = segments > 1 ? GAP : 0;

  return (
    <svg
      width={SIZE}
      height={SIZE}
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      className={cn("shrink-0", className)}
      aria-hidden
    >
      {Array.from({ length: segments }, (_, i) => (
        <path
          key={i}
          d={arc(i * step + gap / 2, (i + 1) * step - gap / 2)}
          fill="none"
          strokeWidth={STROKE}
          strokeLinecap="round"
          className={cn(
            "transition-colors duration-300",
            i < inUse ? "stroke-plex-orange" : "stroke-white/20",
          )}
        />
      ))}
      {/* The spinner: a short arc turning in the middle */}
      <g
        className={cn(downloading ? "animate-spin opacity-100" : "opacity-0", "transition-opacity")}
        style={{ transformOrigin: "center" }}
      >
        <path
          d={`M ${SIZE / 2} ${SIZE / 2 - 5} A 5 5 0 0 1 ${SIZE / 2 + 5} ${SIZE / 2}`}
          fill="none"
          strokeWidth={2}
          strokeLinecap="round"
          className="stroke-white/80"
        />
      </g>
    </svg>
  );
}
