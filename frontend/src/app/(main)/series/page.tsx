"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { PosterCard, DSButton } from "@/components/ds";
import { getSeriesList, triggerScan, type SeriesItem } from "@/lib/api";
import { getTmdbImageUrl } from "@/lib/format";
import { PosterCardSkeleton } from "@/components/ui/skeleton";
import { useIsTV } from "@/hooks/use-platform";

export default function SeriesPage() {
  const t = useTranslations();
  const isTV = useIsTV();
  const [series, setSeries] = useState<SeriesItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const gridClass = isTV
    ? "grid grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8 gap-4 md:gap-5"
    : "flex overflow-x-auto md:overflow-visible md:grid md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-7 2xl:grid-cols-9 gap-3 md:gap-4 scrollbar-hide pb-3 md:pb-0";
  const cardClass = isTV ? "" : "shrink-0 w-[130px] md:w-full";

  useEffect(() => {
    loadSeries();
  }, []);

  const loadSeries = async () => {
    try {
      setLoading(true);
      const data = await getSeriesList({ page_size: 100 });
      setSeries(data.items);
    } catch {
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    try {
      setRefreshing(true);
      await triggerScan(100);
      await loadSeries();
    } catch {
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div className={isTV ? "px-8 py-8" : "px-4 md:px-12 py-6 md:py-8"}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[#fafafa]">
            {t("nav.series")}
          </h1>
          <p className="text-sm text-[#a1a1aa]">
            {series.length} {t("nav.series").toLowerCase()}
          </p>
        </div>
        {!isTV && (
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
        )}
      </div>

      {/* Grid */}
      {loading ? (
        <div className={gridClass}>
          {Array.from({ length: 12 }).map((_, i) => (
            <PosterCardSkeleton key={i} className={cardClass || "w-[130px] md:w-auto"} />
          ))}
        </div>
      ) : series.length === 0 ? (
        <div className="text-center py-12 text-[#a1a1aa]">
          {t("media.seriesEmpty")}
        </div>
      ) : (
        <div className={gridClass}>
          {series.map((s) => (
            <PosterCard
              key={s.id}
              href={`/series/${s.id}`}
              imageUrl={getTmdbImageUrl(s.poster_path, "w300")}
              title={s.title}
              subtitle={
                s.seasons_count === 1
                  ? `1 ${t("media.season")}`
                  : `${s.seasons_count} ${t("media.seasons")}`
              }
              className={cardClass}
            />
          ))}
        </div>
      )}
    </div>
  );
}
