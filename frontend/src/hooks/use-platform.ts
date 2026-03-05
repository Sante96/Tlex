"use client";

import { useSyncExternalStore } from "react";

export type Platform = "web" | "tv";

const SESSION_KEY = "tlex_platform";

function getSnapshot(): Platform {
  const params = new URLSearchParams(window.location.search);
  if (params.get("platform") === "tv") {
    sessionStorage.setItem(SESSION_KEY, "tv");
    return "tv";
  }
  return (sessionStorage.getItem(SESSION_KEY) as Platform) ?? "web";
}

function getServerSnapshot(): Platform {
  return "web";
}

function subscribe() {
  return () => {};
}

export function usePlatform(): Platform {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

export function useIsTV(): boolean {
  return usePlatform() === "tv";
}
