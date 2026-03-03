"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Pencil } from "lucide-react";
import {
  HeroBanner,
  ActionButton,
  MetaRow,
  EpisodeCard,
  CastSection,
  DetailPageLayout,
  EditMediaModal,
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
import { ExpandableOverview } from "@/components/ui/expandable-overview";

export default function SeasonDetailPage() {
  const t = useTranslations();
  const params = useParams();
  const router = useRouter();
  const seriesId = Number(params.id);
  const seasonNumber = Number(params.season);
  const seasonName =
    seasonNumber === 0
      ? t("media.specials")
      : `${t("media.season")} ${seasonNumber}`;

  const [series, setSeries] = useState<SeriesDetails | null>(null);
  const [season, setSeason] = useState<SeasonInfo | null>(null);
  const [cast, setCast] = useState<CastMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingSeason, setEditingSeason] = useState(false);
  const [editingEpisode, setEditingEpisode] = useState<{
    id: number;
    title: string;
    overview: string | null;
    posterPath: string | null;
    episodeNumber: number | null;
    releaseDate: string | null;
  } | null>(null);

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
        <p className="text-[#a1a1aa]">{t("media.seasonNotFound")}</p>
        <button
          onClick={() => router.back()}
          className="text-[#e5a00d] text-sm mt-2 hover:underline"
        >
          {t("media.goBack")}
        </button>
      </div>
    );
  }

  const posterUrl = getTmdbImageUrl(
    season.poster_path || series.poster_path,
    "w500",
  );
  const backdropUrl = getTmdbImageUrl(series.backdrop_path, "original");
  const year = series.first_air_date
    ? new Date(series.first_air_date).getFullYear()
    : null;
  const genresText = series.genres?.join(", ") || "";

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
              <span className="text-sm font-semibold text-[#d4d4d8]">
                {seasonName}
              </span>
              <span className="text-xs text-[#d4d4d8]">
                {season.episodes_count} {t("media.episodes")}
              </span>
              {genresText && (
                <span className="text-xs text-[#d4d4d8] line-clamp-1">
                  {genresText}
                </span>
              )}
              <MetaRow
                voteAverage={series.vote_average}
                contentRating={series.content_rating}
                items={year ? [{ text: String(year) }] : []}
              />
            </div>
          </>
        }
      >
        <div className="flex">
          <ActionButton
            variant="secondary"
            icon={<Pencil className="h-4 w-4" />}
            onClick={() => setEditingSeason(true)}
          >
            {t("media.editSeason")}
          </ActionButton>
        </div>
        {series.overview && <ExpandableOverview text={series.overview} />}
      </HeroBanner>

      {/* Episodes */}
      <div className="flex flex-col gap-6 px-4 md:px-12 py-4 md:py-8">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-semibold text-[#fafafa]">
            {t("media.episodes")}
          </h2>
          <span className="text-sm text-[#a1a1aa]">
            {season.episodes_count} {t("media.episodes").toLowerCase()}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
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
                thumbnailUrl={getTmdbImageUrl(ep.still_path, "original")}
                progress={!isWatched ? progressPercent : undefined}
                isWatched={isWatched}
                onClick={() => router.push(`/watch/${ep.id}`)}
                onEdit={() =>
                  setEditingEpisode({
                    id: ep.id,
                    title: ep.title,
                    overview: ep.overview,
                    posterPath: ep.still_path,
                    episodeNumber: ep.episode_number,
                    releaseDate: ep.release_date,
                  })
                }
              />
            );
          })}
        </div>
      </div>

      {/* Cast */}
      {cast.length > 0 && (
        <div className="px-4 md:px-12 pb-4 md:pb-8">
          <CastSection cast={cast} />
        </div>
      )}
      {/* Season Edit Modal */}
      {editingSeason && series && (
        <EditMediaModal
          mediaId={series.id}
          title={seasonName}
          overview={null}
          posterPath={season.poster_path}
          releaseDate={null}
          entityType="season"
          seriesId={seriesId}
          seriesTitle={series.title}
          seasonNumber={seasonNumber}
          onClose={() => setEditingSeason(false)}
          onSaved={async () => {
            const data = await getSeriesDetails(seriesId);
            setSeries(data);
            const seasonData = data.seasons.find(
              (s) => s.season_number === seasonNumber,
            );
            setSeason(seasonData || null);
          }}
        />
      )}
      {/* Episode Edit Modal */}
      {editingEpisode && series && (
        <EditMediaModal
          mediaId={editingEpisode.id}
          title={editingEpisode.title}
          overview={editingEpisode.overview}
          posterPath={editingEpisode.posterPath}
          releaseDate={editingEpisode.releaseDate}
          seriesTitle={series.title}
          seasonNumber={seasonNumber}
          episodeNumber={editingEpisode.episodeNumber}
          onClose={() => setEditingEpisode(null)}
          onSaved={async () => {
            const data = await getSeriesDetails(seriesId);
            setSeries(data);
            const seasonData = data.seasons.find(
              (s) => s.season_number === seasonNumber,
            );
            setSeason(seasonData || null);
          }}
        />
      )}
    </DetailPageLayout>
  );
}

function SeasonSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="flex items-center gap-6 h-[200px] px-4 md:px-12">
        <div className="w-[100px] h-[150px] bg-[#27272a] rounded-lg hidden md:block" />
        <div className="flex-1 space-y-3">
          <div className="h-8 w-48 bg-[#27272a] rounded" />
          <div className="h-5 w-32 bg-[#27272a] rounded" />
          <div className="h-4 w-full max-w-md bg-[#27272a] rounded" />
        </div>
      </div>
      <div className="px-4 md:px-12 py-4 md:py-8">
        <div className="h-7 w-20 bg-[#27272a] rounded mb-6" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="aspect-video bg-[#27272a] rounded-lg" />
          ))}
        </div>
      </div>
    </div>
  );
}
