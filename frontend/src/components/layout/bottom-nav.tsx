"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, Heart, Film, Tv, Settings } from "lucide-react";
import { useTranslations } from "next-intl";

const navRoutes = [
  { key: "nav.home", href: "/", icon: Home },
  { key: "nav.movies", href: "/movies", icon: Film },
  { key: "nav.series", href: "/series", icon: Tv },
  { key: "nav.watchlist", href: "/watchlist", icon: Heart },
  { key: "nav.settings", href: "/settings", icon: Settings },
];

function isActive(pathname: string, href: string) {
  return pathname === href || (href !== "/" && pathname.startsWith(href));
}

export function BottomNav() {
  const pathname = usePathname();
  const t = useTranslations();

  return (
    <nav
      className="md:hidden landscape:hidden fixed bottom-0 left-0 right-0 z-40 flex items-center justify-around h-16 px-2"
      style={{
        background: "rgba(9, 9, 11, 0.92)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        borderTop: "1px solid rgba(39, 39, 42, 0.5)",
      }}
    >
      {navRoutes.map((item) => {
        const active = isActive(pathname, item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className="flex flex-col items-center gap-1 flex-1 py-2 rounded-[10px] transition-colors"
          >
            <item.icon
              className="h-5 w-5 transition-colors"
              style={{ color: active ? "#e5a00d" : "#a1a1aa" }}
            />
            <span
              className="text-[10px] font-medium leading-none transition-colors"
              style={{ color: active ? "#e5a00d" : "#71717a" }}
            >
              {t(item.key)}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
