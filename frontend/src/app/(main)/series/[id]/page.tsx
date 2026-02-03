"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Image from "next/image";
import { Play, RefreshCw, ArrowLeft, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";
import {
  getSeriesDetails,
  refreshSeriesMetadata,
  getSeriesCast,
  type SeriesDetails,
  type SeasonInfo,
  type CastMember,
} from "@/lib/api";
import { getTmdbImageUrl } from "@/lib/format";
import { PageTransition } from "@/components/motion";
import { HorizontalScroll } from "@/components/horizontal-scroll";

export default function SeriesDetailPage() {
  const params = useParams();
  const router = useRouter();
  const seriesId = Number(params.id);

  const [series, setSeries] = useState<SeriesDetails | null>(null);
  const [cast, setCast] = useState<CastMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    const loadSeries = async () => {
      try {
        setLoading(true);
        const [data, castData] = await Promise.all([
          getSeriesDetails(seriesId),
          getSeriesCast(seriesId),
        ]);
        setSeries(data);
        setCast(castData);
      } catch (error) {
        console.error("Failed to load series:", error);
      } finally {
        setLoading(false);
      }
    };

    if (seriesId) {
      loadSeries();
    }
  }, [seriesId]);

  const handleRefreshMetadata = async () => {
    if (!series || refreshing) return;

    try {
      setRefreshing(true);
      const result = await refreshSeriesMetadata(series.id);
      const updated = await getSeriesDetails(series.id);
      setSeries(updated);
      alert(`Metadati aggiornati: ${result.title}`);
    } catch (error) {
      console.error("Failed to refresh metadata:", error);
      alert("Errore nel refresh dei metadati");
    } finally {
      setRefreshing(false);
    }
  };

  if (loading) {
    return <SeriesSkeleton />;
  }

  if (!series) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-muted-foreground">Serie non trovata</p>
        <Button variant="link" onClick={() => router.back()}>
          Torna indietro
        </Button>
      </div>
    );
  }

  const posterUrl = getTmdbImageUrl(series.poster_path, "w500");
  const backdropUrl = getTmdbImageUrl(series.backdrop_path, "original");

  const year = series.first_air_date
    ? new Date(series.first_air_date).getFullYear()
    : null;

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
          <Button variant="ghost" size="sm" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Indietro
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
              className="shrink-0 w-[150px]"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.2, duration: 0.4 }}
            >
              <div className="relative aspect-[2/3] bg-zinc-800 rounded-md overflow-hidden">
                {posterUrl ? (
                  <Image
                    src={posterUrl}
                    alt={series.title}
                    fill
                    className="object-cover"
                    sizes="150px"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-zinc-600 text-sm">
                    No Poster
                  </div>
                )}
              </div>
            </motion.div>

            {/* Info */}
            <div className="flex-1 space-y-4">
              <div>
                <h1 className="text-3xl font-bold text-white">
                  {series.title}
                </h1>
                {/* Genres */}
                {series.genres && series.genres.length > 0 && (
                  <p className="text-sm text-zinc-400 mt-1">
                    {series.genres.join(", ")}
                  </p>
                )}
                {/* Metadata row: content rating, TMDB score, year, seasons, episodes */}
                <div className="flex items-center gap-3 text-sm mt-2">
                  {series.content_rating && (
                    <span className="px-2 py-0.5 border border-zinc-500 text-zinc-300 rounded text-xs font-medium">
                      {series.content_rating}
                    </span>
                  )}
                  {series.vote_average && series.vote_average > 0 && (
                    <span className="flex items-center gap-1.5">
                      {/* TMDB Logo */}
                      <svg
                        className="h-3"
                        viewBox="0 0 185.04 133.4"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <defs>
                          <linearGradient
                            id="tmdb-grad"
                            x1="0%"
                            y1="0%"
                            x2="100%"
                            y2="0%"
                          >
                            <stop offset="0%" stopColor="#90cea1" />
                            <stop offset="100%" stopColor="#01b4e4" />
                          </linearGradient>
                        </defs>
                        <g fill="url(#tmdb-grad)">
                          <path d="M51.06 66.7h-8.53V29.18h8.53Zm-4.27-44.8a5.07 5.07 0 1 1 5.07-5.07 5.07 5.07 0 0 1-5.07 5.07ZM70.62 66.7h-8.53V29.18h8.53Zm40.74 0h-8.53V47.93c0-3.56-1.18-6.27-4.73-6.27a5.13 5.13 0 0 0-4.81 3.44 6.33 6.33 0 0 0-.31 2.24V66.7h-8.53V40.74c0-3.27-.11-5.91-.22-8.22h7.41l.39 3.58h.17a10.29 10.29 0 0 1 9.07-4.14c6 0 10.49 4.03 10.49 12.7ZM143.59 66.7h-8.53V47.93c0-3.56-1.18-6.27-4.73-6.27a5.13 5.13 0 0 0-4.81 3.44 6.33 6.33 0 0 0-.31 2.24V66.7h-8.53V29.18h8.53v15.52h.11a10.29 10.29 0 0 1 9.07-4.14c6 0 10.49 4.03 10.49 12.7Z" />
                        </g>
                      </svg>
                      <span className="text-[#01b4e4] font-semibold">
                        {Math.round(series.vote_average * 10)}%
                      </span>
                    </span>
                  )}
                  {year && (
                    <span className="text-muted-foreground">{year}</span>
                  )}
                  <span className="text-muted-foreground">•</span>
                  <span className="text-muted-foreground">
                    {series.seasons_count}{" "}
                    {series.seasons_count === 1 ? "stagione" : "stagioni"}
                  </span>
                  <span className="text-muted-foreground">•</span>
                  <span className="text-muted-foreground">
                    {series.episodes_count}{" "}
                    {series.episodes_count === 1 ? "episodio" : "episodi"}
                  </span>
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex items-center gap-3">
                <Button
                  size="lg"
                  className="bg-plex-orange hover:bg-plex-orange/90 text-black font-semibold"
                  onClick={() => {
                    // Play first episode of first season
                    const firstSeason = series.seasons[0];
                    if (firstSeason?.episodes[0]) {
                      router.push(`/watch/${firstSeason.episodes[0].id}`);
                    }
                  }}
                >
                  <Play className="h-5 w-5 mr-2 fill-black" />
                  Riproduci
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
              {series.overview && (
                <p className="text-sm text-zinc-300 leading-relaxed max-w-2xl">
                  {series.overview}
                </p>
              )}
            </div>
          </motion.div>

          {/* Seasons Grid */}
          <section>
            <h2 className="text-xl font-semibold text-white mb-4">Stagioni</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
              {series.seasons.map((season) => (
                <SeasonCard
                  key={season.season_number}
                  season={season}
                  seriesId={series.id}
                  seriesPoster={series.poster_path}
                />
              ))}
            </div>
          </section>

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

// Helper to get season display name
function getSeasonName(seasonNumber: number): string {
  return seasonNumber === 0 ? "Specials" : `Stagione ${seasonNumber}`;
}

function SeasonCard({
  season,
  seriesId,
  seriesPoster,
}: {
  season: SeasonInfo;
  seriesId: number;
  seriesPoster: string | null;
}) {
  const router = useRouter();
  const posterUrl = getTmdbImageUrl(season.poster_path || seriesPoster, "w300");
  const seasonName = getSeasonName(season.season_number);

  return (
    <div
      className="group cursor-pointer"
      onClick={() =>
        router.push(`/series/${seriesId}/season/${season.season_number}`)
      }
    >
      <div className="relative aspect-[2/3] bg-zinc-800 rounded-md overflow-hidden">
        {posterUrl ? (
          <Image
            src={posterUrl}
            alt={seasonName}
            fill
            className="object-cover group-hover:scale-105 transition-transform duration-300"
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-zinc-600 text-lg font-bold">
            {season.season_number === 0 ? "SP" : `S${season.season_number}`}
          </div>
        )}
        {/* Watched indicator placeholder */}
        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="bg-plex-orange rounded-full p-1">
            <Check className="h-4 w-4 text-black" />
          </div>
        </div>
      </div>
      <p className="text-sm text-white mt-2 font-medium">{seasonName}</p>
      <p className="text-xs text-zinc-400">{season.episodes_count} episodi</p>
    </div>
  );
}

function SeriesSkeleton() {
  return (
    <div className="space-y-8 animate-pulse">
      <div className="flex gap-8">
        <div className="w-[200px] h-[300px] bg-zinc-800 rounded-md" />
        <div className="flex-1 space-y-4">
          <div className="h-8 w-64 bg-zinc-800 rounded" />
          <div className="h-4 w-32 bg-zinc-800 rounded" />
          <div className="flex gap-3">
            <div className="h-10 w-32 bg-zinc-800 rounded" />
            <div className="h-10 w-10 bg-zinc-800 rounded" />
          </div>
          <div className="space-y-2">
            <div className="h-4 w-full bg-zinc-800 rounded" />
            <div className="h-4 w-3/4 bg-zinc-800 rounded" />
          </div>
        </div>
      </div>
      <div>
        <div className="h-6 w-24 bg-zinc-800 rounded mb-4" />
        <div className="grid grid-cols-6 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="aspect-[2/3] bg-zinc-800 rounded-md" />
          ))}
        </div>
      </div>
    </div>
  );
}
