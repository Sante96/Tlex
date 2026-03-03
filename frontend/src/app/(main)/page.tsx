"use client";

import { useEffect, useState } from "react";
import { RefreshCw, Play } from "lucide-react";
import { useTranslations } from "next-intl";
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
  const t = useTranslations();
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
      <div className="px-4 md:px-8 py-6 md:py-8">
        <div className="flex overflow-x-auto md:overflow-visible md:grid md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-7 2xl:grid-cols-9 gap-3 md:gap-4 scrollbar-hide pb-3 md:pb-0">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="animate-pulse shrink-0 w-[130px] md:w-auto">
              <div className="aspect-[2/3] bg-[#27272a] rounded-lg" />
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
          {t("home.welcome")}
        </h1>
        <p className="text-[#a1a1aa] mb-6">
          {t("home.emptyLibrary")}
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
          {scanning ? t("home.scanning") : t("home.scan")}
        </DSButton>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 px-4 md:px-8 py-6 md:py-8">
      {/* Continue Watching */}
      {continueWatching.length > 0 && (
        <section>
          <SectionHeader title={t("home.continueWatching")} />
          <StaggerGrid className="flex overflow-x-auto md:overflow-visible md:grid md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-7 2xl:grid-cols-9 gap-3 md:gap-4 scrollbar-hide pb-3 md:pb-0">
            {continueWatching.map((item) => (
              <ContinueWatchingCard key={item.id} item={item} />
            ))}
          </StaggerGrid>
        </section>
      )}

      {/* Film */}
      {media.length > 0 && (
        <section>
          <SectionHeader title={t("home.movies")} href="/movies" />
          <StaggerGrid className="flex overflow-x-auto md:overflow-visible md:grid md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-7 2xl:grid-cols-9 gap-3 md:gap-4 scrollbar-hide pb-3 md:pb-0">
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
                className="shrink-0 w-[130px] md:w-full"
              />
            ))}
          </StaggerGrid>
        </section>
      )}

      {/* Serie TV */}
      {series.length > 0 && (
        <section>
          <SectionHeader title={t("home.series")} href="/series" />
          <StaggerGrid className="flex overflow-x-auto md:overflow-visible md:grid md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-7 2xl:grid-cols-9 gap-3 md:gap-4 scrollbar-hide pb-3 md:pb-0">
            {series.slice(0, 7).map((s) => (
              <PosterCard
                key={s.id}
                href={`/series/${s.id}`}
                imageUrl={getTmdbImageUrl(s.poster_path, "w300")}
                title={s.title}
                subtitle={
                  s.seasons_count === 1
                    ? `1 ${t("home.season")}`
                    : `${s.seasons_count} ${t("home.seasons")}`
                }
                className="shrink-0 w-[130px] md:w-full"
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
      className="shrink-0 w-[130px] md:w-full"
    >
      {/* Play overlay */}
      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
        <Play className="h-10 w-10 text-white fill-white" />
      </div>
    </PosterCard>
  );
}
