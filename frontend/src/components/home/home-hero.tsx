"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Info, Play } from "lucide-react";
import { ActionButton } from "@/components/ds";
import { FadeImage } from "@/components/ui/fade-image";
import { formatDuration } from "@/lib/format";

export interface HeroItem {
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
}

/** The top of the home: the title to resume (or the newest one) over its backdrop */
export function HomeHero({ item }: { item: HeroItem }) {
  const t = useTranslations();
  const router = useRouter();
  const resuming = item.progressPercent !== undefined;
  const left = item.remainingSeconds ? formatDuration(item.remainingSeconds) : null;

  return (
    <section className="relative -mx-4 md:-mx-8 -mt-6 md:-mt-8 h-[46vh] md:h-[56vh] min-h-[300px] max-h-[560px] overflow-hidden">
      {/* The picture fades out at the bottom (a mask, not a dark overlay: the page's
          background is a warm gradient, and the hero ended on a hard black edge) */}
      <div className="absolute inset-0 [mask-image:linear-gradient(to_bottom,black_50%,transparent)]">
        <FadeImage
          src={item.backdropUrl}
          alt=""
          fill
          priority
          sizes="100vw"
          className="object-cover object-top"
        />
        {/* Dark on the left and low down, for the text */}
        <div className="absolute inset-0 bg-gradient-to-r from-[#09090b]/90 via-[#09090b]/50 to-transparent" />
        <div className="absolute inset-0 bg-gradient-to-t from-black/50 via-transparent to-transparent" />
      </div>

      <div className="absolute inset-x-0 bottom-0 px-4 md:px-8 pb-6 md:pb-10 flex flex-col gap-2 md:gap-3 max-w-2xl text-shadow">
        <span className="text-xs font-semibold uppercase tracking-widest text-plex-orange">
          {item.label}
        </span>
        <h1 className="text-2xl md:text-5xl font-bold text-white leading-tight">{item.title}</h1>
        {item.subtitle && <p className="text-sm md:text-base text-white/80">{item.subtitle}</p>}
        {item.overview && (
          <p className="hidden md:block text-sm text-white/70 line-clamp-3">{item.overview}</p>
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
    </section>
  );
}
