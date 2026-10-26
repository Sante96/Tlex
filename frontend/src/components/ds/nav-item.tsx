"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

/** The sidebar's motion (its width, the page's margin): its labels fade with it */
export const NAV_MOTION = { duration: 0.3, ease: [0.4, 0, 0.2, 1] as const };
export const NAV_FADE_EASE = "cubic-bezier(0.4, 0, 0.2, 1)";
export const NAV_FADE = `opacity 0.3s ${NAV_FADE_EASE}`;

interface DSNavItemProps {
  href: string;
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  collapsed?: boolean;
  tvMode?: boolean;
  iconColumn?: number;
}

export function DSNavItem({
  href,
  icon,
  label,
  active,
  collapsed,
  tvMode,
  iconColumn,
}: DSNavItemProps) {
  return (
    <Link
      href={href}
      title={collapsed ? label : undefined}
      className={cn(
        "grid w-full rounded-[10px] font-medium transition-colors outline-none overflow-hidden items-center",
        tvMode ? "h-9 tv-1080:h-10 tv-4k:h-11 text-[13px] tv-1080:text-[14px] tv-4k:text-[15px]" : "h-11 text-[15px]",
        active
          ? "bg-[#e5a00d1a] text-plex-orange"
          : tvMode
            ? "text-[#a1a1aa] focus-visible:bg-white/15 focus-visible:text-[#fafafa] focus-visible:ring-2 focus-visible:ring-plex-orange focus-visible:ring-inset"
            : "text-[#a1a1aa] hover:bg-white/10 hover:text-[#fafafa] focus-visible:bg-white/10 focus-visible:text-[#fafafa]",
      )}
      style={{ gridTemplateColumns: `${iconColumn ?? (tvMode ? 36 : 44)}px minmax(0, 1fr) auto` }}
    >
      {/* Icon — always in 44px column, perfectly centered regardless of label */}
      <span
        className={cn(
          "flex items-center justify-center",
          active ? "text-plex-orange" : "text-[#71717a]",
        )}
      >
        {icon}
      </span>

      {/* Label: minmax(0,1fr) shrinks to 0 when collapsed. Cut by the closing edge (no
          ellipsis) as it fades, in step with the card */}
      <span
        className="overflow-hidden whitespace-nowrap"
        style={{ opacity: collapsed ? 0 : 1, transition: NAV_FADE }}
      >
        {label}
      </span>

      {/* Chevron: fading with the label (collapsed, the card cuts it off) */}
      {active && (
        <span className="pr-3.5" style={{ opacity: collapsed ? 0 : 1, transition: NAV_FADE }}>
          <ChevronRight className="h-4 w-4 text-plex-orange" />
        </span>
      )}
    </Link>
  );
}
