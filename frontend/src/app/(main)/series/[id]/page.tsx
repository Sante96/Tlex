"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Play, RefreshCw, Pencil, Plus, Check } from "lucide-react";
import {
  HeroBanner,
  ActionButton,
  MetaRow,
  PosterCard,
  CastSection,
  DetailPageLayout,
  EditMediaModal,
} from "@/components/ds";
import {
  getSeriesDetails,
  getSeriesCast,
  refreshSeriesMetadata,
  addSeriesToWatchlist,
  removeSeriesFromWatchlist,
  checkSeriesWatchlistStatus,
  type SeriesDetails,
  type CastMember,
} from "@/lib/api";
import { getTmdbImageUrl } from "@/lib/format";

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

  const handleToggleWatchlist = async () => {
    if (!series) return;
    try {
      if (inWatchlist) {
        await removeSeriesFromWatchlist(series.id);
        setInWatchlist(false);
      } else {
        await addSeriesToWatchlist(series.id);
        setInWatchlist(true);
      }
    } catch {}
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
          setCast(castData.slice(0, 20));
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
        <p className="text-[#a1a1aa]">Serie non trovata</p>
        <button
          onClick={() => router.back()}
          className="text-[#e5a00d] text-sm mt-2 hover:underline"
        >
          Torna indietro
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
      >
        <h1 className="text-4xl font-bold text-[#fafafa]">{series.title}</h1>
        <div className="flex flex-col gap-1.5">
          {year && <span className="text-sm text-[#d4d4d8]">{year}</span>}
          {genresText && (
            <span className="text-sm text-[#d4d4d8]">{genresText}</span>
          )}
          <MetaRow
            voteAverage={series.vote_average}
            contentRating={series.content_rating}
            items={[
              {
                text: `${series.seasons_count} ${series.seasons_count === 1 ? "Stagione" : "Stagioni"}`,
              },
            ]}
          />
        </div>
        <div className="flex items-center gap-3">
          {nextEpisode && (
            <ActionButton
              variant="primary"
              icon={<Play className="h-5 w-5 fill-black" />}
              onClick={() => router.push(`/watch/${nextEpisode.id}`)}
            >
              Riproduci S{nextEpisode.season} E{nextEpisode.episode}
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
            {inWatchlist ? "In Watchlist" : "Watchlist"}
          </ActionButton>
          <ActionButton
            variant="secondary"
            icon={<Pencil className="h-4 w-4" />}
            onClick={() => setEditing(true)}
          >
            Modifica
          </ActionButton>
          <ActionButton
            variant="secondary"
            icon={
              <RefreshCw
                className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
              />
            }
            onClick={handleRefreshMetadata}
          >
            {refreshing ? "Aggiornamento..." : "Aggiorna Metadati"}
          </ActionButton>
        </div>
        {series.overview && (
          <p className="text-sm text-[#d4d4d8] leading-relaxed max-w-3xl">
            {series.overview}
          </p>
        )}
      </HeroBanner>

      {/* Seasons */}
      <div className="flex flex-col gap-6 px-12 py-8">
        <h2 className="text-2xl font-semibold text-[#fafafa]">Stagioni</h2>
        <div className="flex flex-wrap gap-5">
          {series.seasons.map((season) => {
            const seasonName =
              season.season_number === 0
                ? "Specials"
                : `Stagione ${season.season_number}`;
            return (
              <PosterCard
                key={season.season_number}
                href={`/series/${series.id}/season/${season.season_number}`}
                imageUrl={getTmdbImageUrl(
                  season.poster_path || series.poster_path,
                  "w300",
                )}
                title={seasonName}
                subtitle={`${season.episodes_count} Episodi`}
                width={160}
                height={240}
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
        <div className="px-12 pb-8">
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
      <div className="flex items-end gap-8 h-[432px] px-12 pb-8">
        <div className="w-[200px] h-[300px] bg-[#27272a] rounded-xl" />
        <div className="flex-1 space-y-4">
          <div className="h-10 w-72 bg-[#27272a] rounded" />
          <div className="h-5 w-48 bg-[#27272a] rounded" />
          <div className="h-4 w-full max-w-lg bg-[#27272a] rounded" />
          <div className="flex gap-3">
            <div className="h-11 w-40 bg-[#27272a] rounded-[10px]" />
            <div className="h-11 w-32 bg-[#27272a] rounded-[10px]" />
          </div>
        </div>
      </div>
      <div className="px-12 py-8">
        <div className="h-7 w-24 bg-[#27272a] rounded mb-6" />
        <div className="flex gap-5">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="w-[160px]">
              <div className="h-[240px] bg-[#27272a] rounded-lg" />
              <div className="h-4 w-3/4 bg-[#27272a] rounded mt-2" />
              <div className="h-3 w-1/2 bg-[#27272a] rounded mt-1" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
