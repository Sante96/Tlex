"use client";

import { useEffect, useState } from "react";
import { RefreshCw, Play } from "lucide-react";
import Link from "next/link";
import Image from "next/image";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { LibraryGrid } from "@/components/library";
import {
  getMediaList,
  getContinueWatching,
  triggerScan,
  getSeriesList,
  type MediaItem,
  type ContinueWatchingItem,
  type SeriesItem,
} from "@/lib/api";
import { formatTime, cleanEpisodeTitle, getTmdbImageUrl } from "@/lib/format";
import {
  PageTransition,
  StaggerContainer,
  StaggerItem,
} from "@/components/motion";

export default function HomePage() {
  const [media, setMedia] = useState<MediaItem[]>([]);
  const [series, setSeries] = useState<SeriesItem[]>([]);
  const [continueWatching, setContinueWatching] = useState<
    ContinueWatchingItem[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    loadMedia();
    loadContinueWatching();
  }, []);

  const loadMedia = async () => {
    try {
      setLoading(true);
      const [mediaData, seriesData] = await Promise.all([
        getMediaList({ limit: 50 }),
        getSeriesList({ page_size: 50 }),
      ]);
      // Only keep movies, not episodes (episodes are shown via series)
      setMedia(mediaData.items.filter((m) => m.media_type === "MOVIE"));
      setSeries(seriesData.items);
    } catch (error) {
      console.error("Failed to load media:", error);
    } finally {
      setLoading(false);
    }
  };

  const loadContinueWatching = async () => {
    const items = await getContinueWatching(10);
    setContinueWatching(items);
  };

  const handleScan = async () => {
    try {
      setScanning(true);
      await triggerScan(100);
      await loadMedia();
    } catch (error) {
      console.error("Scan failed:", error);
    } finally {
      setScanning(false);
    }
  };

  if (loading) {
    return <LibraryGrid items={[]} loading={true} />;
  }

  if (media.length === 0 && series.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <h1 className="text-2xl font-bold text-white mb-4">
          Benvenuto in TLEX
        </h1>
        <p className="text-muted-foreground mb-6">
          La tua libreria è vuota. Scansiona i tuoi canali Telegram per
          iniziare.
        </p>
        <Button onClick={handleScan} disabled={scanning} size="lg">
          <RefreshCw
            className={`mr-2 h-5 w-5 ${scanning ? "animate-spin" : ""}`}
          />
          {scanning ? "Scansione..." : "Scansiona Canali"}
        </Button>
      </div>
    );
  }

  return (
    <PageTransition>
      <div className="space-y-8">
        {/* Header */}
        <motion.div
          className="flex items-center justify-between"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          <h1 className="text-2xl font-bold text-white">Home</h1>
          <Button
            variant="outline"
            size="sm"
            onClick={handleScan}
            disabled={scanning}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${scanning ? "animate-spin" : ""}`}
            />
            {scanning ? "Scansione..." : "Aggiorna"}
          </Button>
        </motion.div>

        {/* Continue Watching */}
        {continueWatching.length > 0 && (
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.4 }}
          >
            <h2 className="text-lg font-semibold text-white mb-4">
              Continua a guardare
            </h2>
            <StaggerContainer className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-7 gap-4">
              {continueWatching.map((item) => (
                <StaggerItem key={item.id}>
                  <ContinueWatchingCard item={item} />
                </StaggerItem>
              ))}
            </StaggerContainer>
          </motion.section>
        )}

        {/* Recent Films */}
        {media.length > 0 && (
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.4 }}
          >
            <h2 className="text-lg font-semibold text-white mb-4">Film</h2>
            <LibraryGrid items={media.slice(0, 14)} />
          </motion.section>
        )}

        {/* Series */}
        {series.length > 0 && (
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.4 }}
          >
            <h2 className="text-lg font-semibold text-white mb-4">Serie TV</h2>
            <StaggerContainer
              staggerDelay={0.05}
              className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-7 gap-4"
            >
              {series.slice(0, 14).map((s) => (
                <StaggerItem key={s.id}>
                  <SeriesCard series={s} />
                </StaggerItem>
              ))}
            </StaggerContainer>
          </motion.section>
        )}
      </div>
    </PageTransition>
  );
}

function SeriesCard({ series }: { series: SeriesItem }) {
  const posterUrl = getTmdbImageUrl(series.poster_path, "w300");

  return (
    <Link href={`/series/${series.id}`} className="group block">
      <div className="relative aspect-[2/3] bg-zinc-800 rounded-lg overflow-hidden">
        {posterUrl ? (
          <Image
            src={posterUrl}
            alt={series.title}
            fill
            className="object-cover transition-transform group-hover:scale-105"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-zinc-600">
            {series.title}
          </div>
        )}
      </div>
      <h3 className="mt-2 text-sm font-medium text-white truncate">
        {series.title}
      </h3>
      <p className="text-xs text-zinc-400">{series.seasons_count} stagioni</p>
    </Link>
  );
}

function ContinueWatchingCard({ item }: { item: ContinueWatchingItem }) {
  // Always use vertical poster for Plex-style look
  const imageUrl = item.series_id
    ? getTmdbImageUrl(item.series_poster_path ?? null, "w300") ||
    getTmdbImageUrl(item.poster_path, "w300")
    : getTmdbImageUrl(item.poster_path, "w300");

  // Line 1: Series title for episodes, movie title for movies
  const title = item.series_title || item.title;

  // Line 2: Episode title for series, year for movies
  const subtitle = item.series_id
    ? cleanEpisodeTitle(item.title) // Episode title
    : item.title; // For movies we could show year but we don't have it, show nothing

  // Line 3: "S3 · E11" format for episodes, nothing for movies
  const episodeIndicator =
    item.season_number && item.episode_number
      ? `S${item.season_number} · E${item.episode_number}`
      : null;

  return (
    <Link href={`/watch/${item.id}`} className="group block">
      <div className="relative aspect-[2/3] bg-zinc-800 rounded-lg overflow-hidden">
        {imageUrl ? (
          <Image
            src={imageUrl}
            alt={title}
            fill
            className="object-cover transition-transform group-hover:scale-105"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-zinc-600">
            No Image
          </div>
        )}

        {/* Play overlay */}
        <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
          <Play className="h-10 w-10 text-white fill-white" />
        </div>

        {/* Progress bar */}
        <div className="absolute bottom-0 left-0 right-0 h-1 bg-zinc-700">
          <div
            className="h-full bg-plex-orange"
            style={{ width: `${item.progress_percent}%` }}
          />
        </div>
      </div>

      {/* Plex-style 3-line text */}
      <div className="mt-2 space-y-0.5">
        <h3 className="text-sm font-medium text-white truncate">{title}</h3>
        {subtitle && subtitle !== title && (
          <p className="text-xs text-zinc-400 truncate">{subtitle}</p>
        )}
        {episodeIndicator && (
          <p className="text-xs text-zinc-500">{episodeIndicator}</p>
        )}
      </div>
    </Link>
  );
}
