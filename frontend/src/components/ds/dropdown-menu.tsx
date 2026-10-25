"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { useBackToClose } from "@/hooks/use-back-to-close";

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
  /** What the trigger opens, for screen readers (the trigger is often just an avatar) */
  label: string;
  align?: "left" | "right";
}

export function DSDropdownMenu({
  items,
  trigger,
  label,
  align = "right",
}: DSDropdownMenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useBackToClose(open, () => setOpen(false));

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

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
      {/* A button: the div wasn't reachable with the keyboard or the TV remote */}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        className="block rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-plex-orange"
      >
        {trigger}
      </button>
      {open && (
        <div
          className={cn(
            "absolute top-full mt-2 z-50 rounded-xl p-1 w-[200px]",
            "flex flex-col gap-0.5",
            "shadow-[0_8px_32px_rgba(0,0,0,0.5)]",
            align === "right" ? "right-0" : "left-0",
          )}
          style={{
            backgroundColor: "rgba(10,10,10,0.75)",
            backdropFilter: "blur(20px)",
            border: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          {items.map((item, i) =>
            item.separator ? (
              <div key={i} className="h-px bg-white/[0.06] my-0.5" />
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
                    ? "text-[#ef4444] hover:bg-red-500/10"
                    : "text-white/80 hover:bg-white/[0.08]",
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
