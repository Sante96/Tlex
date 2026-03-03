"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { PosterCard } from "@/components/ds";
import { getSeriesList, triggerScan, type SeriesItem } from "@/lib/api";
import { getTmdbImageUrl } from "@/lib/format";

export default function SeriesPage() {
  const t = useTranslations();
  const [series, setSeries] = useState<SeriesItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

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
    <div className="px-4 md:px-12 py-6 md:py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[#fafafa]">{t("nav.series")}</h1>
          <p className="text-sm text-[#a1a1aa]">{series.length} {t("nav.series").toLowerCase()}</p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="inline-flex items-center gap-2 h-9 px-4 rounded-lg text-sm text-[#fafafa] transition-colors hover:bg-[#3f3f46] disabled:opacity-50"
          style={{ border: "1px solid #27272a" }}
        >
          <RefreshCw
            className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
          />
          {t("common.refresh")}
        </button>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="flex overflow-x-auto md:overflow-visible md:grid md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-7 2xl:grid-cols-9 gap-3 md:gap-4 scrollbar-hide pb-3 md:pb-0">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="animate-pulse shrink-0 w-[130px] md:w-auto">
              <div className="aspect-[2/3] bg-[#27272a] rounded-lg" />
              <div className="h-4 w-3/4 bg-[#27272a] rounded mt-2" />
              <div className="h-3 w-1/2 bg-[#27272a] rounded mt-1" />
            </div>
          ))}
        </div>
      ) : series.length === 0 ? (
        <div className="text-center py-12 text-[#a1a1aa]">
          {t("media.seriesEmpty")}
        </div>
      ) : (
        <div className="flex overflow-x-auto md:overflow-visible md:grid md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-7 2xl:grid-cols-9 gap-3 md:gap-4 scrollbar-hide pb-3 md:pb-0">
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
              className="shrink-0 w-[130px] md:w-full"
            />
          ))}
        </div>
      )}
    </div>
  );
}
