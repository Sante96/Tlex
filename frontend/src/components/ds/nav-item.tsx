"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface DSNavItemProps {
  href: string;
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  collapsed?: boolean;
  tvMode?: boolean;
}

export function DSNavItem({
  href,
  icon,
  label,
  active,
  collapsed,
  tvMode,
}: DSNavItemProps) {
  return (
    <Link
      href={href}
      title={collapsed ? label : undefined}
      className={cn(
        "grid w-full h-11 rounded-[10px] font-medium transition-colors outline-none overflow-hidden items-center text-[15px]",
        active
          ? "bg-[#e5a00d1a] text-[#e5a00d]"
          : tvMode
            ? "text-[#a1a1aa] focus-visible:bg-white/15 focus-visible:text-[#fafafa] focus-visible:ring-2 focus-visible:ring-[#e5a00d] focus-visible:ring-inset"
            : "text-[#a1a1aa] hover:bg-white/10 hover:text-[#fafafa] focus-visible:bg-white/10 focus-visible:text-[#fafafa]",
      )}
      style={{ gridTemplateColumns: "44px minmax(0, 1fr) auto" }}
    >
      {/* Icon — always in 44px column, perfectly centered regardless of label */}
      <span
        className={cn(
          "flex items-center justify-center",
          active ? "text-[#e5a00d]" : "text-[#71717a]",
        )}
      >
        {icon}
      </span>

      {/* Label — minmax(0,1fr): can shrink to 0 when collapsed */}
      <span
        className="truncate"
        style={{
          opacity: collapsed ? 0 : 1,
          transition: collapsed ? "opacity 0.08s ease" : "opacity 0.15s ease 0.12s",
        }}
      >
        {label}
      </span>

      {/* Chevron — only rendered when visible to avoid ghost space in auto column */}
      {!collapsed && active && (
        <span className="pr-3.5" style={{ opacity: 1, transition: "opacity 0.15s ease 0.12s" }}>
          <ChevronRight className="h-4 w-4 text-[#e5a00d]" />
        </span>
      )}
    </Link>
  );
}
