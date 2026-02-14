"use client";

import { useRef, useState, useEffect } from "react";
import Image from "next/image";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { CastMember } from "@/lib/api";
import { getTmdbImageUrl } from "@/lib/format";

interface CastSectionProps {
  cast: CastMember[];
}

export function CastSection({ cast }: CastSectionProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const checkScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 0);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 1);
  };

  useEffect(() => {
    checkScroll();
    const el = scrollRef.current;
    if (el) el.addEventListener("scroll", checkScroll);
    return () => el?.removeEventListener("scroll", checkScroll);
  }, [cast]);

  const scroll = (direction: "left" | "right") => {
    const el = scrollRef.current;
    if (!el) return;
    const amount = 400;
    el.scrollBy({
      left: direction === "left" ? -amount : amount,
      behavior: "smooth",
    });
  };

  if (!cast.length) return null;

  return (
    <section className="flex flex-col gap-4">
      {/* Header with chevrons */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold text-[#fafafa]">Cast</h2>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => scroll("left")}
            disabled={!canScrollLeft}
            className="flex items-center justify-center w-8 h-8 rounded-full bg-[#27272a] transition-colors disabled:opacity-30"
          >
            <ChevronLeft
              className={`h-[18px] w-[18px] ${canScrollLeft ? "text-[#fafafa]" : "text-[#71717a]"}`}
            />
          </button>
          <button
            type="button"
            onClick={() => scroll("right")}
            disabled={!canScrollRight}
            className="flex items-center justify-center w-8 h-8 rounded-full bg-[#27272a] transition-colors disabled:opacity-30"
          >
            <ChevronRight
              className={`h-[18px] w-[18px] ${canScrollRight ? "text-[#fafafa]" : "text-[#71717a]"}`}
            />
          </button>
        </div>
      </div>

      {/* Scrollable cast grid */}
      <div
        ref={scrollRef}
        className="flex gap-5 overflow-x-auto scrollbar-hide"
        style={{ scrollbarWidth: "none" }}
      >
        {cast.map((member) => (
          <div
            key={member.id}
            className="flex flex-col items-center gap-2 shrink-0 w-[100px]"
          >
            <div className="w-20 h-20 rounded-full overflow-hidden bg-[#27272a] shrink-0">
              {member.profile_path ? (
                <Image
                  src={getTmdbImageUrl(member.profile_path, "w300") || ""}
                  alt={member.name}
                  width={80}
                  height={80}
                  className="object-cover w-full h-full"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-[#52525b] text-lg font-semibold">
                  {member.name.charAt(0)}
                </div>
              )}
            </div>
            <span className="text-xs font-medium text-[#fafafa] text-center leading-tight line-clamp-2">
              {member.name}
            </span>
            {member.character && (
              <span className="text-[11px] text-[#71717a] text-center leading-tight line-clamp-1 -mt-1">
                {member.character}
              </span>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
