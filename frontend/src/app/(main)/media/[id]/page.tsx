"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Image from "next/image";
import { Play, Check, Share2, RefreshCw, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { WatchlistButton } from "@/components/watchlist-button";
import {
  getMediaDetails,
  refreshMetadata,
  getMediaCast,
  getMediaEpisodes,
  type MediaDetails,
  type CastMember,
  type EpisodeInfo,
} from "@/lib/api";
import { motion } from "framer-motion";
import { formatDuration, formatBytes, getTmdbImageUrl } from "@/lib/format";
import { PageTransition } from "@/components/motion";
import { HorizontalScroll } from "@/components/horizontal-scroll";

export default function MediaDetailPage() {
  const params = useParams();
  const router = useRouter();
  const mediaId = Number(params.id);

  const [media, setMedia] = useState<MediaDetails | null>(null);
  const [cast, setCast] = useState<CastMember[]>([]);
  const [episodes, setEpisodes] = useState<EpisodeInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    const loadMedia = async () => {
      try {
        setLoading(true);
        const data = await getMediaDetails(mediaId);
        setMedia(data);

        // Load cast for all media with tmdb_id
        if (data.tmdb_id) {
          const castData = await getMediaCast(mediaId);
          setCast(castData);

          // Load episodes only for TV shows
          if (data.media_type === "EPISODE") {
            const episodesData = await getMediaEpisodes(mediaId);
            setEpisodes(episodesData);
          }
        }
      } catch (error) {
        console.error("Failed to load media:", error);
      } finally {
        setLoading(false);
      }
    };

    if (mediaId) {
      loadMedia();
    }
  }, [mediaId]);

  const handleRefreshMetadata = async () => {
    if (!media || refreshing) return;

    try {
      setRefreshing(true);
      const result = await refreshMetadata(media.id);
      // Reload media details to get updated data
      const updated = await getMediaDetails(media.id);
      setMedia(updated);
      alert(`Metadati aggiornati: ${result.title}`);
    } catch (error) {
      console.error("Failed to refresh metadata:", error);
      alert("Errore nel refresh dei metadati");
    } finally {
      setRefreshing(false);
    }
  };

  if (loading) {
    return <DetailSkeleton />;
  }

  if (!media) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-muted-foreground">Media non trovato</p>
        <Button variant="link" onClick={() => router.back()}>
          Torna indietro
        </Button>
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

  const audioTracks = media.streams.filter((s) => s.codec_type === "AUDIO");
  const subtitleTracks = media.streams.filter(
    (s) => s.codec_type === "SUBTITLE",
  );
  const videoTrack = media.streams.find((s) => s.codec_type === "VIDEO");

  return (
    <PageTransition>
      <div className="relative -m-6">
        {/* Backdrop */}
        {backdropUrl && (
          <motion.div
            className="fixed inset-0 overflow-hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5 }}
          >
            <Image
              src={backdropUrl}
              alt=""
              fill
              className="object-cover opacity-20"
              priority
            />
            <div className="absolute inset-0 bg-gradient-to-b from-zinc-950/50 via-zinc-950/80 to-zinc-950" />
          </motion.div>
        )}

        <div className="relative z-10 space-y-6 p-6">
          {/* Back button */}
          <Button variant="ghost" size="sm" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Indietro
          </Button>

          {/* Main content */}
          <motion.div
            className="flex gap-8"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.4 }}
          >
            {/* Poster */}
            <motion.div
              className="shrink-0 w-[200px]"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.2, duration: 0.4 }}
            >
              {posterUrl ? (
                <Image
                  src={posterUrl}
                  alt={media.title}
                  width={200}
                  height={300}
                  className="rounded-md"
                />
              ) : (
                <div className="w-[200px] h-[300px] bg-zinc-800 rounded-md flex items-center justify-center text-zinc-600">
                  No Poster
                </div>
              )}
            </motion.div>

            {/* Info */}
            <div className="flex-1 space-y-4">
              <div>
                <h1 className="text-3xl font-bold text-white">{media.title}</h1>
                <div className="flex items-center gap-2 text-sm text-muted-foreground mt-1">
                  {year && <span>{year}</span>}
                  {duration && (
                    <>
                      <span>•</span>
                      <span>{duration}</span>
                    </>
                  )}
                  {media.media_type === "EPISODE" && (
                    <>
                      <span>•</span>
                      <span>
                        S{media.season_number || 1} E{media.episode_number || 1}
                      </span>
                    </>
                  )}
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex items-center gap-3">
                <Button
                  size="lg"
                  className="bg-plex-orange hover:bg-plex-orange/90 text-black font-semibold"
                  onClick={() => router.push(`/watch/${media.id}`)}
                >
                  <Play className="h-5 w-5 mr-2 fill-black" />
                  Riproduci
                </Button>
                <WatchlistButton mediaId={media.id} />
                <Button variant="outline" size="icon">
                  <Check className="h-5 w-5" />
                </Button>
                <Button variant="outline" size="icon">
                  <Share2 className="h-5 w-5" />
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={handleRefreshMetadata}
                  disabled={refreshing}
                  title="Aggiorna metadati TMDB"
                >
                  <RefreshCw
                    className={`h-5 w-5 ${refreshing ? "animate-spin" : ""}`}
                  />
                </Button>
              </div>

              {/* Overview */}
              {media.overview && (
                <p className="text-sm text-zinc-300 leading-relaxed max-w-2xl">
                  {media.overview}
                </p>
              )}

              {/* Technical info */}
              <div className="grid grid-cols-2 gap-4 text-sm pt-4 border-t border-zinc-800">
                {videoTrack && (
                  <InfoRow
                    label="Video"
                    value={videoTrack.codec_name.toUpperCase()}
                  />
                )}
                {audioTracks.length > 0 && (
                  <InfoRow
                    label="Audio"
                    value={`${audioTracks.length} tracce (${audioTracks.map((t) => t.language || "N/A").join(", ")})`}
                  />
                )}
                {subtitleTracks.length > 0 && (
                  <InfoRow
                    label="Sottotitoli"
                    value={`${subtitleTracks.length} tracce`}
                  />
                )}
                <InfoRow
                  label="Dimensione"
                  value={formatBytes(media.total_size)}
                />
              </div>
            </div>
          </motion.div>

          {/* Cast & Crew Section */}
          {cast.length > 0 && (
            <motion.section
              className="mt-6"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.4 }}
            >
              <HorizontalScroll title="Cast" className="gap-3 pb-2">
                {cast.slice(0, 20).map((person) => (
                  <div key={person.id} className="shrink-0 w-32 text-center">
                    {person.profile_path ? (
                      <Image
                        src={getTmdbImageUrl(person.profile_path, "w300")!}
                        alt={person.name}
                        width={120}
                        height={120}
                        className="w-[120px] h-[120px] rounded-full object-cover mx-auto"
                      />
                    ) : (
                      <div className="w-[120px] h-[120px] rounded-full bg-zinc-800 flex items-center justify-center text-zinc-500 text-3xl font-bold mx-auto">
                        {person.name
                          .split(" ")
                          .map((n) => n[0])
                          .join("")
                          .slice(0, 2)}
                      </div>
                    )}
                    <p className="text-xs text-white mt-1.5 truncate">
                      {person.name}
                    </p>
                    <p className="text-[10px] text-zinc-500 truncate">
                      {person.character || person.job}
                    </p>
                  </div>
                ))}
              </HorizontalScroll>
            </motion.section>
          )}

          {/* Episodes Section */}
          {episodes.length > 0 && (
            <section className="mt-8">
              <h2 className="text-xl font-semibold text-white mb-4">
                {episodes.length} episodi
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {episodes.map((ep) => (
                  <div
                    key={ep.episode_number}
                    className="bg-zinc-900 rounded-lg overflow-hidden hover:bg-zinc-800 transition-colors cursor-pointer group"
                  >
                    {/* Episode Thumbnail */}
                    <div className="relative aspect-video bg-zinc-800">
                      {ep.still_path ? (
                        <Image
                          src={getTmdbImageUrl(ep.still_path, "w500")!}
                          alt={ep.name}
                          fill
                          className="object-cover"
                        />
                      ) : (
                        <div className="absolute inset-0 flex items-center justify-center text-zinc-600">
                          Ep. {ep.episode_number}
                        </div>
                      )}
                      {/* Play overlay */}
                      <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                        <Play className="h-12 w-12 text-white fill-white" />
                      </div>
                    </div>
                    {/* Episode Info */}
                    <div className="p-3">
                      <p className="text-sm font-medium text-white truncate">
                        {ep.episode_number}. {ep.name}
                      </p>
                      {ep.runtime && (
                        <p className="text-xs text-zinc-400">
                          {ep.runtime} min
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </PageTransition>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-muted-foreground">{label}:</span>{" "}
      <span className="text-white">{value}</span>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="flex gap-8 animate-pulse">
      <div className="w-[200px] h-[300px] bg-zinc-800 rounded-md" />
      <div className="flex-1 space-y-4">
        <div className="h-8 w-64 bg-zinc-800 rounded" />
        <div className="h-4 w-32 bg-zinc-800 rounded" />
        <div className="flex gap-3">
          <div className="h-10 w-32 bg-zinc-800 rounded" />
          <div className="h-10 w-10 bg-zinc-800 rounded" />
          <div className="h-10 w-10 bg-zinc-800 rounded" />
        </div>
        <div className="space-y-2">
          <div className="h-4 w-full bg-zinc-800 rounded" />
          <div className="h-4 w-3/4 bg-zinc-800 rounded" />
        </div>
      </div>
    </div>
  );
}
