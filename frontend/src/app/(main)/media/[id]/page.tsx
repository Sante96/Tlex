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
import { isAxiosError } from "axios";
import {
  HeroBanner,
  ActionButton,
  MetaRow,
  CastSection,
  DetailPageLayout,
  EditMediaModal,
  TrailerModal,
  HeroBannerSkeleton,
} from "@/components/ds";
import {
  getMediaDetails,
  getMediaCast,
  getMediaTrailer,
  refreshMetadata,
  addToWatchlist,
  removeFromWatchlist,
  checkWatchlistStatus,
  type MediaDetails,
  type CastMember,
} from "@/lib/api";
import { formatDuration, getTmdbImageUrl, yearOf } from "@/lib/format";
import { useToast } from "@/components/ui/toast";
import { useIsTV } from "@/hooks/use-platform";
import { useAuth } from "@/contexts/auth-context";
import { useDelayed } from "@/hooks/use-delayed";

export default function MediaDetailPage() {
  const params = useParams();
  const router = useRouter();
  const mediaId = Number(params.id);

  const [media, setMedia] = useState<MediaDetails | null>(null);
  const [cast, setCast] = useState<CastMember[]>([]);
  const [loading, setLoading] = useState(true);
  const showSkeleton = useDelayed(loading);
  const [failed, setFailed] = useState(false); // a load error, not a 404
  const [attempt, setAttempt] = useState(0);
  const [inWatchlist, setInWatchlist] = useState(false);
  const [editing, setEditing] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [trailerKey, setTrailerKey] = useState<string | null>(null);
  const [showTrailer, setShowTrailer] = useState(false);
  const toast = useToast();
  const t = useTranslations();
  const isTV = useIsTV();
  const { user } = useAuth();

  const handleRefreshMetadata = async () => {
    if (!media || refreshing) return;
    setRefreshing(true);
    try {
      await refreshMetadata(media.id);
      const data = await getMediaDetails(mediaId);
      setMedia(data);
    } catch {
      toast(t("common.error"), "error");
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

  // The page shows as soon as the details arrive; watchlist, cast and trailer (TMDB calls)
  // fill in when they do, instead of five requests one after the other
  useEffect(() => {
    // /media/abc: "not found" instead of a skeleton forever
    if (!Number.isInteger(mediaId)) return;
    let alive = true;
    getMediaDetails(mediaId)
      .then((data) => alive && setMedia(data))
      .catch((e) => alive && setFailed(!(isAxiosError(e) && e.response?.status === 404)))
      .finally(() => alive && setLoading(false));
    checkWatchlistStatus(mediaId).then((s) => alive && setInWatchlist(s), () => {});
    getMediaCast(mediaId).then((c) => alive && setCast(c), () => {});
    getMediaTrailer(mediaId).then((k) => alive && setTrailerKey(k), () => {});
    return () => {
      alive = false;
    };
  }, [mediaId, attempt]);

  if (loading && Number.isInteger(mediaId)) return showSkeleton ? <DetailSkeleton /> : null;

  if (failed) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20">
        <p className="text-[#a1a1aa]">{t("common.loadError")}</p>
        <ActionButton
          variant="secondary"
          icon={<RefreshCw className="h-4 w-4" />}
          onClick={() => {
            setFailed(false);
            setLoading(true);
            setAttempt((n) => n + 1);
          }}
        >
          {t("common.retry")}
        </ActionButton>
      </div>
    );
  }

  if (!media) {
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

  const posterUrl = getTmdbImageUrl(media.poster_path, "w500");
  const backdropUrl = getTmdbImageUrl(media.backdrop_path, "original");
  const year = media.release_date
    ? yearOf(media.release_date)
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
          {/* Re-reading TMDB takes an admin: it failed silently for everyone else */}
          {user?.is_admin && (
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
          )}
        </div>
        {media.overview && <ExpandableOverview text={media.overview} />}
      </HeroBanner>

      {showTrailer && trailerKey && (
        <TrailerModal
          youtubeKey={trailerKey}
          onClose={() => setShowTrailer(false)}
        />
      )}

      {/* Cast */}
      {cast.length > 0 && (
        <div className={isTV ? "px-8 pb-8" : "px-4 md:px-12 pb-4 md:pb-8"}>
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
      <HeroBannerSkeleton buttons={4} />
    </div>
  );
}
