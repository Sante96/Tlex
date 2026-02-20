"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Play, Plus, Check, Pencil, RefreshCw } from "lucide-react";
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
  getMediaDetails,
  getMediaList,
  getMediaCast,
  refreshMetadata,
  addToWatchlist,
  removeFromWatchlist,
  checkWatchlistStatus,
  type MediaDetails,
  type MediaItem,
  type CastMember,
} from "@/lib/api";
import { formatDuration, getTmdbImageUrl } from "@/lib/format";

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
      } else {
        await addToWatchlist(media.id);
        setInWatchlist(true);
      }
    } catch {}
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
          setCast(castData.slice(0, 20));
        } catch {
          // Similar media not available
        }
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
        <p className="text-[#a1a1aa]">Media non trovato</p>
        <button
          onClick={() => router.back()}
          className="text-[#e5a00d] text-sm mt-2 hover:underline"
        >
          Torna indietro
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
        height={374}
        posterUrl={posterUrl}
        posterAlt={media.title}
        posterWidth={180}
        posterHeight={270}
      >
        <h1 className="text-4xl font-bold text-[#fafafa]">{media.title}</h1>
        <div className="flex flex-col gap-1.5">
          <span className="text-sm text-[#d4d4d8]">
            {[year, duration].filter(Boolean).join(" · ")}
          </span>
          {genresText && (
            <span className="text-sm text-[#d4d4d8]">{genresText}</span>
          )}
          <MetaRow
            voteAverage={media.vote_average}
            contentRating={media.content_rating}
            items={[]}
          />
        </div>
        <div className="flex items-center gap-3">
          <ActionButton
            variant="primary"
            icon={<Play className="h-5 w-5 fill-black" />}
            onClick={() => router.push(`/watch/${media.id}`)}
          >
            Riproduci
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
        {media.overview && (
          <p className="text-sm text-[#d4d4d8] leading-relaxed max-w-3xl">
            {media.overview}
          </p>
        )}
      </HeroBanner>

      {/* Similar Movies */}
      {similar.length > 0 && (
        <div className="flex flex-col gap-6 px-12 py-8">
          <h2 className="text-2xl font-semibold text-[#fafafa]">Film simili</h2>
          <div className="flex flex-wrap gap-5">
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
                width={160}
                height={240}
              />
            ))}
          </div>
        </div>
      )}

      {/* Cast */}
      {cast.length > 0 && (
        <div className="px-12 pb-8">
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
      <div className="flex items-end gap-8 h-[374px] px-12 pb-8">
        <div className="w-[180px] h-[270px] bg-[#27272a] rounded-xl" />
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
