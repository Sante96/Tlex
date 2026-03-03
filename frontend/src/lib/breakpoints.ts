import { useState, useEffect } from "react";

export const BREAKPOINTS = {
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  "2xl": 1536,
} as const;

export type Breakpoint = keyof typeof BREAKPOINTS;

export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.matchMedia(`(max-width: ${BREAKPOINTS.md - 1}px)`).matches;
  });

  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${BREAKPOINTS.md - 1}px)`);
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  return isMobile;
}

export function useBreakpoint(bp: Breakpoint): boolean {
  const [isAbove, setIsAbove] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.matchMedia(`(min-width: ${BREAKPOINTS[bp]}px)`).matches;
  });

  useEffect(() => {
    const mq = window.matchMedia(`(min-width: ${BREAKPOINTS[bp]}px)`);
    const handler = (e: MediaQueryListEvent) => setIsAbove(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [bp]);

  return isAbove;
}
