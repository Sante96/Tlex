"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface DropdownItem {
  icon?: React.ReactNode;
  label: string;
  onClick?: () => void;
  destructive?: boolean;
  separator?: boolean;
}

interface DSDropdownMenuProps {
  items: DropdownItem[];
  trigger: React.ReactNode;
  align?: "left" | "right";
}

export function DSDropdownMenu({
  items,
  trigger,
  align = "right",
}: DSDropdownMenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <div onClick={() => setOpen(!open)} className="cursor-pointer">
        {trigger}
      </div>
      {open && (
        <div
          className={cn(
            "absolute top-full mt-2 z-50 rounded-xl border border-[#27272a] bg-[#18181b] p-1 w-[200px]",
            "flex flex-col gap-0.5",
            align === "right" ? "right-0" : "left-0",
          )}
        >
          {items.map((item, i) =>
            item.separator ? (
              <div key={i} className="h-px bg-[#27272a] my-0.5" />
            ) : (
              <button
                key={i}
                onClick={() => {
                  item.onClick?.();
                  setOpen(false);
                }}
                className={cn(
                  "flex items-center gap-3 h-9 px-3 rounded-lg text-sm transition-colors w-full text-left",
                  item.destructive
                    ? "text-[#ef4444] hover:bg-[#ef444420]"
                    : "text-[#fafafa] hover:bg-[#e5a00d40]",
                )}
              >
                {item.icon && (
                  <span
                    className={cn(
                      "shrink-0",
                      item.destructive ? "text-[#ef4444]" : "text-[#a1a1aa]",
                    )}
                  >
                    {item.icon}
                  </span>
                )}
                {item.label}
              </button>
            ),
          )}
        </div>
      )}
    </div>
  );
}
