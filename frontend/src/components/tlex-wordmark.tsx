"use client";

import { NAV_FADE_EASE } from "@/components/ds/nav-item";

// The wordmark of public/tlex-logo.svg, one path per letter: each moves on its own
export const T =
  "M508.42,656.17c-11.34,0-14.83-5.66-10.46-17l35.97-88.94c5.23-11.77,13.29-17.66,24.2-17.66h410.71c12.2,0,15.7,5.89,10.46,17.66l-35.97,88.94c-4.36,11.34-12.43,17-24.2,17h-410.71ZM753.67,684.29c11.33,0,14.82,5.67,10.46,17l-115.1,284.49c-5.23,11.77-13.3,17.66-24.2,17.66h-102.68c-12.21,0-15.7-5.89-10.46-17.66l115.1-284.49c4.35-11.33,12.43-17,24.2-17h102.68Z";
export const L =
  "M1201.66,879.83c11.77,0,15.47,5.67,11.12,17l-35.97,88.94c-5.23,11.77-13.52,17.66-24.85,17.66h-317.19c-11.77,0-15.04-5.89-9.81-17.66l175.93-435.56c5.23-11.77,13.29-17.66,24.2-17.66h103.33c11.77,0,15.04,5.89,9.81,17.66l-130.8,323.08c-1.31,4.36,0,6.54,3.92,6.54h190.31Z";
export const E =
  "M1627.41,879.83c11.33,0,14.82,5.67,10.46,17l-35.97,88.94c-5.23,11.77-13.3,17.66-24.2,17.66h-360.35c-11.77,0-15.04-5.89-9.81-17.66l175.93-435.56c5.23-11.77,13.29-17.66,24.2-17.66h360.35c11.77,0,15.04,5.89,9.81,17.66l-35.97,88.94c-4.36,11.34-12.21,17-23.54,17h-234.79c-4.8,0-7.85,2.19-9.16,6.54l-85.67,210.59c-1.31,4.36,0,6.54,3.92,6.54h234.79ZM1476.33,732.68c5.23-11.77,13.29-17.66,24.2-17.66h164.81c11.77,0,15.04,5.89,9.81,17.66l-28.12,70.63c-5.23,11.77-13.3,17.66-24.2,17.66h-164.81c-11.77,0-15.04-5.89-9.81-17.66l28.12-70.63Z";
// The X: the orange stroke, and the blue arm (Telegram's) that lands on it
export const X_STROKE =
  "M2018.79,768.33l-54.58-223.99c-2.19-7.41-8.29-11.12-18.31-11.12h-134.07c-14.83,0-20.71,6.33-17.66,18.97l51.67,209.28c1.31,3.92.21,7.63-3.27,11.12l-223.01,211.9c-3.92,3.49-6.75,7.52-8.5,12.1-1.74,4.58,1.96,6.87,11.12,6.87h132.76c9.58,0,18.53-4.14,26.81-12.43l105.29-111.18,17,111.18c1.31,8.29,6.75,12.43,16.35,12.43h132.76c15.26,0,21.36-6.32,18.31-18.97l-52.67-216.15Z";
export const X_ARM =
  "M2024.37,605.81l58.21-60.17c7.85-8.28,16.57-12.43,26.16-12.43h134.07c10.02,0,14.28,1.96,12.75,5.89-1.53,3.92-4.69,8.29-9.48,13.08l-185.08,171.35c-5.67,5.67-10.69,8.5-15.04,8.5-3.92,0-6.54-2.83-7.85-8.5l-22.89-92.21c-2.19-8.72.87-17.22,9.16-25.51Z";
export const VIEW_BOX = "485 505 1790 515";

// The X's two pieces go as one letter
const LETTERS = [
  [{ d: T, fill: "#fff" }],
  [{ d: L, fill: "#fff" }],
  [{ d: E, fill: "#fff" }],
  [
    { d: X_STROKE, fill: "#db9d10" },
    { d: X_ARM, fill: "#08c" },
  ],
];
const LETTER_S = 0.15;
const STAGGER_S = 0.05;

/**
 * The TLEX wordmark, a letter at a time as the sidebar closes and opens (0.3 s, its own
 * motion): closing, the X goes first, as the edge reaches it; opening, the T comes first.
 */
export function TlexWordmark({ hidden, className }: { hidden: boolean; className?: string }) {
  return (
    <svg viewBox={VIEW_BOX} role="img" aria-label="TLEX" className={className}>
      {LETTERS.map((pieces, i) => {
        const delay = (hidden ? LETTERS.length - 1 - i : i) * STAGGER_S;
        return (
          <g
            key={i}
            style={{
              opacity: hidden ? 0 : 1,
              transform: hidden ? "translateX(-60px)" : "none",
              transition: `opacity ${LETTER_S}s ${NAV_FADE_EASE} ${delay}s, transform ${LETTER_S}s ${NAV_FADE_EASE} ${delay}s`,
            }}
          >
            {pieces.map((piece) => (
              <path key={piece.fill} d={piece.d} fill={piece.fill} />
            ))}
          </g>
        );
      })}
    </svg>
  );
}
