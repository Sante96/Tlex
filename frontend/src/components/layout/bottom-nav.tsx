"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { Home, Heart, Film, Tv, Music, Origami } from "lucide-react";
import { useTranslations } from "next-intl";
import { isActive, useSidebar } from "@/contexts/sidebar-context";

// Settings live in the avatar's menu (top bar): a seventh item was too narrow
const navRoutes = [
  { key: "nav.home", href: "/", icon: Home },
  { key: "nav.movies", href: "/movies", icon: Film },
  { key: "nav.series", href: "/series", icon: Tv },
  { key: "nav.anime", href: "/anime", icon: Origami },
  { key: "nav.concerts", href: "/concerts", icon: Music },
  { key: "nav.watchlist", href: "/watchlist", icon: Heart },
];

/**
 * The phone's navigation: a glass capsule floating above the home indicator, clear of the
 * screen's rounded corners (its own round ends follow them); the active item sits on a
 * pill that slides from one to the next.
 */
export function BottomNav() {
  const pathname = usePathname();
  const { section } = useSidebar();
  const t = useTranslations();

  return (
    <nav
      className="vt-bottombar md:hidden landscape:hidden fixed z-40 flex items-center p-1.5 rounded-full border border-white/10 shadow-[0_12px_40px_rgba(0,0,0,0.55)]"
      style={{
        height: "var(--bottom-nav-h)",
        bottom: "var(--bottom-nav-gap)",
        left: "calc(12px + env(safe-area-inset-left, 0px))",
        right: "calc(12px + env(safe-area-inset-right, 0px))",
        background: "rgba(18, 18, 20, 0.72)",
        backdropFilter: "blur(24px) saturate(160%)",
        WebkitBackdropFilter: "blur(24px) saturate(160%)",
      }}
    >
      {navRoutes.map((item) => {
        const active = isActive(pathname, item.href, section);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className="relative flex flex-col items-center justify-center gap-1 flex-1 h-full rounded-full outline-none focus-visible:ring-2 focus-visible:ring-plex-orange"
          >
            {active && (
              <motion.span
                layoutId="bottom-nav-active"
                className="absolute inset-0 rounded-full bg-plex-orange/15"
                transition={{ type: "spring", stiffness: 500, damping: 38 }}
              />
            )}
            <item.icon
              className="relative h-5 w-5 transition-colors"
              style={{ color: active ? "#e5a00d" : "#a1a1aa" }}
            />
            <span
              className="relative text-[10px] font-medium leading-none transition-colors"
              style={{ color: active ? "#e5a00d" : "#a1a1aa" }}
            >
              {t(item.key)}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
