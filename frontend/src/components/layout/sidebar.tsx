"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Home, Heart, Film, Tv, Settings, Menu, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { DSNavItem, DSIconButton } from "@/components/ds";
import Image from "next/image";
import pkg from "../../../package.json";
import { useSidebar } from "@/contexts/sidebar-context";
import { useIsTV } from "@/hooks/use-platform";
import { getScannerStatus } from "@/lib/api";
import type { FocusEvent } from "react";

const SIDEBAR_EXPANDED = 260;
const SIDEBAR_COLLAPSED = 72;

const navRoutes = [
  { key: "nav.home", href: "/", icon: Home },
  { key: "nav.watchlist", href: "/watchlist", icon: Heart },
];

const libraryRoutes = [
  { key: "nav.movies", href: "/movies", icon: Film },
  { key: "nav.series", href: "/series", icon: Tv },
];

const bottomRoutes = [
  { key: "nav.settings", href: "/settings", icon: Settings },
];

function isActive(pathname: string, href: string) {
  return pathname === href || (href !== "/" && pathname.startsWith(href));
}

export function Sidebar() {
  const pathname = usePathname();
  const { isCollapsed, toggleCollapsed, tvExpanded, setTvExpanded } = useSidebar();
  const [isScanning, setIsScanning] = useState(false);
  const t = useTranslations();
  const isTV = useIsTV();

  const collapsed = isTV ? !tvExpanded : isCollapsed;
  const sidebarWidth = collapsed ? SIDEBAR_COLLAPSED : SIDEBAR_EXPANDED;

  const handleTvFocus = () => {
    if (isTV) setTvExpanded(true);
  };

  const handleTvBlur = (e: FocusEvent<HTMLElement>) => {
    if (isTV && !e.currentTarget.contains(e.relatedTarget as Node)) {
      setTvExpanded(false);
    }
  };

  useEffect(() => {
    const checkScanStatus = async () => {
      try {
        const status = await getScannerStatus();
        setIsScanning(status.is_scanning);
      } catch {}
    };

    checkScanStatus();
    const interval = setInterval(checkScanStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <motion.aside
      className="hidden md:flex fixed left-0 top-0 h-screen flex-col z-40 overflow-hidden"
      animate={{ width: sidebarWidth }}
      transition={collapsed
        ? { duration: 0.25, ease: [0.4, 0, 0.2, 1], delay: 0.1 }
        : { duration: 0.25, ease: [0.4, 0, 0.2, 1] }
      }
      onFocus={handleTvFocus}
      onBlur={handleTvBlur}
      style={{
        background: "rgba(9, 9, 11, 0.80)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        borderRight: "1px solid rgba(39, 39, 42, 0.5)",
        padding: "20px 14px",
      }}
    >
      {/* Header */}
      <div className="flex items-center gap-3 h-12 pb-4">
        {isTV ? (
          collapsed ? (
            <Link
              href="/"
              className="flex items-center justify-center w-10 h-10 rounded-[10px] flex-shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#e5a00d]"
            >
              <Image src="/tlex-icon.svg" alt="TLEX" width={32} height={32} unoptimized />
            </Link>
          ) : (
            <Link
              href="/"
              className="flex items-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#e5a00d] rounded-[10px]"
            >
              <Image src="/tlex-logo.svg" alt="TLEX" width={200} height={58} className="h-8 w-auto" unoptimized />
            </Link>
          )
        ) : (
          <>
            <DSIconButton
              onClick={toggleCollapsed}
              icon={<Menu className="h-[22px] w-[22px]" />}
              className="w-10 h-10 flex-shrink-0"
            />
            <Link
              href="/"
              className="flex items-center whitespace-nowrap"
              style={{
                opacity: collapsed ? 0 : 1,
                transition: collapsed ? "opacity 0.08s ease" : "opacity 0.15s ease 0.12s",
              }}
            >
              <Image src="/tlex-logo.svg" alt="TLEX" width={200} height={58} className="h-7 w-auto" unoptimized />
            </Link>
          </>
        )}
      </div>

      {/* Nav Main */}
      <nav className="flex flex-col gap-1 pt-4">
        {navRoutes.map((item) => (
          <DSNavItem
            key={item.href}
            href={item.href}
            icon={<item.icon className={isTV ? "h-6 w-6" : "h-5 w-5"} />}
            label={t(item.key)}
            active={isActive(pathname, item.href)}
            collapsed={collapsed}
            tvMode={isTV}
          />
        ))}
      </nav>

      {/* Divider */}
      <div className="h-px my-3 bg-[#27272a]" />

      {/* Library label */}
      <span
        className="text-[11px] font-semibold uppercase text-[#52525b] tracking-[1px] whitespace-nowrap"
        style={{
          opacity: collapsed ? 0 : 1,
          transition: collapsed ? "opacity 0.08s ease" : "opacity 0.15s ease 0.12s",
        }}
      >
        {t("nav.libraries")}
      </span>

      {/* Nav Library */}
      <nav className="flex flex-col gap-1 mt-2">
        {libraryRoutes.map((item) => (
          <DSNavItem
            key={item.href}
            href={item.href}
            icon={<item.icon className={isTV ? "h-6 w-6" : "h-5 w-5"} />}
            label={t(item.key)}
            active={isActive(pathname, item.href)}
            collapsed={collapsed}
            tvMode={isTV}
          />
        ))}
      </nav>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Scan indicator */}
      {isScanning && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-[10px] mb-3 bg-[#e5a00d]/10 border border-[#e5a00d]/30">
          <Loader2 className="h-4 w-4 animate-spin text-[#e5a00d] flex-shrink-0" />
          <span
            className="text-xs font-medium text-[#e5a00d] whitespace-nowrap"
            style={{
              opacity: collapsed ? 0 : 1,
              transition: collapsed ? "opacity 0.08s ease" : "opacity 0.15s ease 0.12s",
            }}
          >
            {t("home.scanning")}
          </span>
        </div>
      )}

      {/* Nav Bottom */}
      <nav className="flex flex-col gap-1 pt-3">
        {bottomRoutes.map((item) => (
          <DSNavItem
            key={item.href}
            href={item.href}
            icon={<item.icon className={isTV ? "h-6 w-6" : "h-5 w-5"} />}
            label={t(item.key)}
            active={isActive(pathname, item.href)}
            collapsed={collapsed}
            tvMode={isTV}
          />
        ))}
      </nav>
      {/* Credit */}
      <div
        className="flex flex-row items-center justify-between pt-3 select-none"
        style={{
          opacity: collapsed ? 0 : 1,
          transition: collapsed ? "opacity 0.08s ease" : "opacity 0.15s ease 0.12s",
        }}
      >
        <p className="text-[10px] text-[#3f3f46] tracking-wide whitespace-nowrap">{t("common.madeBy")}</p>
        <p className="text-[10px] text-[#3f3f46] tracking-wide whitespace-nowrap">v{pkg.version}</p>
      </div>
    </motion.aside>
  );
}

export { SIDEBAR_EXPANDED, SIDEBAR_COLLAPSED };
