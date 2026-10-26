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
  hideFromContinueWatching,
  triggerScan,
  getSeriesList,
  getAnimeList,
  type AnimeItem,
  type MediaItem,
  type ContinueWatchingItem,
  type SeriesItem,
} from "@/lib/api";
import { cleanEpisodeTitle, getTmdbImageUrl, yearOf } from "@/lib/format";
import { HomeHero, type HeroItem } from "@/components/home/home-hero";
import { PosterCardSkeleton, Skeleton } from "@/components/ui/skeleton";
import { useDelayed } from "@/hooks/use-delayed";

// Posters per home row: the widest grid's columns (9). Each width shows only what fills
// its rows (gridClass); the phone's row scrolls through all of them
const ROW = 9;

/** The hero's titles: what's being watched, else the newest title with a backdrop */
function heroItems(
  watching: ContinueWatchingItem[],
  movies: MediaItem[],
  series: SeriesItem[],
  concerts: MediaItem[],
  anime: AnimeItem[],
  t: ReturnType<typeof useTranslations>,
): HeroItem[] {
  const current = watching.filter((w) => w.backdrop_path);
  if (current.length) {
    return current.map((w) => ({
      id: w.id,
      label: t("home.continueWatching"),
      title: w.series_title || w.title,
      subtitle:
        w.season_number && w.episode_number
          ? `S${w.season_number} · E${w.episode_number} · ${cleanEpisodeTitle(w.title)}`
          : (w.franchise_title ?? undefined),
      overview: w.overview,
      backdropUrl: getTmdbImageUrl(w.backdrop_path, "original")!,
      stillUrl: getTmdbImageUrl(w.still_path ?? w.backdrop_path, "w500"),
      playHref: `/watch/${w.id}`,
      detailsHref: w.series_id ? `/series/${w.series_id}` : `/media/${w.id}`,
      progressPercent: w.progress_percent,
      remainingSeconds: w.duration_seconds - w.position_seconds,
    }));
  }
  // Films, concerts, series and anime together: a series added after the films was never
  // shown. Ids order them, a series by its newest episode's
  const newest = [
    ...anime.map((a) => ({
      added: a.added,
      backdrop: a.backdrop_path,
      item: {
        id: a.id,
        title: a.title,
        overview: null as string | null,
        playHref: a.kind === "series" ? `/series/${a.id}` : `/watch/${a.id}`,
        detailsHref: a.kind === "series" ? `/series/${a.id}` : `/media/${a.id}`,
      },
    })),
    ...[...movies, ...concerts].map((m) => ({
      added: m.id,
      backdrop: m.backdrop_path,
      item: { ...m, playHref: `/watch/${m.id}`, detailsHref: `/media/${m.id}` },
    })),
    ...series.map((s) => ({
      added: s.latest_media_id ?? 0,
      backdrop: s.backdrop_path,
      item: { ...s, playHref: `/series/${s.id}`, detailsHref: `/series/${s.id}` },
    })),
  ]
    .filter((c) => c.backdrop)
    .sort((a, b) => b.added - a.added)[0];
  if (!newest) return [];
  const { item } = newest;
  return [{
    id: item.id,
    label: t("home.recentlyAdded"),
    title: item.title,
    overview: item.overview,
    backdropUrl: getTmdbImageUrl(newest.backdrop, "original")!,
    playHref: item.playHref,
    detailsHref: item.detailsHref,
  }];
}

export default function HomePage() {
  const t = useTranslations();
  const isTV = useIsTV();
  const { user } = useAuth();
  const [media, setMedia] = useState<MediaItem[]>([]);
  const [series, setSeries] = useState<SeriesItem[]>([]);
  const [concerts, setConcerts] = useState<MediaItem[]>([]);
  const [anime, setAnime] = useState<AnimeItem[]>([]);
  const [continueWatching, setContinueWatching] = useState<
    ContinueWatchingItem[]
  >([]);
  const [loading, setLoading] = useState(true);
  const showSkeleton = useDelayed(loading);
  const [failed, setFailed] = useState(false);
  const [scanning, setScanning] = useState(false);

  // Columns, and the posters past the last full row hidden: 6 in two rows of 3, then one
  // row of 5, 7 and 9 (on the TV 6, 7 and 8). With 7 posters for 9 columns, two stood empty
  const gridClass = isTV
    ? "grid grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8 gap-4 md:gap-5 max-xl:[&>:nth-child(n+7)]:hidden xl:max-2xl:[&>:nth-child(n+8)]:hidden 2xl:[&>:nth-child(n+9)]:hidden"
    : "flex overflow-x-auto md:overflow-visible md:grid md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-7 2xl:grid-cols-9 gap-3 md:gap-4 scrollbar-hide pb-3 md:pb-0 md:max-lg:[&>:nth-child(n+7)]:hidden lg:max-xl:[&>:nth-child(n+6)]:hidden xl:max-2xl:[&>:nth-child(n+8)]:hidden";

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
      // The anime have their own row: not in the films' and the series'
      const [mediaData, seriesData, watching, concertData, animeData] = await Promise.all([
        getMediaList({ media_type: "MOVIE", sort: "recent", limit: ROW, anime: false }),
        getSeriesList({ sort: "recent", page_size: ROW, anime: false }),
        getContinueWatching(10),
        // A row of its own: a backend without concerts yet (422) mustn't blank the home
        getMediaList({ media_type: "CONCERT", sort: "recent", limit: ROW }).catch(() => null),
        getAnimeList({ sort: "recent", page_size: ROW }).catch(() => null),
      ]);
      setAnime(animeData?.items ?? []);
      setMedia(mediaData.items);
      setSeries(seriesData.items);
      setConcerts(concertData?.items ?? []);
      setContinueWatching(watching);
    } catch {
      setFailed(true); // not "your library is empty"
    } finally {
      setLoading(false);
    }
  };

  // Gone from the strip at once; the server keeps the place (the player asks whether to
  // resume). If it fails, the list comes back as the server has it
  const removeFromContinueWatching = (item: HeroItem) => {
    setContinueWatching((list) => list.filter((w) => w.id !== item.id));
    hideFromContinueWatching(item.id).catch(() => getContinueWatching(10).then(setContinueWatching));
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

  if (media.length === 0 && series.length === 0 && concerts.length === 0 && anime.length === 0) {
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

  const hero = heroItems(continueWatching, media, series, concerts, anime, t);

  return (
    <div className={`flex flex-col gap-8 ${isTV ? "px-8 py-8" : "px-4 md:px-8 py-6 md:py-8"}`}>
      {/* Continue Watching lives in the hero: the title on top, the others in its strip */}
      {hero.length > 0 && <HomeHero items={hero} onRemove={removeFromContinueWatching} />}

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

      {/* Concerti */}
      {concerts.length > 0 && (
        <section>
          <SectionHeader title={t("home.recentConcerts")} href="/concerts" />
          <StaggerGrid className={gridClass}>
            {concerts.map((c) => (
              <PosterCard
                key={c.id}
                href={`/media/${c.id}`}
                imageUrl={getTmdbImageUrl(c.poster_path, "w300")}
                title={c.title}
                subtitle={c.release_date ? yearOf(c.release_date) : ""}
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

      {/* Anime: series and films */}
      {anime.length > 0 && (
        <section>
          <SectionHeader title={t("home.recentAnime")} href="/anime" />
          <StaggerGrid className={gridClass}>
            {anime.map((a) => (
              <PosterCard
                key={`${a.kind}-${a.id}`}
                href={a.kind === "series" ? `/series/${a.id}` : `/media/${a.id}`}
                imageUrl={getTmdbImageUrl(a.poster_path, "w300")}
                title={a.title}
                subtitle={
                  a.kind === "movie"
                    ? [t("media.movieLabel"), a.date ? yearOf(a.date) : null].filter(Boolean).join(" · ")
                    : a.seasons_count === 1
                      ? `1 ${t("home.season")}`
                      : `${a.seasons_count ?? 0} ${t("home.seasons")}`
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
      <div className="-mx-4 md:-mx-8 -mt-6 md:-mt-8 h-[480px] md:h-[max(520px,64vh)] bg-[#18181b] animate-pulse" />
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
