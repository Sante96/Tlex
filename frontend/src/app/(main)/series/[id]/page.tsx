"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { ExpandableOverview } from "@/components/ui/expandable-overview";
import {
  Play,
  RefreshCw,
  Pencil,
  Plus,
  Check,
  Clapperboard,
} from "lucide-react";
import {
  HeroBanner,
  ActionButton,
  MetaRow,
  PosterCard,
  CastSection,
  DetailPageLayout,
  EditMediaModal,
  TrailerModal,
} from "@/components/ds";
import {
  getSeriesDetails,
  getSeriesCast,
  getSeriesTrailer,
  refreshSeriesMetadata,
  addSeriesToWatchlist,
  removeSeriesFromWatchlist,
  checkSeriesWatchlistStatus,
  type SeriesDetails,
  type CastMember,
} from "@/lib/api";
import { getTmdbImageUrl } from "@/lib/format";
import { useToast } from "@/components/ui/toast";
import { useIsTV } from "@/hooks/use-platform";

export default function SeriesDetailPage() {
  const params = useParams();
  const router = useRouter();
  const seriesId = Number(params.id);

  const [series, setSeries] = useState<SeriesDetails | null>(null);
  const [cast, setCast] = useState<CastMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [editing, setEditing] = useState(false);
  const [inWatchlist, setInWatchlist] = useState(false);
  const [trailerKey, setTrailerKey] = useState<string | null>(null);
  const [showTrailer, setShowTrailer] = useState(false);
  const toast = useToast();
  const t = useTranslations();
  const isTV = useIsTV();

  const handleToggleWatchlist = async () => {
    if (!series) return;
    try {
      if (inWatchlist) {
        await removeSeriesFromWatchlist(series.id);
        setInWatchlist(false);
        toast(t("media.removedWatchlist"), "info");
      } else {
        await addSeriesToWatchlist(series.id);
        setInWatchlist(true);
        toast(t("media.addedWatchlist"), "success");
      }
    } catch {
      toast(t("media.watchlistError"), "error");
    }
  };

  const handleRefreshMetadata = async () => {
    if (!series || refreshing) return;
    setRefreshing(true);
    try {
      await refreshSeriesMetadata(seriesId);
      const data = await getSeriesDetails(seriesId);
      setSeries(data);
    } catch {
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    const loadSeries = async () => {
      try {
        setLoading(true);
        const data = await getSeriesDetails(seriesId);
        setSeries(data);
        try {
          const status = await checkSeriesWatchlistStatus(seriesId);
          setInWatchlist(status);
        } catch {}
        try {
          const castData = await getSeriesCast(seriesId);
          setCast(castData);
        } catch {}
        try {
          const key = await getSeriesTrailer(seriesId);
          setTrailerKey(key);
        } catch {}
      } catch {
      } finally {
        setLoading(false);
      }
    };

    if (seriesId) loadSeries();
  }, [seriesId]);

  if (loading) return <SeriesSkeleton />;

  if (!series) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-[#a1a1aa]">{t("media.notFound")}</p>
        <button
          onClick={() => router.back()}
          className="text-[#e5a00d] text-sm mt-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#e5a00d] rounded"
        >
          {t("media.goBack")}
        </button>
      </div>
    );
  }

  const posterUrl = getTmdbImageUrl(series.poster_path, "w500");
  const backdropUrl = getTmdbImageUrl(series.backdrop_path, "original");
  const year = series.first_air_date
    ? new Date(series.first_air_date).getFullYear()
    : null;
  const genresText = series.genres?.join(", ") || "";

  // Find next episode to watch: skip Specials (S0), find first non-completed episode
  const nextEpisode = (() => {
    const regularSeasons = series.seasons.filter((s) => s.season_number > 0);
    for (const s of regularSeasons) {
      for (const ep of s.episodes) {
        if (!ep.watch_progress?.is_completed) {
          return {
            id: ep.id,
            season: s.season_number,
            episode: ep.episode_number ?? 1,
          };
        }
      }
    }
    // All watched — fallback to first regular episode
    const firstSeason = regularSeasons[0] || series.seasons[0];
    const firstEp = firstSeason?.episodes[0];
    if (firstSeason && firstEp) {
      return {
        id: firstEp.id,
        season: firstSeason.season_number,
        episode: firstEp.episode_number ?? 1,
      };
    }
    return null;
  })();

  return (
    <DetailPageLayout backdropUrl={backdropUrl}>
      <HeroBanner
        height={432}
        posterUrl={posterUrl}
        posterAlt={series.title}
        posterWidth={200}
        posterHeight={300}
        mobileInfoSlot={
          <>
            <h1 className="text-xl md:text-4xl font-bold text-[#fafafa] leading-tight">
              {series.title}
            </h1>
            <div className="flex flex-col gap-1">
              {year && (
                <span className="text-xs md:text-sm text-[#d4d4d8]">
                  {year}
                </span>
              )}
              {genresText && (
                <span className="text-xs md:text-sm text-[#d4d4d8] line-clamp-2">
                  {genresText}
                </span>
              )}
              <MetaRow
                voteAverage={series.vote_average}
                contentRating={series.content_rating}
                items={[
                  {
                    text: `${series.seasons_count} ${series.seasons_count === 1 ? t("media.season") : t("media.seasons")}`,
                  },
                ]}
              />
            </div>
          </>
        }
      >
        <div className="flex flex-wrap items-center gap-2 md:gap-3">
          {nextEpisode && (
            <ActionButton
              variant="primary"
              icon={<Play className="h-5 w-5 fill-black" />}
              onClick={() => router.push(`/watch/${nextEpisode.id}`)}
            >
              {t("media.play")} S{nextEpisode.season} E{nextEpisode.episode}
            </ActionButton>
          )}
          <ActionButton
            variant="secondary"
            icon={
              inWatchlist ? (
                <Check className="h-5 w-5" />
              ) : (
                <Plus className="h-5 w-5" />
              )
            }
            onClick={handleToggleWatchlist}
          >
            {inWatchlist ? t("media.inWatchlist") : t("media.addWatchlist")}
          </ActionButton>
          {trailerKey && !isTV && (
            <ActionButton
              variant="secondary"
              icon={<Clapperboard className="h-4 w-4" />}
              onClick={() => setShowTrailer(true)}
            >
              {t("media.trailer")}
            </ActionButton>
          )}
          {!isTV && (
            <ActionButton
              variant="secondary"
              icon={<Pencil className="h-4 w-4" />}
              onClick={() => setEditing(true)}
            >
              {t("media.edit")}
            </ActionButton>
          )}
          <ActionButton
            variant="secondary"
            icon={
              <RefreshCw
                className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
              />
            }
            onClick={handleRefreshMetadata}
          >
            {refreshing ? t("media.refreshing") : t("media.refresh")}
          </ActionButton>
        </div>
        {series.overview && <ExpandableOverview text={series.overview} />}
      </HeroBanner>

      {showTrailer && trailerKey && (
        <TrailerModal
          youtubeKey={trailerKey}
          onClose={() => setShowTrailer(false)}
        />
      )}

      {/* Seasons */}
      <div className={`flex flex-col gap-6 py-4 md:py-8 ${isTV ? "px-8" : "px-4 md:px-12"}`}>
        <h2 className="text-2xl font-semibold text-[#fafafa]">
          {t("media.seasons")}
        </h2>
        <div className={isTV
          ? "grid grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8 gap-4"
          : "flex overflow-x-auto md:overflow-visible md:grid md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-7 2xl:grid-cols-9 gap-3 md:gap-4 scrollbar-hide pb-3 md:pb-0"
        }>
          {series.seasons.map((season) => {
            const seasonName =
              season.season_number === 0
                ? t("media.specials")
                : `${t("media.season")} ${season.season_number}`;
            return (
              <PosterCard
                key={season.season_number}
                href={`/series/${series.id}/season/${season.season_number}`}
                imageUrl={getTmdbImageUrl(
                  season.poster_path || series.poster_path,
                  "w300",
                )}
                title={seasonName}
                subtitle={`${season.episodes_count} ${t("media.episodes")}`}
                className={isTV ? "" : "shrink-0 w-[120px] md:w-full"}
              >
                <span className="absolute top-2 right-2 flex items-center justify-center min-w-6 h-6 px-1.5 rounded-full bg-black/70 text-white text-xs font-bold">
                  {season.episodes_count}
                </span>
              </PosterCard>
            );
          })}
        </div>
      </div>

      {/* Cast */}
      {cast.length > 0 && (
        <div className={isTV ? "px-8 pb-8" : "px-4 md:px-12 pb-4 md:pb-8"}>
          <CastSection cast={cast} />
        </div>
      )}
      {/* Edit Modal */}
      {editing && series && (
        <EditMediaModal
          mediaId={series.id}
          title={series.title}
          overview={series.overview}
          posterPath={series.poster_path}
          backdropPath={series.backdrop_path}
          releaseDate={series.first_air_date}
          entityType="series"
          onClose={() => setEditing(false)}
          onSaved={async () => {
            const data = await getSeriesDetails(seriesId);
            setSeries(data);
          }}
        />
      )}
    </DetailPageLayout>
  );
}

function SeriesSkeleton() {
  return (
    <div className="animate-pulse">
      {/* Hero — matches HeroBanner height=432 with backdrop gradient */}
      <div className="relative h-auto md:h-[432px] bg-[#18181b]">
        <div className="absolute inset-0 bg-gradient-to-t from-[#09090b] via-[#09090b]/60 to-transparent hidden md:block" />

        {/* Mobile layout: poster + info row */}
        <div className="flex md:hidden flex-col gap-4 px-4 pt-5 pb-4">
          <div className="flex items-end gap-3">
            <div className="w-[90px] h-[135px] bg-[#27272a] rounded-xl shrink-0" />
            <div className="flex flex-col gap-2 flex-1 min-w-0 pb-1">
              <div className="h-6 w-40 bg-[#27272a] rounded" />
              <div className="h-4 w-24 bg-[#27272a] rounded" />
              <div className="h-4 w-32 bg-[#27272a] rounded" />
            </div>
          </div>
          <div className="flex gap-2">
            <div className="h-10 w-36 bg-[#27272a] rounded-[10px]" />
            <div className="h-10 w-28 bg-[#27272a] rounded-[10px]" />
          </div>
          <div className="h-3 w-full bg-[#27272a] rounded" />
          <div className="h-3 w-4/5 bg-[#27272a] rounded" />
        </div>

        {/* Desktop layout: poster + info at bottom */}
        <div className="hidden md:flex absolute bottom-0 left-0 right-0 items-end gap-8 px-12 pb-8">
          <div className="w-[200px] h-[300px] bg-[#27272a] rounded-xl shrink-0" />
          <div className="flex flex-col gap-4 flex-1 min-w-0">
            <div className="h-10 w-72 bg-[#27272a] rounded" />
            <div className="h-5 w-48 bg-[#27272a] rounded" />
            <div className="h-4 w-full max-w-lg bg-[#27272a] rounded" />
            <div className="flex gap-3">
              <div className="h-11 w-44 bg-[#27272a] rounded-[10px]" />
              <div className="h-11 w-32 bg-[#27272a] rounded-[10px]" />
              <div className="h-11 w-24 bg-[#27272a] rounded-[10px]" />
            </div>
          </div>
        </div>
      </div>

      {/* Seasons — matches flex overflow-x-auto md:grid md:grid-cols-3 lg:grid-cols-5 */}
      <div className="px-4 md:px-12 py-4 md:py-8">
        <div className="h-7 w-24 bg-[#27272a] rounded mb-6" />
        <div className="flex gap-3 md:grid md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-7 2xl:grid-cols-9 overflow-hidden">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="shrink-0 w-[120px] md:w-full">
              <div className="aspect-[2/3] bg-[#27272a] rounded-xl" />
              <div className="h-4 w-3/4 bg-[#27272a] rounded mt-2" />
              <div className="h-3 w-1/2 bg-[#27272a] rounded mt-1" />
            </div>
          ))}
        </div>
      </div>

      {/* Cast row */}
      <div className="px-4 md:px-12 pb-8">
        <div className="h-7 w-16 bg-[#27272a] rounded mb-5" />
        <div className="flex gap-5">
          {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
            <div
              key={i}
              className="flex flex-col items-center gap-2 shrink-0 w-[200px]"
            >
              <div className="w-[200px] h-[200px] rounded-full bg-[#27272a]" />
              <div className="h-3 w-24 bg-[#27272a] rounded" />
              <div className="h-2.5 w-16 bg-[#27272a] rounded" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
