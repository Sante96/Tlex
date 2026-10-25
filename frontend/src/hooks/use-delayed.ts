"use client";

import { useEffect, useState } from "react";

/**
 * True once `active` has stayed true for `ms`: the loader or skeleton of a load that ends
 * sooner never shows. On the LAN the data lands in about 100 ms, and a skeleton flashed
 * for a few frames before the page, which then jumped into place.
 */
export function useDelayed(active: boolean, ms = 200): boolean {
  const [elapsed, setElapsed] = useState(false);
  useEffect(() => {
    if (!active) return;
    const timer = setTimeout(() => setElapsed(true), ms);
    return () => {
      clearTimeout(timer);
      setElapsed(false);
    };
  }, [active, ms]);
  return active && elapsed;
}
