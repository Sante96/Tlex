"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  HeroBanner,
  MetaRow,
  EpisodeCard,
  CastSection,
  DetailPageLayout,
} from "@/components/ds";
import {
  getSeriesDetails,
  getSeriesCast,
  type SeriesDetails,
  type SeasonInfo,
  type CastMember,
} from "@/lib/api";
import {
  formatDurationShort,
  cleanEpisodeTitle,
  getTmdbImageUrl,
} from "@/lib/format";

function getSeasonName(seasonNumber: number): string {
  return seasonNumber === 0 ? "Specials" : `Stagione ${seasonNumber}`;
}

export default function SeasonDetailPage() {
  const params = useParams();
  const router = useRouter();
  const seriesId = Number(params.id);
  const seasonNumber = Number(params.season);
  const seasonName = getSeasonName(seasonNumber);

  const [series, setSeries] = useState<SeriesDetails | null>(null);
  const [season, setSeason] = useState<SeasonInfo | null>(null);
  const [cast, setCast] = useState<CastMember[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const data = await getSeriesDetails(seriesId);
        setSeries(data);
        const seasonData = data.seasons.find(
          (s) => s.season_number === seasonNumber,
        );
        setSeason(seasonData || null);
        try {
          const castData = await getSeriesCast(seriesId);
          setCast(castData.slice(0, 20));
        } catch {}
      } catch {
      } finally {
        setLoading(false);
      }
    };

    if (seriesId && seasonNumber !== undefined && !isNaN(seasonNumber)) {
      loadData();
    }
  }, [seriesId, seasonNumber]);

  if (loading) return <SeasonSkeleton />;

  if (!series || !season) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-[#a1a1aa]">Stagione non trovata</p>
        <button
          onClick={() => router.back()}
          className="text-[#e5a00d] text-sm mt-2 hover:underline"
        >
          Torna indietro
        </button>
      </div>
    );
  }

  const posterUrl = getTmdbImageUrl(
    season.poster_path || series.poster_path,
    "w500",
  );
  const backdropUrl = getTmdbImageUrl(series.backdrop_path, "w1280");

  return (
    <DetailPageLayout backdropUrl={backdropUrl}>
      <HeroBanner
        height={200}
        posterUrl={posterUrl}
        posterAlt={`${series.title} - ${seasonName}`}
        posterWidth={100}
        posterHeight={150}
        align="center"
      >
        <h1 className="text-[28px] font-bold text-[#fafafa]">{series.title}</h1>
        <MetaRow
          voteAverage={series.vote_average}
          items={[
            { text: seasonName },
            { text: `${season.episodes_count} Episodi` },
          ]}
        />
        {series.overview && (
          <p className="text-[13px] text-[#e4e4e7] leading-relaxed line-clamp-2 max-w-2xl">
            {series.overview}
          </p>
        )}
      </HeroBanner>

      {/* Episodes */}
      <div className="flex flex-col gap-6 px-12 py-8">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-semibold text-[#fafafa]">Episodi</h2>
          <span className="text-sm text-[#a1a1aa]">
            {season.episodes_count} episodi
          </span>
        </div>

        <div className="flex flex-col gap-3">
          {season.episodes.map((ep) => {
            const progressPercent = ep.watch_progress?.progress_percent ?? 0;
            const isWatched = ep.watch_progress?.is_completed ?? false;

            return (
              <EpisodeCard
                key={ep.id}
                episodeNumber={ep.episode_number ?? 0}
                title={cleanEpisodeTitle(ep.title)}
                duration={
                  ep.duration_seconds
                    ? (formatDurationShort(ep.duration_seconds) ?? undefined)
                    : undefined
                }
                overview={ep.overview ?? undefined}
                thumbnailUrl={getTmdbImageUrl(ep.still_path, "w500")}
                progress={!isWatched ? progressPercent : undefined}
                onClick={() => router.push(`/watch/${ep.id}`)}
              />
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
    </DetailPageLayout>
  );
}

function SeasonSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="flex items-center gap-6 h-[200px] px-12">
        <div className="w-[100px] h-[150px] bg-[#27272a] rounded-lg" />
        <div className="flex-1 space-y-3">
          <div className="h-8 w-48 bg-[#27272a] rounded" />
          <div className="h-5 w-32 bg-[#27272a] rounded" />
          <div className="h-4 w-full max-w-md bg-[#27272a] rounded" />
        </div>
      </div>
      <div className="px-12 py-8">
        <div className="h-7 w-20 bg-[#27272a] rounded mb-6" />
        <div className="flex flex-col gap-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-[120px] bg-[#18181b] rounded-xl" />
          ))}
        </div>
      </div>
    </div>
  );
}
