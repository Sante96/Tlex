"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { DSButton, TVButton, PosterCard, SectionHeader } from "@/components/ds";
import { StaggerGrid } from "@/components/motion/stagger-grid";
import { useIsTV } from "@/hooks/use-platform";
import { useAuth } from "@/contexts/auth-context";
import {
  getMediaList,
  getContinueWatching,
  triggerScan,
  getSeriesList,
  type MediaItem,
  type ContinueWatchingItem,
  type SeriesItem,
} from "@/lib/api";
import { cleanEpisodeTitle, getTmdbImageUrl, yearOf } from "@/lib/format";
import { HomeHero, type HeroItem } from "@/components/home/home-hero";
import { ContinueWatchingCard } from "@/components/home/continue-watching-card";
import { PosterCardSkeleton, Skeleton } from "@/components/ui/skeleton";
import { useDelayed } from "@/hooks/use-delayed";

// Posters per home row
const ROW = 7;

// Continue Watching: landscape cards, fewer per row; a strip on phones
const CONTINUE_GRID =
  "flex overflow-x-auto md:overflow-visible md:grid md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-3 md:gap-4 scrollbar-hide pb-3 md:pb-0";
const TV_CONTINUE_GRID = "grid grid-cols-4 gap-5";
const CONTINUE_CARD = "shrink-0 w-[260px] md:w-full";

/** What the hero shows: the title last watched, else the newest one with a backdrop */
function heroItem(
  watching: ContinueWatchingItem[],
  movies: MediaItem[],
  series: SeriesItem[],
  t: ReturnType<typeof useTranslations>,
): HeroItem | null {
  const current = watching.find((w) => w.backdrop_path);
  if (current) {
    return {
      label: t("home.continueWatching"),
      title: current.series_title || current.title,
      subtitle:
        current.season_number && current.episode_number
          ? `S${current.season_number} · E${current.episode_number} · ${cleanEpisodeTitle(current.title)}`
          : undefined,
      overview: current.overview,
      backdropUrl: getTmdbImageUrl(current.backdrop_path, "original")!,
      playHref: `/watch/${current.id}`,
      detailsHref: current.series_id ? `/series/${current.series_id}` : `/media/${current.id}`,
      progressPercent: current.progress_percent,
      remainingSeconds: current.duration_seconds - current.position_seconds,
    };
  }
  const movie = movies.find((m) => m.backdrop_path);
  if (movie) {
    return {
      label: t("home.recentlyAdded"),
      title: movie.title,
      overview: movie.overview,
      backdropUrl: getTmdbImageUrl(movie.backdrop_path, "original")!,
      playHref: `/watch/${movie.id}`,
      detailsHref: `/media/${movie.id}`,
    };
  }
  const show = series.find((s) => s.backdrop_path);
  if (show) {
    return {
      label: t("home.recentlyAdded"),
      title: show.title,
      overview: show.overview,
      backdropUrl: getTmdbImageUrl(show.backdrop_path, "original")!,
      playHref: `/series/${show.id}`,
      detailsHref: `/series/${show.id}`,
    };
  }
  return null;
}

export default function HomePage() {
  const t = useTranslations();
  const isTV = useIsTV();
  const { user } = useAuth();
  const [media, setMedia] = useState<MediaItem[]>([]);
  const [series, setSeries] = useState<SeriesItem[]>([]);
  const [continueWatching, setContinueWatching] = useState<
    ContinueWatchingItem[]
  >([]);
  const [loading, setLoading] = useState(true);
  const showSkeleton = useDelayed(loading);
  const [failed, setFailed] = useState(false);
  const [scanning, setScanning] = useState(false);

  const gridClass = isTV
    ? "grid grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8 gap-4 md:gap-5"
    : "flex overflow-x-auto md:overflow-visible md:grid md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-7 2xl:grid-cols-9 gap-3 md:gap-4 scrollbar-hide pb-3 md:pb-0";

  const cardClass = isTV ? "" : "shrink-0 w-[130px] md:w-full";

  useEffect(() => {
    loadHome();
  }, []);

  // All rows in one go: Continue Watching used to land later and push the others down.
  // Only movies, newest first: the old request mixed in episodes sorted by title, which
  // could leave no movie in the first 50.
  const loadHome = async () => {
    setLoading(true);
    setFailed(false);
    try {
      const [mediaData, seriesData, watching] = await Promise.all([
        getMediaList({ media_type: "MOVIE", sort: "recent", limit: ROW }),
        getSeriesList({ sort: "recent", page_size: ROW }),
        getContinueWatching(10),
      ]);
      setMedia(mediaData.items);
      setSeries(seriesData.items);
      setContinueWatching(watching);
    } catch {
      setFailed(true); // not "your library is empty"
    } finally {
      setLoading(false);
    }
  };

  const handleScan = async () => {
    try {
      setScanning(true);
      await triggerScan(100);
      await loadHome();
    } catch {
    } finally {
      setScanning(false);
    }
  };

  if (loading) {
    return showSkeleton ? (
      <HomeSkeleton isTV={isTV} gridClass={gridClass} cardClass={cardClass} />
    ) : null;
  }

  if (failed) {
    return (
      <div className="flex flex-col items-center justify-center gap-6 py-20">
        <p className="text-[#a1a1aa]">{t("common.loadError")}</p>
        {isTV ? (
          <TVButton onClick={loadHome} icon={<RefreshCw className="h-5 w-5" />}>
            {t("common.retry")}
          </TVButton>
        ) : (
          <DSButton onClick={loadHome} icon={<RefreshCw className="h-5 w-5" />}>
            {t("common.retry")}
          </DSButton>
        )}
      </div>
    );
  }

  if (media.length === 0 && series.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <h1 className="text-2xl font-bold text-[#fafafa] mb-4">
          {t("home.welcome")}
        </h1>
        {/* Scanning takes an admin: the button used to fail silently for everyone else */}
        <p className="text-[#a1a1aa] mb-6">
          {user?.is_admin ? t("home.emptyLibrary") : t("home.emptyLibraryUser")}
        </p>
        {!user?.is_admin ? null : isTV ? (
          <TVButton
            onClick={handleScan}
            disabled={scanning}
            icon={<RefreshCw className={`h-5 w-5 ${scanning ? "animate-spin" : ""}`} />}
          >
            {scanning ? t("home.scanning") : t("home.scan")}
          </TVButton>
        ) : (
          <DSButton
            onClick={handleScan}
            disabled={scanning}
            icon={<RefreshCw className={`h-5 w-5 ${scanning ? "animate-spin" : ""}`} />}
          >
            {scanning ? t("home.scanning") : t("home.scan")}
          </DSButton>
        )}
      </div>
    );
  }

  const hero = heroItem(continueWatching, media, series, t);

  return (
    <div className={`flex flex-col gap-8 ${isTV ? "px-8 py-8" : "px-4 md:px-8 py-6 md:py-8"}`}>
      {hero && <HomeHero item={hero} />}

      {/* Continue Watching */}
      {continueWatching.length > 0 && (
        <section>
          <SectionHeader title={t("home.continueWatching")} />
          <div className={isTV ? TV_CONTINUE_GRID : CONTINUE_GRID}>
            {continueWatching.map((item) => (
              <ContinueWatchingCard key={item.id} item={item} className={isTV ? "" : CONTINUE_CARD} />
            ))}
          </div>
        </section>
      )}

      {/* Film */}
      {media.length > 0 && (
        <section>
          <SectionHeader title={t("home.recentMovies")} href="/movies" />
          <StaggerGrid className={gridClass}>
            {media.map((m) => (
              <PosterCard
                key={m.id}
                href={`/media/${m.id}`}
                imageUrl={getTmdbImageUrl(m.poster_path, "w300")}
                title={m.title}
                subtitle={
                  m.release_date
                    ? yearOf(m.release_date)
                    : ""
                }
                className={cardClass}
              />
            ))}
          </StaggerGrid>
        </section>
      )}

      {/* Serie TV */}
      {series.length > 0 && (
        <section>
          <SectionHeader title={t("home.recentSeries")} href="/series" />
          <StaggerGrid className={gridClass}>
            {series.map((s) => (
              <PosterCard
                key={s.id}
                href={`/series/${s.id}`}
                imageUrl={getTmdbImageUrl(s.poster_path, "w300")}
                title={s.title}
                subtitle={
                  s.seasons_count === 1
                    ? `1 ${t("home.season")}`
                    : `${s.seasons_count} ${t("home.seasons")}`
                }
                className={cardClass}
              />
            ))}
          </StaggerGrid>
        </section>
      )}
    </div>
  );
}

/** The home while it loads: three titled rows like the page's (one untitled row jumped) */
function HomeSkeleton({
  isTV,
  gridClass,
  cardClass,
}: {
  isTV: boolean;
  gridClass: string;
  cardClass: string;
}) {
  return (
    <div className={`flex flex-col gap-8 ${isTV ? "px-8 py-8" : "px-4 md:px-8 py-6 md:py-8"}`}>
      <div className="-mx-4 md:-mx-8 -mt-6 md:-mt-8 h-[46vh] md:h-[56vh] min-h-[300px] max-h-[560px] bg-[#18181b] animate-pulse" />
      <section>
        <Skeleton className="h-8 w-48 mb-5" />
        <div className={isTV ? TV_CONTINUE_GRID : CONTINUE_GRID}>
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className={isTV ? "" : CONTINUE_CARD}>
              <Skeleton className="aspect-video" />
              <Skeleton className="h-4 w-3/4 mt-2" />
            </div>
          ))}
        </div>
      </section>
      {[0, 1].map((row) => (
        <section key={row}>
          <Skeleton className="h-8 w-48 mb-5" />
          <div className={gridClass}>
            {Array.from({ length: ROW }).map((_, i) => (
              <PosterCardSkeleton key={i} className={cardClass} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
