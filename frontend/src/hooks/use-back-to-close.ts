"use client";

import { useEffect, useRef } from "react";

// How many overlays are open: Back closes only the top one
let openOverlays = 0;

/**
 * While `open`, Back closes the overlay instead of leaving the page: the TV remote's Back
 * (the app's WebView goes back in history), a phone's back gesture, the browser's button.
 * Opening adds a history entry, going back pops it and closes; closing another way
 * (Escape, a click) removes the entry again. Next's router copies its own state into the
 * entry, so popping it doesn't navigate.
 */
export function useBackToClose(open: boolean, close: () => void) {
  const closeRef = useRef(close);
  useEffect(() => {
    closeRef.current = close;
  }, [close]);

  useEffect(() => {
    if (!open) return;
    const level = ++openOverlays;
    let pushed = false;
    let popped = false;
    // A tick later: StrictMode's mount-unmount-mount pushed, went back and pushed again,
    // and the async back() landed on the wrong entry
    const timer = setTimeout(() => {
      history.pushState({ tlexOverlay: level }, "");
      pushed = true;
    });
    const onPop = () => {
      // Back from an overlay opened on top of this one lands on this one's entry
      if ((history.state?.tlexOverlay ?? 0) >= level) return;
      popped = true;
      closeRef.current();
    };
    window.addEventListener("popstate", onPop);
    return () => {
      openOverlays--;
      clearTimeout(timer);
      window.removeEventListener("popstate", onPop);
      if (pushed && !popped && history.state?.tlexOverlay === level)
        history.back();
    };
  }, [open]);
}
