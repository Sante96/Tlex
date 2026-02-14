"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { PosterCard } from "@/components/ds";
import { getSeriesList, triggerScan, type SeriesItem } from "@/lib/api";
import { getTmdbImageUrl } from "@/lib/format";

export default function SeriesPage() {
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
    <div style={{ padding: "32px 48px" }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[#fafafa]">Serie TV</h1>
          <p className="text-sm text-[#a1a1aa]">{series.length} serie</p>
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
          Aggiorna
        </button>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="flex flex-wrap gap-5">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="w-[180px] animate-pulse">
              <div className="h-[270px] bg-[#27272a] rounded-lg" />
              <div className="h-4 w-3/4 bg-[#27272a] rounded mt-2" />
              <div className="h-3 w-1/2 bg-[#27272a] rounded mt-1" />
            </div>
          ))}
        </div>
      ) : series.length === 0 ? (
        <div className="text-center py-12 text-[#a1a1aa]">
          Nessuna serie trovata. Avvia una scansione per importare contenuti.
        </div>
      ) : (
        <div className="flex flex-wrap gap-5">
          {series.map((s) => (
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
        </div>
      )}
    </div>
  );
}
