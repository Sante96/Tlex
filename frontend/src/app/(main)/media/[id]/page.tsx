"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { ExpandableOverview } from "@/components/ui/expandable-overview";
import {
  Play,
  Plus,
  Check,
  Pencil,
  RefreshCw,
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
  getMediaDetails,
  getMediaList,
  getMediaCast,
  getMediaTrailer,
  refreshMetadata,
  addToWatchlist,
  removeFromWatchlist,
  checkWatchlistStatus,
  type MediaDetails,
  type MediaItem,
  type CastMember,
} from "@/lib/api";
import { formatDuration, getTmdbImageUrl } from "@/lib/format";
import { useToast } from "@/components/ui/toast";

export default function MediaDetailPage() {
  const params = useParams();
  const router = useRouter();
  const mediaId = Number(params.id);

  const [media, setMedia] = useState<MediaDetails | null>(null);
  const [similar, setSimilar] = useState<MediaItem[]>([]);
  const [cast, setCast] = useState<CastMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [inWatchlist, setInWatchlist] = useState(false);
  const [editing, setEditing] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [trailerKey, setTrailerKey] = useState<string | null>(null);
  const [showTrailer, setShowTrailer] = useState(false);
  const toast = useToast();
  const t = useTranslations();

  const handleRefreshMetadata = async () => {
    if (!media || refreshing) return;
    setRefreshing(true);
    try {
      await refreshMetadata(media.id);
      const data = await getMediaDetails(mediaId);
      setMedia(data);
    } catch {
    } finally {
      setRefreshing(false);
    }
  };

  const handleToggleWatchlist = async () => {
    if (!media) return;
    try {
      if (inWatchlist) {
        await removeFromWatchlist(media.id);
        setInWatchlist(false);
        toast(t("media.removedWatchlist"), "info");
      } else {
        await addToWatchlist(media.id);
        setInWatchlist(true);
        toast(t("media.addedWatchlist"), "success");
      }
    } catch {
      toast(t("media.watchlistError"), "error");
    }
  };

  useEffect(() => {
    const loadMedia = async () => {
      try {
        setLoading(true);
        const data = await getMediaDetails(mediaId);
        setMedia(data);

        try {
          const status = await checkWatchlistStatus(mediaId);
          setInWatchlist(status);
        } catch {}

        try {
          const allMovies = await getMediaList({
            media_type: "MOVIE",
            limit: 20,
          });
          setSimilar(
            allMovies.items.filter((m) => m.id !== mediaId).slice(0, 6),
          );
        } catch {
          // Similar media not available
        }
        try {
          const castData = await getMediaCast(mediaId);
          setCast(castData);
        } catch {}
        try {
          const key = await getMediaTrailer(mediaId);
          setTrailerKey(key);
        } catch {}
      } catch {
      } finally {
        setLoading(false);
      }
    };

    if (mediaId) loadMedia();
  }, [mediaId]);

  if (loading) return <DetailSkeleton />;

  if (!media) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-[#a1a1aa]">{t("media.notFound")}</p>
        <button
          onClick={() => router.back()}
          className="text-[#e5a00d] text-sm mt-2 hover:underline"
        >
          {t("media.goBack")}
        </button>
      </div>
    );
  }

  const posterUrl = getTmdbImageUrl(media.poster_path, "w500");
  const backdropUrl = getTmdbImageUrl(media.backdrop_path, "original");
  const year = media.release_date
    ? new Date(media.release_date).getFullYear()
    : null;
  const duration = media.duration_seconds
    ? formatDuration(media.duration_seconds)
    : null;
  const genresText = media.genres?.join(", ") || "";

  return (
    <DetailPageLayout backdropUrl={backdropUrl}>
      <HeroBanner
        height={432}
        posterUrl={posterUrl}
        posterAlt={media.title}
        posterWidth={200}
        posterHeight={300}
        mobileInfoSlot={
          <>
            <h1 className="text-xl md:text-4xl font-bold text-[#fafafa] leading-tight">
              {media.title}
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
                voteAverage={media.vote_average}
                contentRating={media.content_rating}
                items={duration ? [{ text: duration }] : []}
              />
            </div>
          </>
        }
      >
        <div className="flex flex-wrap items-center gap-2 md:gap-3">
          <ActionButton
            variant="primary"
            icon={<Play className="h-5 w-5 fill-black" />}
            onClick={() => router.push(`/watch/${media.id}`)}
          >
            {t("media.play")}
          </ActionButton>
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
          {trailerKey && (
            <ActionButton
              variant="secondary"
              icon={<Clapperboard className="h-4 w-4" />}
              onClick={() => setShowTrailer(true)}
            >
              {t("media.trailer")}
            </ActionButton>
          )}
          <ActionButton
            variant="secondary"
            icon={<Pencil className="h-4 w-4" />}
            onClick={() => setEditing(true)}
          >
            {t("media.edit")}
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
            {refreshing ? t("media.refreshing") : t("media.refresh")}
          </ActionButton>
        </div>
        {media.overview && (
          <ExpandableOverview text={media.overview} />
        )}
      </HeroBanner>

      {showTrailer && trailerKey && (
        <TrailerModal
          youtubeKey={trailerKey}
          onClose={() => setShowTrailer(false)}
        />
      )}

      {/* Similar Movies */}
      {similar.length > 0 && (
        <div className="flex flex-col gap-6 px-4 md:px-12 py-4 md:py-8">
          <h2 className="text-2xl font-semibold text-[#fafafa]">{t("media.similarMovies")}</h2>
          <div className="flex overflow-x-auto md:overflow-visible md:grid md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-7 2xl:grid-cols-9 gap-3 md:gap-4 scrollbar-hide pb-3 md:pb-0">
            {similar.map((item) => (
              <PosterCard
                key={item.id}
                href={`/media/${item.id}`}
                imageUrl={getTmdbImageUrl(item.poster_path, "w300")}
                title={item.title}
                subtitle={
                  item.release_date
                    ? new Date(item.release_date).getFullYear().toString()
                    : ""
                }
                className="shrink-0 w-[120px] md:w-full"
              />
            ))}
          </div>
        </div>
      )}

      {/* Cast */}
      {cast.length > 0 && (
        <div className="px-4 md:px-12 pb-4 md:pb-8">
          <CastSection cast={cast} />
        </div>
      )}
      {/* Edit Modal */}
      {editing && (
        <EditMediaModal
          mediaId={media.id}
          title={media.title}
          overview={media.overview}
          posterPath={media.poster_path}
          backdropPath={media.backdrop_path}
          releaseDate={media.release_date}
          onClose={() => setEditing(false)}
          onSaved={async () => {
            const data = await getMediaDetails(mediaId);
            setMedia(data);
          }}
        />
      )}
    </DetailPageLayout>
  );
}

function DetailSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="flex items-end gap-8 h-[374px] px-4 md:px-12 pb-8">
        <div className="w-[180px] h-[270px] bg-[#27272a] rounded-xl hidden md:block" />
        <div className="flex-1 space-y-4">
          <div className="h-10 w-72 bg-[#27272a] rounded" />
          <div className="h-5 w-48 bg-[#27272a] rounded" />
          <div className="h-4 w-full max-w-lg bg-[#27272a] rounded" />
          <div className="flex gap-3">
            <div className="h-11 w-36 bg-[#27272a] rounded-[10px]" />
            <div className="h-11 w-32 bg-[#27272a] rounded-[10px]" />
          </div>
        </div>
      </div>
    </div>
  );
}
