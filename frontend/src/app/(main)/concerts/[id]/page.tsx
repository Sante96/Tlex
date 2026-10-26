"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  HeroBanner,
  EpisodeCard,
  DetailPageLayout,
  HeroBannerSkeleton,
} from "@/components/ds";
import { getFranchise, type FranchiseDetails } from "@/lib/api";
import { formatDurationShort, getTmdbImageUrl, yearOf } from "@/lib/format";
import { ExpandableOverview } from "@/components/ui/expandable-overview";
import { useIsTV } from "@/hooks/use-platform";
import { useDelayed } from "@/hooks/use-delayed";

/** An anime/game of the Concerts section and its concerts, newest first */
export default function FranchisePage() {
  const t = useTranslations();
  const params = useParams();
  const router = useRouter();
  const franchiseId = Number(params.id);
  const isTV = useIsTV();
  const [franchise, setFranchise] = useState<FranchiseDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const showSkeleton = useDelayed(loading);

  const load = useCallback(async () => {
    try {
      setFranchise(await getFranchise(franchiseId));
    } catch {
      setFranchise(null);
    } finally {
      setLoading(false);
    }
  }, [franchiseId]);

  useEffect(() => {
    if (Number.isInteger(franchiseId)) load();
  }, [franchiseId, load]);

  // An invalid id never loads: "not found" instead of a skeleton forever
  if (loading && Number.isInteger(franchiseId)) {
    return showSkeleton ? <FranchiseSkeleton /> : null;
  }

  if (!franchise) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-[#a1a1aa]">{t("media.notFound")}</p>
        <button
          onClick={() => router.back()}
          className="text-plex-orange text-sm mt-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-plex-orange rounded"
        >
          {t("media.goBack")}
        </button>
      </div>
    );
  }

  return (
    <DetailPageLayout backdropUrl={getTmdbImageUrl(franchise.backdrop_path, "original")}>
      <HeroBanner
        height={432}
        posterUrl={getTmdbImageUrl(franchise.poster_path, "w500")}
        posterAlt={franchise.title}
        posterWidth={200}
        posterHeight={300}
        mobileInfoSlot={
          <>
            <h1 className="text-xl md:text-4xl font-bold text-[#fafafa] leading-tight">
              {franchise.title}
            </h1>
            <span className="text-xs md:text-sm text-[#d4d4d8]">
              {t("concerts.count", { n: franchise.concerts.length })}
            </span>
          </>
        }
      >
        {franchise.overview && <ExpandableOverview text={franchise.overview} />}
      </HeroBanner>

      <div className={`flex flex-col gap-6 py-4 md:py-8 ${isTV ? "px-8" : "px-4 md:px-12"}`}>
        <h2 className="text-2xl font-semibold text-[#fafafa]">{t("nav.concerts")}</h2>
        <div
          className={
            isTV
              ? "grid grid-cols-2 xl:grid-cols-3 gap-5"
              : "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6"
          }
        >
          {franchise.concerts.map((c) => {
            const isWatched = c.watch_progress?.is_completed ?? false;
            return (
              <EpisodeCard
                key={c.id}
                label={c.release_date ? yearOf(c.release_date) : undefined}
                title={c.title}
                duration={
                  c.duration_seconds
                    ? (formatDurationShort(c.duration_seconds) ?? undefined)
                    : undefined
                }
                overview={c.overview}
                thumbnailUrl={getTmdbImageUrl(c.poster_path, "w500")}
                progress={!isWatched ? (c.watch_progress?.progress_percent ?? 0) : undefined}
                isWatched={isWatched}
                onClick={() => router.push(`/watch/${c.id}`)}
              />
            );
          })}
        </div>
      </div>
    </DetailPageLayout>
  );
}

function FranchiseSkeleton() {
  return (
    <div className="animate-pulse">
      <HeroBannerSkeleton buttons={0} />
      <div className="px-4 md:px-12 py-4 md:py-8">
        <div className="h-7 w-28 bg-[#27272a] rounded mb-6" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
          {[1, 2, 3].map((i) => (
            <div key={i} className="aspect-video bg-[#27272a] rounded-lg" />
          ))}
        </div>
      </div>
    </div>
  );
}
