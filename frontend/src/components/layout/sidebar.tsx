"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Home, Heart, Film, Tv, Music, Download, Settings, Menu, Loader2, Origami } from "lucide-react";
import { useTranslations } from "next-intl";
import { DSNavItem, DSIconButton } from "@/components/ds";
import { NAV_FADE, NAV_MOTION } from "@/components/ds/nav-item";
import { TlexWordmark } from "@/components/tlex-wordmark";
import Image from "next/image";
import pkg from "../../../package.json";
import { isActive, useSidebar } from "@/contexts/sidebar-context";
import { useIsTV, useTVTier, type TVTier } from "@/hooks/use-platform";
import { getScannerStatus } from "@/lib/api";
import { useIsMobile, useIsTablet } from "@/lib/breakpoints";
import type { FocusEvent } from "react";

const SIDEBAR_EXPANDED = 260;
const SIDEBAR_COLLAPSED = 72;

export const TV_WIDTHS: Record<TVTier, { expanded: number; collapsed: number }> = {
  "720":  { expanded: 200, collapsed: 56 },
  "1080": { expanded: 220, collapsed: 64 },
  "4k":   { expanded: 260, collapsed: 72 },
};

// Horizontal padding per tier — determines icon column size when collapsed
const TV_PADDINGS: Record<TVTier, { v: number; h: number }> = {
  "720":  { v: 12, h: 10 },
  "1080": { v: 14, h: 12 },
  "4k":   { v: 20, h: 14 },
};

const navRoutes = [
  { key: "nav.home", href: "/", icon: Home },
  { key: "nav.watchlist", href: "/watchlist", icon: Heart },
];

const libraryRoutes = [
  { key: "nav.movies", href: "/movies", icon: Film },
  { key: "nav.series", href: "/series", icon: Tv },
  { key: "nav.anime", href: "/anime", icon: Origami },
  { key: "nav.concerts", href: "/concerts", icon: Music },
];

const bottomRoutes = [
  { key: "nav.downloads", href: "/downloads", icon: Download },
  { key: "nav.settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { isCollapsed, toggleCollapsed, tvExpanded, setTvExpanded, section } = useSidebar();
  const [isScanning, setIsScanning] = useState(false);
  const t = useTranslations();
  const isTV = useIsTV();
  const isMobile = useIsMobile();
  // An upright iPad: open, the sidebar took a third of the width. There it's a rail that
  // opens over the page, and closes on the next page (opened on this one only) or a tap out
  const isTablet = useIsTablet() && !isTV;
  const [openOn, setOpenOn] = useState<string | null>(null);
  const tabletOpen = openOn === pathname;

  const tvTier = useTVTier();
  const tvWidths = TV_WIDTHS[tvTier ?? "1080"];
  const tvPad = TV_PADDINGS[tvTier ?? "1080"];
  // Icon column fills the full inner width of the collapsed sidebar
  const tvIconCol = tvWidths.collapsed - tvPad.h * 2;
  const collapsed = isTV ? !tvExpanded : isTablet ? !tabletOpen : isCollapsed;
  const toggle = isTablet ? () => setOpenOn(tabletOpen ? null : pathname) : toggleCollapsed;
  const sidebarWidth = isTV
    ? (collapsed ? tvWidths.collapsed : tvWidths.expanded)
    : (collapsed ? SIDEBAR_COLLAPSED : SIDEBAR_EXPANDED);

  const handleTvFocus = () => {
    if (isTV) setTvExpanded(true);
  };

  const handleTvBlur = (e: FocusEvent<HTMLElement>) => {
    if (isTV && !e.currentTarget.contains(e.relatedTarget as Node)) {
      setTvExpanded(false);
    }
  };

  // Only while someone can see it: phones hide the sidebar, and a background tab polled
  // the backend every 5 s all day
  useEffect(() => {
    if (isMobile) return;
    const checkScanStatus = async () => {
      if (document.hidden) return;
      try {
        const status = await getScannerStatus();
        setIsScanning(status.is_scanning);
      } catch {}
    };

    checkScanStatus();
    const interval = setInterval(checkScanStatus, 5000);
    return () => clearInterval(interval);
  }, [isMobile]);

  return (
    <>
    {isTablet && tabletOpen && (
      // Over the page: a tap outside closes it
      <div className="hidden md:block fixed inset-0 z-30" onClick={() => setOpenOn(null)} />
    )}
    <motion.aside
      className="vt-sidebar hidden md:flex fixed left-0 top-0 h-screen flex-col z-40 overflow-hidden"
      // Mounted at its saved width: it grew or shrank from its content's width on every
      // reload and profile switch
      initial={false}
      animate={{ width: sidebarWidth }}
      // One motion: the page's margin, the labels and the wordmark go with it
      transition={NAV_MOTION}
      onFocus={handleTvFocus}
      onBlur={handleTvBlur}
      style={{
        background: "rgba(9, 9, 11, 0.80)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        borderRight: "1px solid rgba(39, 39, 42, 0.5)",
        padding: isTV
          ? `${tvPad.v}px ${tvPad.h}px`
          : "calc(20px + env(safe-area-inset-top, 0px)) 14px 20px",
        // Clear of the notch held sideways, of the status bar opened from the home screen
        left: "env(safe-area-inset-left, 0px)",
      }}
    >
      {/* Header */}
      <div className={isTV
        ? "flex items-center gap-2 tv-1080:gap-3 h-10 tv-1080:h-12 tv-4k:h-14 pb-2 tv-1080:pb-3 tv-4k:pb-4"
        : "flex items-center gap-3 h-12 pb-4"
      }>
        {isTV ? (
          // Closed, the X icon; opening, it fades as the letters come in
          <Link
            href="/"
            className="relative flex items-center h-9 tv-1080:h-10 shrink-0 rounded-[10px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-plex-orange"
          >
            <Image
              src="/tlex-icon.svg"
              alt=""
              width={32}
              height={32}
              className="absolute left-1.5 w-6 h-6 tv-1080:w-7 tv-1080:h-7 tv-4k:w-8 tv-4k:h-8"
              style={{ opacity: collapsed ? 1 : 0, transition: NAV_FADE }}
              unoptimized
            />
            <TlexWordmark hidden={collapsed} className="h-7 tv-1080:h-8 tv-4k:h-10 w-auto" />
          </Link>
        ) : (
          <>
            <DSIconButton
              onClick={toggle}
              aria-label={collapsed ? t("nav.expandMenu") : t("nav.collapseMenu")}
              aria-expanded={!collapsed}
              icon={<Menu className="h-[22px] w-[22px]" />}
              className="w-10 h-10 flex-shrink-0"
            />
            <Link href="/" className="flex items-center whitespace-nowrap">
              <TlexWordmark hidden={collapsed} className="h-7 w-auto" />
            </Link>
          </>
        )}
      </div>

      {/* Nav Main */}
      <nav className="flex flex-col gap-1 pt-3 tv-1080:pt-4 tv-4k:pt-5">
        {navRoutes.map((item) => (
          <DSNavItem
            key={item.href}
            href={item.href}
            icon={<item.icon className={isTV ? "h-5 w-5 tv-1080:h-6 tv-1080:w-6 tv-4k:h-6 tv-4k:w-6" : "h-5 w-5"} />}
            label={t(item.key)}
            active={isActive(pathname, item.href, section)}
            collapsed={collapsed}
            tvMode={isTV}
            iconColumn={isTV ? tvIconCol : undefined}
          />
        ))}
      </nav>

      {/* Divider */}
      <div className="h-px my-2 tv-1080:my-3 tv-4k:my-4 bg-[#27272a]" />

      {/* Library label */}
      <span
        className="text-[11px] tv-4k:text-xs font-semibold uppercase text-[#52525b] tracking-[1px] whitespace-nowrap"
        style={{ opacity: collapsed ? 0 : 1, transition: NAV_FADE }}
      >
        {t("nav.libraries")}
      </span>

      {/* Nav Library */}
      <nav className="flex flex-col gap-1 mt-1 tv-1080:mt-2 tv-4k:mt-3">
        {libraryRoutes.map((item) => (
          <DSNavItem
            key={item.href}
            href={item.href}
            icon={<item.icon className={isTV ? "h-5 w-5 tv-1080:h-6 tv-1080:w-6 tv-4k:h-6 tv-4k:w-6" : "h-5 w-5"} />}
            label={t(item.key)}
            active={isActive(pathname, item.href, section)}
            collapsed={collapsed}
            tvMode={isTV}
            iconColumn={isTV ? tvIconCol : undefined}
          />
        ))}
      </nav>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Scan indicator */}
      {isScanning && (
        <div className="flex items-center gap-2 px-2 tv-1080:px-3 py-1.5 tv-1080:py-2 rounded-[10px] mb-2 tv-1080:mb-3 bg-plex-orange/10 border border-plex-orange/30">
          <Loader2 className="h-4 w-4 animate-spin text-plex-orange flex-shrink-0" />
          <span
            className="text-xs font-medium text-plex-orange whitespace-nowrap"
            style={{ opacity: collapsed ? 0 : 1, transition: NAV_FADE }}
          >
            {t("home.scanning")}
          </span>
        </div>
      )}

      {/* Nav Bottom */}
      <nav className="flex flex-col gap-1 pt-2 tv-1080:pt-3 tv-4k:pt-4">
        {bottomRoutes.map((item) => (
          <DSNavItem
            key={item.href}
            href={item.href}
            icon={<item.icon className={isTV ? "h-5 w-5 tv-1080:h-6 tv-1080:w-6 tv-4k:h-6 tv-4k:w-6" : "h-5 w-5"} />}
            label={t(item.key)}
            active={isActive(pathname, item.href, section)}
            collapsed={collapsed}
            tvMode={isTV}
            iconColumn={isTV ? tvIconCol : undefined}
          />
        ))}
      </nav>
      {/* Credit */}
      <div
        className="flex flex-row items-center justify-between pt-2 tv-1080:pt-3 tv-4k:pt-4 select-none"
        style={{ opacity: collapsed ? 0 : 1, transition: NAV_FADE }}
      >
        <p className="text-[10px] tv-4k:text-[11px] text-[#3f3f46] tracking-wide whitespace-nowrap">{t("common.madeBy")}</p>
        <p className="text-[10px] tv-4k:text-[11px] text-[#3f3f46] tracking-wide whitespace-nowrap">v{pkg.version}</p>
      </div>
    </motion.aside>
    </>
  );
}

export { SIDEBAR_EXPANDED, SIDEBAR_COLLAPSED };
