"use client";

import { useRef, useState, useEffect } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface HorizontalScrollProps {
  children: React.ReactNode;
  title?: string;
  className?: string;
}

export function HorizontalScroll({
  children,
  title,
  className,
}: HorizontalScrollProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const checkScroll = () => {
    const el = scrollRef.current;
    if (el) {
      setCanScrollLeft(el.scrollLeft > 0);
      setCanScrollRight(el.scrollLeft < el.scrollWidth - el.clientWidth - 1);
    }
  };

  useEffect(() => {
    checkScroll();
    const el = scrollRef.current;
    if (el) {
      el.addEventListener("scroll", checkScroll);
      window.addEventListener("resize", checkScroll);
      return () => {
        el.removeEventListener("scroll", checkScroll);
        window.removeEventListener("resize", checkScroll);
      };
    }
  }, []);

  const scroll = (direction: "left" | "right") => {
    const el = scrollRef.current;
    if (el) {
      const scrollAmount = el.clientWidth * 0.8;
      el.scrollBy({
        left: direction === "left" ? -scrollAmount : scrollAmount,
        behavior: "smooth",
      });
    }
  };

  return (
    <div>
      {/* Header with title and arrows */}
      {title && (
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-white">{title}</h2>
          <div className="flex items-center gap-1">
            {canScrollLeft && (
              <button
                onClick={() => scroll("left")}
                className="w-8 h-8 flex items-center justify-center hover:bg-zinc-800 rounded-full transition-colors"
              >
                <ChevronLeft className="w-5 h-5 text-zinc-400" />
              </button>
            )}
            {canScrollRight && (
              <button
                onClick={() => scroll("right")}
                className="w-8 h-8 flex items-center justify-center hover:bg-zinc-800 rounded-full transition-colors"
              >
                <ChevronRight className="w-5 h-5 text-zinc-400" />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Scrollable content */}
      <div
        ref={scrollRef}
        className={cn("flex overflow-x-auto scrollbar-hide", className)}
        style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}
      >
        {children}
      </div>
    </div>
  );
}
