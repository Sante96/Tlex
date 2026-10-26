"use client";

import { useEffect, useEffectEvent } from "react";
import { E, L, T, VIEW_BOX, X_ARM, X_STROKE } from "@/components/tlex-wordmark";

const LETTERS = [T, L, E];
// The lit copy's, 15% wider on each side: its glow fits inside (globals.css, .splash-lit)
const LIT_VIEW_BOX = `${485 - 0.15 * 1790} ${505 - 0.15 * 515} ${1.3 * 1790} ${1.3 * 515}`;

/** Until the screen has faded out: the timeline is in globals.css ("The splash") */
const DURATION_MS = 3300;

/**
 * The first screen of a session: T, L and E rise along their slant, the X's blue arm
 * lands on its orange stroke, and from where they meet the light runs back across the
 * word. It grows with the screen, from a phone to the TV.
 */
export function SplashScreen({ onComplete }: { onComplete: () => void }) {
  const complete = useEffectEvent(onComplete);
  useEffect(() => {
    const timer = setTimeout(complete, DURATION_MS);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div
      role="img"
      aria-label="TLEX"
      className="splash fixed inset-0 z-50 flex items-center justify-center pb-[8vh]"
    >
      <div className="splash-exit relative w-[min(8rem_+_30vw,36rem)] aspect-1790/515">
        <div className="splash-glow" />
        <div className="splash-bump absolute inset-0">
          {/* Unlit: the letters come up through the baseline */}
          <svg viewBox={VIEW_BOX} className="absolute inset-0 size-full overflow-visible">
            <clipPath id="splash-baseline">
              <rect x="0" y="0" width="3000" height="1004" />
            </clipPath>
            <g clipPath="url(#splash-baseline)" fill="#fff" fillOpacity={0.3}>
              {LETTERS.map((d, i) => (
                <path key={i} d={d} className="splash-rise" style={{ animationDelay: `${150 + i * 100}ms` }} />
              ))}
              <path d={X_STROKE} fill="#db9d10" className="splash-x" />
            </g>
            <path d={X_ARM} fill="#08c" className="splash-arm" />
          </svg>
          {/* Lit: uncovered from the X to the T */}
          <svg viewBox={LIT_VIEW_BOX} fill="#fff" className="splash-lit">
            {LETTERS.map((d, i) => (
              <path key={i} d={d} />
            ))}
          </svg>
          <div className="splash-bloom" />
        </div>
      </div>
    </div>
  );
}
