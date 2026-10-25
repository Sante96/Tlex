"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Info, Play } from "lucide-react";
import { ActionButton } from "@/components/ds";
import { FadeImage } from "@/components/ui/fade-image";
import { cn } from "@/lib/utils";
import { formatDuration } from "@/lib/format";

export interface HeroItem {
  id: number;
  /** "Continue watching" or "Recently added" */
  label: string;
  title: string;
  /** The episode's line (S1 · E2 · title) */
  subtitle?: string;
  overview?: string | null;
  backdropUrl: string;
  playHref: string;
  detailsHref: string;
  /** Set when it's being watched: the bar and "x left", and "Resume" */
  progressPercent?: number;
  remainingSeconds?: number;
  /** The strip's landscape picture (an episode's still) */
  stillUrl?: string | null;
}

const ROTATE_MS = 8000;
// Hovering a card selects it after this: sweeping the mouse across the strip flickered
const HOVER_SELECT_MS = 200;

/**
 * The top of the home: what's being watched, over its backdrop, with the strip of the
 * others at the bottom. Hovering or focusing a card shows it, clicking it plays it; the
 * hero moves on by itself every 8 s while nobody is pointing at it.
 */
export function HomeHero({ items }: { items: HeroItem[] }) {
  const t = useTranslations();
  const router = useRouter();
  const [active, setActive] = useState(0);
  // Backdrops mounted so far: the active one and the next stay loaded, for the crossfade
  const [seen, setSeen] = useState<Set<number>>(() => new Set([0]));
  const [paused, setPaused] = useState(false);
  const [reducedMotion] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const select = useCallback((index: number) => {
    setActive(index);
    setSeen((s) => (s.has(index) ? s : new Set(s).add(index)));
  }, []);

  const rotating = items.length > 1 && !paused && !reducedMotion;
  useEffect(() => {
    if (!rotating) return;
    let timer: ReturnType<typeof setTimeout>;
    // A background tab waits: the hero doesn't move on unseen
    const arm = () => {
      timer = setTimeout(() => (document.hidden ? arm() : select((active + 1) % items.length)), ROTATE_MS);
    };
    arm();
    return () => clearTimeout(timer);
  }, [rotating, active, items.length, select]);

  useEffect(() => () => clearTimeout(hoverTimer.current), []);

  const item = items[active] ?? items[0];
  const next = (active + 1) % items.length;
  const resuming = item.progressPercent !== undefined;
  const left = item.remainingSeconds ? formatDuration(item.remainingSeconds) : null;

  return (
    <section
      className="relative -mx-4 md:-mx-8 -mt-6 md:-mt-8"
      // Pointing at it or having the focus in it (the TV remote) holds the rotation
      onPointerEnter={(e) => e.pointerType === "mouse" && setPaused(true)}
      onPointerLeave={(e) => e.pointerType === "mouse" && setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={(e) => !e.currentTarget.contains(e.relatedTarget as Node) && setPaused(false)}
    >
      {/* The pictures fade out at the bottom (a mask, not a dark overlay: the page's
          background is a warm gradient, and the hero ended on a hard black edge) */}
      <div className="absolute inset-0 overflow-hidden [mask-image:linear-gradient(to_bottom,black_55%,transparent)]">
        {items.map((it, i) =>
          seen.has(i) || i === next ? (
            <div
              key={it.id}
              className={cn(
                "absolute inset-0 transition-opacity duration-700",
                i === active ? "opacity-100" : "opacity-0",
              )}
            >
              <FadeImage
                src={it.backdropUrl}
                alt=""
                fill
                priority={i === 0}
                sizes="100vw"
                className="object-cover object-top"
              />
            </div>
          ) : null,
        )}
        {/* Dark on the left and low down, for the text and the strip */}
        <div className="absolute inset-0 bg-gradient-to-r from-[#09090b]/90 via-[#09090b]/50 to-transparent" />
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
      </div>

      <div className="relative flex flex-col justify-end gap-6 min-h-[440px] md:min-h-[64vh] px-4 md:px-8 pt-32 md:pt-40 pb-4 md:pb-8">
        <div className="flex flex-col gap-2 md:gap-3 max-w-2xl text-shadow">
          {/* The text changes with the title; the buttons below stay put (and their glass
              blurred: a fading ancestor would turn the blur off) */}
          <div key={item.id} className="flex flex-col gap-2 md:gap-3 animate-[hero-text-in_400ms_ease-out]">
            <span className="text-xs font-semibold uppercase tracking-widest text-plex-orange">
              {item.label}
            </span>
            <h1 className="text-2xl md:text-5xl font-bold text-white leading-tight">{item.title}</h1>
            {item.subtitle && <p className="text-sm md:text-base text-white/80">{item.subtitle}</p>}
            {item.overview && (
              <p className="hidden md:block text-sm text-white/70 line-clamp-2">{item.overview}</p>
            )}
            {resuming && (
              <div className="flex items-center gap-3">
                <div className="h-1 w-32 md:w-48 rounded-full bg-white/20 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-plex-orange"
                    style={{ width: `${Math.min(100, item.progressPercent ?? 0)}%` }}
                  />
                </div>
                {left && (
                  <span className="text-xs text-white/70">{t("home.timeLeft", { time: left })}</span>
                )}
              </div>
            )}
          </div>
          <div className="flex flex-wrap gap-3 pt-1">
            <ActionButton icon={<Play className="h-5 w-5 fill-current" />} onClick={() => router.push(item.playHref)}>
              {resuming ? t("home.resume") : t("media.play")}
            </ActionButton>
            <ActionButton
              variant="secondary"
              icon={<Info className="h-5 w-5" />}
              onClick={() => router.push(item.detailsHref)}
            >
              {t("home.details")}
            </ActionButton>
          </div>
        </div>

        {items.length > 1 && (
          <div className="flex gap-3 md:gap-4 overflow-x-auto scrollbar-hide py-1 -mx-1 px-1">
            {items.map((it, i) => (
              <StripCard
                key={it.id}
                item={it}
                active={i === active}
                timing={i === active && rotating}
                onShow={() => select(i)}
                onHoverStart={() => {
                  clearTimeout(hoverTimer.current);
                  hoverTimer.current = setTimeout(() => select(i), HOVER_SELECT_MS);
                }}
                onHoverEnd={() => clearTimeout(hoverTimer.current)}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function StripCard({
  item,
  active,
  timing,
  onShow,
  onHoverStart,
  onHoverEnd,
}: {
  item: HeroItem;
  active: boolean;
  /** The active card while the hero rotates: a bar shows when it moves on */
  timing: boolean;
  onShow: () => void;
  onHoverStart: () => void;
  onHoverEnd: () => void;
}) {
  return (
    <Link
      href={item.playHref}
      onFocus={onShow}
      onPointerEnter={(e) => e.pointerType === "mouse" && onHoverStart()}
      onPointerLeave={onHoverEnd}
      className="group shrink-0 w-44 md:w-56 outline-none"
    >
      <div
        className={cn(
          "relative aspect-video rounded-lg overflow-hidden bg-[#27272a] ring-2 transition-[box-shadow,transform] duration-200",
          active ? "ring-plex-orange" : "ring-white/10 group-hover:ring-white/40",
          "group-focus-visible:ring-plex-orange group-focus-visible:scale-105",
        )}
      >
        {item.stillUrl && (
          <FadeImage
            src={item.stillUrl}
            alt=""
            fill
            sizes="(min-width: 768px) 224px, 176px"
            className="object-cover"
          />
        )}
        <div className="absolute inset-0 flex items-center justify-center bg-black/0 group-hover:bg-black/30 transition-colors">
          <Play className="h-8 w-8 text-white fill-white opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
        {timing && (
          <div className="absolute top-0 left-0 h-0.5 bg-white/80 animate-[hero-timer_8s_linear_forwards]" />
        )}
        <div className="absolute inset-x-0 bottom-0 h-1 bg-white/20">
          <div
            className="h-full bg-plex-orange"
            style={{ width: `${Math.min(100, item.progressPercent ?? 0)}%` }}
          />
        </div>
      </div>
      <p className={cn("mt-2 text-sm font-medium truncate", active ? "text-white" : "text-white/70")}>
        {item.title}
      </p>
      {item.subtitle && <p className="text-xs text-white/50 truncate">{item.subtitle}</p>}
    </Link>
  );
}
