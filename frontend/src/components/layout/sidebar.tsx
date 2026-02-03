"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home,
  Heart,
  Film,
  Tv,
  Settings,
  Menu,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useSidebar } from "@/contexts/sidebar-context";

const SIDEBAR_WIDTH_EXPANDED = 200;
const SIDEBAR_WIDTH_COLLAPSED = 64;

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
}

const navItems: NavItem[] = [
  { label: "Home", href: "/", icon: Home },
  { label: "Watchlist", href: "/watchlist", icon: Heart },
];

const libraryItems: NavItem[] = [
  { label: "Film", href: "/movies", icon: Film },
  { label: "Serie TV", href: "/series", icon: Tv },
];

const bottomItems: NavItem[] = [
  { label: "Impostazioni", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { isCollapsed, toggleCollapsed } = useSidebar();

  const width = isCollapsed ? SIDEBAR_WIDTH_COLLAPSED : SIDEBAR_WIDTH_EXPANDED;

  return (
    <aside
      className="fixed left-0 top-0 h-screen bg-sidebar flex flex-col z-40 transition-all duration-300"
      style={{ width }}
    >
      {/* Header with hamburger and logo */}
      <div className="flex items-center h-14 px-3 gap-2">
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleCollapsed}
          className="shrink-0 text-sidebar-foreground hover:bg-sidebar-accent"
        >
          <Menu className="h-5 w-5" />
        </Button>
        {!isCollapsed && (
          <Link href="/" className="text-xl font-bold text-plex-orange">
            TLEX
          </Link>
        )}
      </div>

      {/* Main navigation */}
      <nav className="flex-1 py-2 overflow-y-auto">
        <NavSection
          items={navItems}
          pathname={pathname}
          isCollapsed={isCollapsed}
        />

        <div className="my-2 mx-3 h-px bg-sidebar-border" />

        {!isCollapsed && (
          <div className="px-3 py-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Librerie
          </div>
        )}
        <NavSection
          items={libraryItems}
          pathname={pathname}
          isCollapsed={isCollapsed}
        />
      </nav>

      {/* Bottom section */}
      <div className="py-2 border-t border-sidebar-border">
        <NavSection
          items={bottomItems}
          pathname={pathname}
          isCollapsed={isCollapsed}
        />
      </div>
    </aside>
  );
}

interface NavSectionProps {
  items: NavItem[];
  pathname: string;
  isCollapsed: boolean;
}

function NavSection({ items, pathname, isCollapsed }: NavSectionProps) {
  return (
    <ul className="space-y-1 px-2">
      {items.map((item) => {
        const isActive =
          pathname === item.href ||
          (item.href !== "/" && pathname.startsWith(item.href));
        const Icon = item.icon;

        return (
          <li key={item.href}>
            <Link
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md transition-colors",
                "hover:bg-sidebar-accent",
                isActive && "bg-sidebar-accent text-plex-orange",
                !isActive && "text-sidebar-foreground",
                isCollapsed && "justify-center px-2",
              )}
              title={isCollapsed ? item.label : undefined}
            >
              <Icon
                className={cn(
                  "h-5 w-5 shrink-0",
                  isActive && "text-plex-orange",
                )}
              />
              {!isCollapsed && (
                <span
                  className={cn(
                    "text-sm font-medium",
                    isActive && "text-plex-orange",
                  )}
                >
                  {item.label}
                </span>
              )}
              {!isCollapsed && isActive && (
                <ChevronRight className="ml-auto h-4 w-4 text-plex-orange" />
              )}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

export { SIDEBAR_WIDTH_EXPANDED, SIDEBAR_WIDTH_COLLAPSED };
