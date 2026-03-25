"use client";

import { useEffect } from "react";
import { useIsTV, useTVTier } from "@/hooks/use-platform";

/**
 * Locks the viewport to width=1920 on TV and keeps it locked via a
 * MutationObserver that immediately restores the value if Next.js head
 * reconciliation resets it during SPA navigation.
 *
 * Why MutationObserver instead of re-running on pathname change:
 * Adding pathname to the effect deps causes a visible large→small flash
 * because the effect runs one render cycle *after* React has already
 * written the default viewport to the DOM. The MutationObserver fires
 * synchronously (microtask) before the browser performs a reflow, so the
 * user never sees the intermediate state.
 *
 * Why data-tv-tier: sets the CSS tier breakpoint variants (tv-720:,
 * tv-1080:, tv-4k:) for Tailwind without requiring per-component JS.
 */
export function TVViewportEffect() {
  const isTV = useIsTV();
  const tier = useTVTier();

  useEffect(() => {
    if (!isTV) return;

    if (tier) document.documentElement.dataset.tvTier = tier;

    const meta = document.querySelector(
      'meta[name="viewport"]',
    ) as HTMLMetaElement | null;
    if (!meta) return;

    const scale = Math.round((window.screen.width / 1920) * 1000) / 1000;
    const content = [
      "width=1920",
      `initial-scale=${scale}`,
      `minimum-scale=${scale}`,
      `maximum-scale=${scale}`,
      "user-scalable=no",
    ].join(", ");

    meta.content = content;

    // React's head reconciler resets the viewport meta on every route change.
    // The observer fires synchronously before the browser reflows, so the
    // correction is invisible to the user.
    const observer = new MutationObserver(() => {
      if (meta.content !== content) meta.content = content;
    });

    observer.observe(meta, { attributes: true, attributeFilter: ["content"] });

    return () => observer.disconnect();
  }, [isTV, tier]);

  return null;
}
