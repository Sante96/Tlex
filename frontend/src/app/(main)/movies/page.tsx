"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { PosterCard, DSButton } from "@/components/ds";
import { getMediaList, triggerScan, type MediaItem } from "@/lib/api";
import { getTmdbImageUrl } from "@/lib/format";
import { PosterCardSkeleton } from "@/components/ui/skeleton";

export default function MoviesPage() {
  const t = useTranslations();
  const [movies, setMovies] = useState<MediaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadMovies();
  }, []);

  const loadMovies = async () => {
    try {
      setLoading(true);
      const data = await getMediaList({ media_type: "MOVIE", limit: 100 });
      setMovies(data.items);
    } catch {
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    try {
      setRefreshing(true);
      await triggerScan(100);
      await loadMovies();
    } catch {
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div className="px-4 md:px-12 py-6 md:py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[#fafafa]">
            {t("nav.movies")}
          </h1>
          <p className="text-sm text-[#a1a1aa]">
            {movies.length} {t("nav.movies").toLowerCase()}
          </p>
        </div>
        <DSButton
          variant="secondary"
          onClick={handleRefresh}
          disabled={refreshing}
          className="!h-9"
          icon={
            <RefreshCw
              className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
            />
          }
        >
          {t("common.refresh")}
        </DSButton>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="flex overflow-x-auto md:overflow-visible md:grid md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-7 2xl:grid-cols-9 gap-3 md:gap-4 scrollbar-hide pb-3 md:pb-0">
          {Array.from({ length: 12 }).map((_, i) => (
            <PosterCardSkeleton key={i} className="w-[130px] md:w-auto" />
          ))}
        </div>
      ) : movies.length === 0 ? (
        <div className="text-center py-12 text-[#a1a1aa]">
          {t("media.moviesEmpty")}
        </div>
      ) : (
        <div className="flex overflow-x-auto md:overflow-visible md:grid md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-7 2xl:grid-cols-9 gap-3 md:gap-4 scrollbar-hide pb-3 md:pb-0">
          {movies.map((m) => (
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
        </div>
      )}
    </div>
  );
}
