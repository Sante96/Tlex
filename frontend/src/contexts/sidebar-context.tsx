"use client";

import { createContext, useContext, useState, useCallback, useEffect } from "react";
import type { ReactNode } from "react";

interface SidebarContextValue {
  isCollapsed: boolean;
  toggleCollapsed: () => void;
  tvExpanded: boolean;
  setTvExpanded: (value: boolean) => void;
  /** The nav entry the page belongs to when its URL says otherwise */
  section: string | null;
  setSection: (href: string | null) => void;
}

const SidebarContext = createContext<SidebarContextValue | null>(null);

function getInitialCollapsed(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem("sidebar-collapsed") === "true";
}

export function SidebarProvider({ children }: { children: ReactNode }) {
  const [isCollapsed, setIsCollapsed] = useState(getInitialCollapsed);
  const [tvExpanded, setTvExpanded] = useState(false);
  const [section, setSection] = useState<string | null>(null);

  const toggleCollapsed = useCallback(() => {
    setIsCollapsed((prev) => {
      const newState = !prev;
      localStorage.setItem("sidebar-collapsed", String(newState));
      return newState;
    });
  }, []);

  return (
    <SidebarContext.Provider
      value={{ isCollapsed, toggleCollapsed, tvExpanded, setTvExpanded, section, setSection }}
    >
      {children}
    </SidebarContext.Provider>
  );
}

export function useSidebar() {
  const context = useContext(SidebarContext);
  if (!context) {
    throw new Error("useSidebar must be used within SidebarProvider");
  }
  return context;
}

/** An anime lives under /series or /media, yet belongs to the Anime entry */
export function useNavSection(href: string | null) {
  const { setSection } = useSidebar();
  useEffect(() => {
    setSection(href);
    return () => setSection(null);
  }, [href, setSection]);
}

/** Whether a nav entry is the current page's */
export function isActive(pathname: string, href: string, section: string | null) {
  if (section) return href === section;
  return pathname === href || (href !== "/" && pathname.startsWith(href));
}
