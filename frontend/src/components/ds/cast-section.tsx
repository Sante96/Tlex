"use client";

import { useRef, useState, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { DSIconButton } from "@/components/ds";
import { useIsTV } from "@/hooks/use-platform";
import type { CastMember } from "@/lib/api";
import { getTmdbImageUrl } from "@/lib/format";

interface CastSectionProps {
  cast: CastMember[];
}

function PeopleRow({
  title,
  members,
}: {
  title: string;
  members: CastMember[];
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);
  const isTV = useIsTV();

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
  }, [members]);

  const scroll = (direction: "left" | "right") => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollBy({
      left: direction === "left" ? -400 : 400,
      behavior: "smooth",
    });
  };

  if (!members.length) return null;

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold text-[#fafafa]">{title}</h2>
        {!isTV && (
          <div className="flex items-center gap-2">
            <DSIconButton
              onClick={() => scroll("left")}
              disabled={!canScrollLeft}
              className="rounded-full bg-[#27272a] disabled:opacity-30"
              icon={
                <ChevronLeft
                  className={`h-[18px] w-[18px] ${canScrollLeft ? "text-[#fafafa]" : "text-[#71717a]"}`}
                />
              }
            />
            <DSIconButton
              onClick={() => scroll("right")}
              disabled={!canScrollRight}
              className="rounded-full bg-[#27272a] disabled:opacity-30"
              icon={
                <ChevronRight
                  className={`h-[18px] w-[18px] ${canScrollRight ? "text-[#fafafa]" : "text-[#71717a]"}`}
                />
              }
            />
          </div>
        )}
      </div>

      <div
        ref={scrollRef}
        className="flex gap-6 overflow-x-auto scrollbar-hide py-2 px-1"
        style={{ scrollbarWidth: "none" }}
      >
        {members.map((member) => (
          <Link
            key={`${member.id}-${member.character ?? member.job}`}
            href={`/person/${member.id}`}
            className="flex flex-col items-center gap-2 shrink-0 w-[200px] group outline-none"
          >
            <div
              className="w-50 h-50 rounded-full overflow-hidden bg-[#27272a] shrink-0 ring-2 ring-transparent group-hover:ring-[#e5a00d] group-focus-visible:ring-[#e5a00d] transition-all duration-200 group-hover:scale-105 group-focus-visible:scale-105"
              style={{ boxShadow: "none" }}
            >
              {member.profile_path ? (
                <Image
                  src={getTmdbImageUrl(member.profile_path, "w300") || ""}
                  alt={member.name}
                  width={200}
                  height={200}
                  className="object-cover w-full h-full transition-[filter] duration-200 group-hover:brightness-110"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-[#52525b] group-hover:text-[#e5a00d] text-lg font-semibold transition-colors duration-200">
                  {member.name.charAt(0)}
                </div>
              )}
            </div>
            <span className="text-xs font-medium text-[#a1a1aa] group-hover:text-white text-center leading-tight line-clamp-2 transition-colors duration-200">
              {member.name}
            </span>
            {(member.character || member.job) && (
              <span className="text-[11px] text-[#52525b] group-hover:text-[#a1a1aa] text-center leading-tight line-clamp-1 -mt-1 transition-colors duration-200">
                {member.character ?? member.job}
              </span>
            )}
          </Link>
        ))}
      </div>
    </section>
  );
}

export function CastSection({ cast }: CastSectionProps) {
  const actors = cast.filter((m) => m.job === null);
  const crew = cast.filter((m) => m.job !== null);

  if (!cast.length) return null;

  return (
    <div className="flex flex-col gap-8">
      <PeopleRow title="Cast" members={actors} />
      <PeopleRow title="Staff" members={crew} />
    </div>
  );
}
