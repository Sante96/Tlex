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
}

export function DSNavItem({
  href,
  icon,
  label,
  active,
  collapsed,
}: DSNavItemProps) {
  return (
    <Link
      href={href}
      title={collapsed ? label : undefined}
      className={cn(
        "flex items-center h-11 rounded-[10px] text-[15px] font-medium transition-colors",
        collapsed ? "justify-center w-11 px-0" : "gap-3.5 px-3.5",
        active
          ? "bg-[#e5a00d1a] text-[#e5a00d]"
          : "text-[#a1a1aa] hover:bg-[#27272a80] hover:text-[#fafafa]",
      )}
    >
      <span
        className={cn("shrink-0", active ? "text-[#e5a00d]" : "text-[#71717a]")}
      >
        {icon}
      </span>
      {!collapsed && <span className="flex-1 truncate">{label}</span>}
      {!collapsed && active && (
        <ChevronRight className="h-4 w-4 text-[#e5a00d]" />
      )}
    </Link>
  );
}
