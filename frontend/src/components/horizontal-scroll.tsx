"use client";

import { useRef, useState, useEffect } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { DSIconButton } from "@/components/ds";
import { useIsTV } from "@/hooks/use-platform";

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
  const isTV = useIsTV();

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
          {!isTV && (
            <div className="flex items-center gap-1">
              {canScrollLeft && (
                <DSIconButton
                  onClick={() => scroll("left")}
                  className="rounded-full hover:bg-zinc-800"
                  icon={<ChevronLeft className="w-5 h-5 text-zinc-400" />}
                />
              )}
              {canScrollRight && (
                <DSIconButton
                  onClick={() => scroll("right")}
                  className="rounded-full hover:bg-zinc-800"
                  icon={<ChevronRight className="w-5 h-5 text-zinc-400" />}
                />
              )}
            </div>
          )}
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
