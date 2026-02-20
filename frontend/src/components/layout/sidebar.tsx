"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Home, Heart, Film, Tv, Settings, Menu, Loader2 } from "lucide-react";
import { DSNavItem } from "@/components/ds";
import { useSidebar } from "@/contexts/sidebar-context";
import { getScannerStatus } from "@/lib/api";

const SIDEBAR_EXPANDED = 260;
const SIDEBAR_COLLAPSED = 72;

const navItems = [
  { label: "Home", href: "/", icon: Home },
  { label: "Watchlist", href: "/watchlist", icon: Heart },
];

const libraryItems = [
  { label: "Film", href: "/movies", icon: Film },
  { label: "Serie TV", href: "/series", icon: Tv },
];

const bottomItems = [
  { label: "Impostazioni", href: "/settings", icon: Settings },
];

function isActive(pathname: string, href: string) {
  return pathname === href || (href !== "/" && pathname.startsWith(href));
}

export function Sidebar() {
  const pathname = usePathname();
  const { isCollapsed, toggleCollapsed } = useSidebar();
  const [isScanning, setIsScanning] = useState(false);

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
      className="fixed left-0 top-0 h-screen flex flex-col z-40 overflow-hidden"
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
        {navItems.map((item) => (
          <DSNavItem
            key={item.href}
            href={item.href}
            icon={<item.icon className="h-5 w-5" />}
            label={item.label}
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
          Librerie
        </span>
      )}

      {/* Nav Library */}
      <nav
        className={`flex flex-col gap-1 ${isCollapsed ? "items-center" : "mt-2"}`}
      >
        {libraryItems.map((item) => (
          <DSNavItem
            key={item.href}
            href={item.href}
            icon={<item.icon className="h-5 w-5" />}
            label={item.label}
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
          title={isCollapsed ? "Scansione..." : undefined}
        >
          <Loader2 className="h-4 w-4 animate-spin text-[#e5a00d] shrink-0" />
          {!isCollapsed && (
            <span className="text-xs font-medium text-[#e5a00d]">
              Scansione...
            </span>
          )}
        </div>
      )}

      {/* Divider */}
      <div
        className="h-px bg-[#27272a]"
        style={{ width: isCollapsed ? 40 : "100%", alignSelf: "center" }}
      />

      {/* Nav Bottom */}
      <nav
        className={`flex flex-col gap-1 pt-3 ${isCollapsed ? "items-center" : ""}`}
      >
        {bottomItems.map((item) => (
          <DSNavItem
            key={item.href}
            href={item.href}
            icon={<item.icon className="h-5 w-5" />}
            label={item.label}
            active={isActive(pathname, item.href)}
            collapsed={isCollapsed}
          />
        ))}
      </nav>
    </motion.aside>
  );
}

export { SIDEBAR_EXPANDED, SIDEBAR_COLLAPSED };
