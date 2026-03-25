"use client";

import { useSyncExternalStore } from "react";

export type Platform = "web" | "tv";
export type TVTier = "720" | "1080" | "4k";

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

function getTierSnapshot(): TVTier {
  const physical = window.screen.width * window.devicePixelRatio;
  if (physical >= 3840) return "4k";
  if (physical >= 1920) return "1080";
  return "720";
}

function getTierServerSnapshot(): TVTier {
  return "1080";
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

export function useTVTier(): TVTier | null {
  const isTV = useIsTV();
  const tier = useSyncExternalStore(subscribe, getTierSnapshot, getTierServerSnapshot);
  return isTV ? tier : null;
}
