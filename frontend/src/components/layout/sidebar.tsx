"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Home, Heart, Film, Tv, Settings, Menu, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { DSNavItem } from "@/components/ds";
import pkg from "../../../package.json";
import { useSidebar } from "@/contexts/sidebar-context";
import { getScannerStatus } from "@/lib/api";

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
  const { isCollapsed, toggleCollapsed } = useSidebar();
  const [isScanning, setIsScanning] = useState(false);
  const t = useTranslations();

  const sidebarWidth = isCollapsed ? SIDEBAR_COLLAPSED : SIDEBAR_EXPANDED;

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
      transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
      style={{
        background: "rgba(9, 9, 11, 0.80)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        borderRight: "1px solid rgba(39, 39, 42, 0.5)",
        padding: isCollapsed ? "20px 14px" : "20px 16px",
      }}
    >
      {/* Header */}
      <div
        className={`flex items-center h-12 pb-4 ${isCollapsed ? "justify-center" : "gap-3"}`}
      >
        <button
          type="button"
          onClick={toggleCollapsed}
          className="flex items-center justify-center w-10 h-10 rounded-[10px] hover:bg-white/10 transition-colors shrink-0"
        >
          <Menu className="h-[22px] w-[22px] text-[#a1a1aa]" />
        </button>
        {!isCollapsed && (
          <Link
            href="/"
            className="text-2xl font-extrabold tracking-tight text-[#e5a00d]"
          >
            TLEX
          </Link>
        )}
      </div>

      {/* Nav Main */}
      <nav
        className={`flex flex-col gap-1 pt-4 ${isCollapsed ? "items-center" : ""}`}
      >
        {navRoutes.map((item) => (
          <DSNavItem
            key={item.href}
            href={item.href}
            icon={<item.icon className="h-5 w-5" />}
            label={t(item.key)}
            active={isActive(pathname, item.href)}
            collapsed={isCollapsed}
          />
        ))}
      </nav>

      {/* Divider */}
      <div
        className="h-px my-3 bg-[#27272a]"
        style={{ width: isCollapsed ? 40 : "100%", alignSelf: "center" }}
      />

      {/* Library label */}
      {!isCollapsed && (
        <span className="text-[11px] font-semibold uppercase text-[#52525b] tracking-[1px]">
          {t("nav.libraries")}
        </span>
      )}

      {/* Nav Library */}
      <nav
        className={`flex flex-col gap-1 ${isCollapsed ? "items-center" : "mt-2"}`}
      >
        {libraryRoutes.map((item) => (
          <DSNavItem
            key={item.href}
            href={item.href}
            icon={<item.icon className="h-5 w-5" />}
            label={t(item.key)}
            active={isActive(pathname, item.href)}
            collapsed={isCollapsed}
          />
        ))}
      </nav>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Scan indicator */}
      {isScanning && (
        <div
          className={`flex items-center rounded-[10px] mb-3 bg-[#e5a00d]/10 border border-[#e5a00d]/30 ${
            isCollapsed ? "justify-center w-11 h-11" : "gap-2 px-3.5 py-2"
          }`}
          title={isCollapsed ? t("home.scanning") : undefined}
        >
          <Loader2 className="h-4 w-4 animate-spin text-[#e5a00d] shrink-0" />
          {!isCollapsed && (
            <span className="text-xs font-medium text-[#e5a00d]">
              {t("home.scanning")}
            </span>
          )}
        </div>
      )}

      {/* Nav Bottom */}
      <nav
        className={`flex flex-col gap-1 pt-3 ${isCollapsed ? "items-center" : ""}`}
      >
        {bottomRoutes.map((item) => (
          <DSNavItem
            key={item.href}
            href={item.href}
            icon={<item.icon className="h-5 w-5" />}
            label={t(item.key)}
            active={isActive(pathname, item.href)}
            collapsed={isCollapsed}
          />
        ))}
      </nav>
      {/* Credit */}
      {!isCollapsed && (
        <div className="flex flex-row items-center justify-between pt-3 select-none">
          <p className="text-[10px] text-[#3f3f46] tracking-wide">
            {t("common.madeBy")}
          </p>
          <p className="text-[10px] text-[#3f3f46] tracking-wide">
            v{pkg.version}
          </p>
        </div>
      )}
    </motion.aside>
  );
}

export { SIDEBAR_EXPANDED, SIDEBAR_COLLAPSED };
