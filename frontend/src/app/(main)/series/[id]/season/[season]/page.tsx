"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Image from "next/image";
import { Play, ArrowLeft, Clock, CheckCircle2 } from "lucide-react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
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
import { PageTransition } from "@/components/motion";
import { HorizontalScroll } from "@/components/horizontal-scroll";

// Helper to get season display name
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
        const [data, castData] = await Promise.all([
          getSeriesDetails(seriesId),
          getSeriesCast(seriesId),
        ]);
        setSeries(data);
        setCast(castData);
        const seasonData = data.seasons.find(
          (s) => s.season_number === seasonNumber,
        );
        setSeason(seasonData || null);
      } catch (error) {
        console.error("Failed to load season:", error);
      } finally {
        setLoading(false);
      }
    };

    if (seriesId && seasonNumber !== undefined && !isNaN(seasonNumber)) {
      loadData();
    }
  }, [seriesId, seasonNumber]);

  if (loading) {
    return <SeasonSkeleton />;
  }

  if (!series || !season) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-muted-foreground">Stagione non trovata</p>
        <Button variant="link" onClick={() => router.back()}>
          Torna indietro
        </Button>
      </div>
    );
  }

  const posterUrl = getTmdbImageUrl(
    season.poster_path || series.poster_path,
    "w500",
  );
  const backdropUrl = getTmdbImageUrl(series.backdrop_path, "original");

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

        <div className="relative z-10 space-y-8 p-6">
          {/* Back button */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push(`/series/${seriesId}`)}
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            {series.title}
          </Button>

          {/* Header */}
          <motion.div
            className="flex gap-8"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.4 }}
          >
            {/* Poster */}
            <motion.div
              className="shrink-0 w-[180px]"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.2, duration: 0.4 }}
            >
              {posterUrl ? (
                <Image
                  src={posterUrl}
                  alt={`${series.title} - ${seasonName}`}
                  width={180}
                  height={270}
                  className="rounded-md"
                />
              ) : (
                <div className="w-[180px] h-[270px] bg-zinc-800 rounded-md flex items-center justify-center text-zinc-600">
                  S{seasonNumber}
                </div>
              )}
            </motion.div>

            {/* Info */}
            <div className="flex-1 space-y-4">
              <div>
                <h1 className="text-3xl font-bold text-white">
                  {series.title}
                </h1>
                <p className="text-xl text-plex-orange mt-1">{seasonName}</p>
                <p className="text-sm text-muted-foreground mt-1">
                  {season.episodes_count} episodi
                </p>
              </div>

              {/* Play button */}
              <Button
                size="lg"
                className="bg-plex-orange hover:bg-plex-orange/90 text-black font-semibold"
                onClick={() => {
                  if (season.episodes[0]) {
                    router.push(`/watch/${season.episodes[0].id}`);
                  }
                }}
              >
                <Play className="h-5 w-5 mr-2 fill-black" />
                Riproduci
              </Button>
            </div>
          </motion.div>

          {/* Episodes List */}
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.4 }}
          >
            <h2 className="text-xl font-semibold text-white mb-4">
              {season.episodes_count} episodi
            </h2>
            <div className="space-y-3">
              {season.episodes.map((ep, index) => (
                <EpisodeRow key={ep.id} episode={ep} index={index} />
              ))}
            </div>
          </motion.section>

          {/* Cast Section */}
          {cast.length > 0 && (
            <motion.section
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4, duration: 0.4 }}
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
        </div>
      </div>
    </PageTransition>
  );
}

function EpisodeRow({
  episode,
  index,
}: {
  episode: SeasonInfo["episodes"][0];
  index: number;
}) {
  const router = useRouter();
  const thumbnailUrl = getTmdbImageUrl(episode.still_path, "w500");
  const isWatched = episode.watch_progress?.is_completed ?? false;
  const progressPercent = episode.watch_progress?.progress_percent ?? 0;
  const hasProgress = progressPercent > 0 && !isWatched;

  return (
    <motion.div
      className="group relative overflow-hidden rounded-xl bg-zinc-900/80 hover:bg-zinc-800/90 border border-zinc-800/50 hover:border-zinc-700/50 cursor-pointer transition-colors"
      onClick={() => router.push(`/watch/${episode.id}`)}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.3 }}
      whileHover={{ scale: 1.005 }}
    >
      <div className="flex gap-4 p-3">
        {/* Episode number badge */}
        <div className="shrink-0 w-12 flex items-center justify-center">
          <span className="text-2xl font-bold text-zinc-600 group-hover:text-zinc-500 transition-colors">
            {episode.episode_number}
          </span>
        </div>

        {/* Episode thumbnail */}
        <div className="shrink-0 w-44 aspect-video bg-zinc-800 rounded-lg overflow-hidden relative shadow-lg">
          {thumbnailUrl ? (
            <Image
              src={thumbnailUrl}
              alt={episode.title}
              fill
              className="object-cover transition-transform duration-300 group-hover:scale-105"
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-zinc-700 to-zinc-800">
              <span className="text-3xl font-bold text-zinc-600">
                E{episode.episode_number}
              </span>
            </div>
          )}

          {/* Play overlay */}
          <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-all duration-200 flex items-center justify-center">
            <div className="w-12 h-12 rounded-full bg-plex-orange flex items-center justify-center transform scale-75 group-hover:scale-100 transition-transform">
              <Play className="h-6 w-6 text-black fill-black ml-0.5" />
            </div>
          </div>

          {/* Progress bar */}
          {hasProgress && (
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-zinc-900/80">
              <div
                className="h-full bg-plex-orange"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          )}

          {/* Watched badge */}
          {isWatched && (
            <div className="absolute top-2 right-2">
              <CheckCircle2 className="h-5 w-5 text-green-500 drop-shadow-lg" />
            </div>
          )}
        </div>

        {/* Episode info */}
        <div className="flex-1 min-w-0 py-1">
          <div className="flex items-start justify-between gap-2">
            <h3 className="text-white font-semibold group-hover:text-plex-orange transition-colors line-clamp-1">
              {cleanEpisodeTitle(episode.title)}
            </h3>
            {episode.duration_seconds && (
              <div className="shrink-0 flex items-center gap-1 text-xs text-zinc-500">
                <Clock className="h-3 w-3" />
                {formatDurationShort(episode.duration_seconds)}
              </div>
            )}
          </div>

          {episode.overview && (
            <p className="text-sm text-zinc-400 line-clamp-2 mt-1.5 leading-relaxed">
              {episode.overview}
            </p>
          )}

          {/* Status indicators */}
          <div className="flex items-center gap-3 mt-2">
            {isWatched && (
              <span className="text-xs text-green-500 font-medium">Visto</span>
            )}
            {hasProgress && (
              <span className="text-xs text-plex-orange font-medium">
                {Math.round(progressPercent)}% completato
              </span>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function SeasonSkeleton() {
  return (
    <div className="space-y-8 animate-pulse">
      <div className="flex gap-8">
        <div className="w-[180px] h-[270px] bg-zinc-800 rounded-md" />
        <div className="flex-1 space-y-4">
          <div className="h-8 w-48 bg-zinc-800 rounded" />
          <div className="h-6 w-32 bg-zinc-800 rounded" />
          <div className="h-10 w-32 bg-zinc-800 rounded" />
        </div>
      </div>
      <div>
        <div className="h-6 w-24 bg-zinc-800 rounded mb-4" />
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-20 bg-zinc-800 rounded-lg" />
          ))}
        </div>
      </div>
    </div>
  );
}
