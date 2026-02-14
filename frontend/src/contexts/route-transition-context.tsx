"use client";

import { useLayoutEffect, useRef } from "react";
import type { ReactNode } from "react";
import { usePathname } from "next/navigation";

const FADE_MS = 200;

/** Sidebar tab routes — no fade transition between these */
const SIDEBAR_ROUTES = new Set([
  "/",
  "/watchlist",
  "/movies",
  "/series",
  "/settings",
]);

function isSidebarRoute(path: string): boolean {
  return SIDEBAR_ROUTES.has(path);
}

/**
 * Route transition using useLayoutEffect to set opacity=0 synchronously
 * before browser paint, then animate to opacity=1 via CSS transition.
 * Only applies when navigating to/from detail routes (not between sidebar tabs).
 */
export function RouteTransitionProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const containerRef = useRef<HTMLDivElement>(null);
  const prevPathRef = useRef(pathname);
  const isFirstRender = useRef(true);

  useLayoutEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }

    if (pathname === prevPathRef.current) return;

    const el = containerRef.current;
    if (!el) return;

    const from = prevPathRef.current;
    prevPathRef.current = pathname;

    // Skip fade between sidebar tabs (Home, Movies, Series, etc.)
    if (isSidebarRoute(from) && isSidebarRoute(pathname)) return;

    // 1. Disable transition so opacity snaps to 0 instantly
    el.style.transition = "none";
    el.style.opacity = "0";

    // 2. Force browser to apply opacity=0 (layout flush)
    el.getBoundingClientRect();

    // 3. Re-enable transition and animate to opacity=1
    requestAnimationFrame(() => {
      el.style.transition = `opacity ${FADE_MS}ms ease-out`;
      el.style.opacity = "1";
    });
  }, [pathname]);

  return (
    <div ref={containerRef} style={{ opacity: 1 }}>
      {children}
    </div>
  );
}
