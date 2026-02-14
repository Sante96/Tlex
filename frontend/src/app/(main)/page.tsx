"use client";

import { useEffect, useState } from "react";
import { RefreshCw, Play } from "lucide-react";
import { DSButton, PosterCard, SectionHeader } from "@/components/ds";
import { StaggerGrid } from "@/components/motion/stagger-grid";
import {
  getMediaList,
  getContinueWatching,
  triggerScan,
  getSeriesList,
  type MediaItem,
  type ContinueWatchingItem,
  type SeriesItem,
} from "@/lib/api";
import { cleanEpisodeTitle, getTmdbImageUrl } from "@/lib/format";

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
      setMedia(mediaData.items.filter((m) => m.media_type === "MOVIE"));
      setSeries(seriesData.items);
    } catch {
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
    } catch {
    } finally {
      setScanning(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8">
        <div className="flex flex-wrap gap-5">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="w-[180px] animate-pulse">
              <div className="h-[270px] bg-[#27272a] rounded-lg" />
              <div className="h-4 w-3/4 bg-[#27272a] rounded mt-2" />
              <div className="h-3 w-1/2 bg-[#27272a] rounded mt-1" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (media.length === 0 && series.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <h1 className="text-2xl font-bold text-[#fafafa] mb-4">
          Benvenuto in TLEX
        </h1>
        <p className="text-[#a1a1aa] mb-6">
          La tua libreria è vuota. Scansiona i tuoi canali Telegram per
          iniziare.
        </p>
        <DSButton
          onClick={handleScan}
          disabled={scanning}
          icon={
            <RefreshCw
              className={`h-5 w-5 ${scanning ? "animate-spin" : ""}`}
            />
          }
        >
          {scanning ? "Scansione..." : "Scansiona Canali"}
        </DSButton>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 p-8">
      {/* Continue Watching */}
      {continueWatching.length > 0 && (
        <section>
          <SectionHeader title="Continua a guardare" />
          <StaggerGrid className="flex flex-wrap gap-5">
            {continueWatching.map((item) => (
              <ContinueWatchingCard key={item.id} item={item} />
            ))}
          </StaggerGrid>
        </section>
      )}

      {/* Film */}
      {media.length > 0 && (
        <section>
          <SectionHeader title="Film" href="/movies" />
          <StaggerGrid className="flex flex-wrap gap-5">
            {media.slice(0, 7).map((m) => (
              <PosterCard
                key={m.id}
                href={`/media/${m.id}`}
                imageUrl={getTmdbImageUrl(m.poster_path, "w300")}
                title={m.title}
                subtitle={
                  m.release_date
                    ? new Date(m.release_date).getFullYear().toString()
                    : ""
                }
              />
            ))}
          </StaggerGrid>
        </section>
      )}

      {/* Serie TV */}
      {series.length > 0 && (
        <section>
          <SectionHeader title="Serie TV" href="/series" />
          <StaggerGrid className="flex flex-wrap gap-5">
            {series.slice(0, 7).map((s) => (
              <PosterCard
                key={s.id}
                href={`/series/${s.id}`}
                imageUrl={getTmdbImageUrl(s.poster_path, "w300")}
                title={s.title}
                subtitle={
                  s.seasons_count === 1
                    ? "1 Stagione"
                    : `${s.seasons_count} Stagioni`
                }
              />
            ))}
          </StaggerGrid>
        </section>
      )}
    </div>
  );
}

function ContinueWatchingCard({ item }: { item: ContinueWatchingItem }) {
  const imageUrl = item.series_id
    ? getTmdbImageUrl(item.series_poster_path ?? null, "w300") ||
      getTmdbImageUrl(item.poster_path, "w300")
    : getTmdbImageUrl(item.poster_path, "w300");

  const title = item.series_title || item.title;
  const subtitle = item.series_id ? cleanEpisodeTitle(item.title) : undefined;
  const episodeIndicator =
    item.season_number && item.episode_number
      ? `S${item.season_number} · E${item.episode_number}`
      : undefined;

  const combinedSubtitle = [subtitle, episodeIndicator]
    .filter(Boolean)
    .join(" · ");

  return (
    <PosterCard
      href={`/watch/${item.id}`}
      imageUrl={imageUrl}
      title={title}
      subtitle={combinedSubtitle || undefined}
      progress={item.progress_percent}
    >
      {/* Play overlay */}
      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
        <Play className="h-10 w-10 text-white fill-white" />
      </div>
    </PosterCard>
  );
}
