"use client";

import { useEffect, useRef } from "react";

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
    history.pushState({ tlexOverlay: true }, "");
    let popped = false;
    const onPop = () => {
      popped = true;
      closeRef.current();
    };
    window.addEventListener("popstate", onPop);
    return () => {
      window.removeEventListener("popstate", onPop);
      if (!popped && history.state?.tlexOverlay) history.back();
    };
  }, [open]);
}
