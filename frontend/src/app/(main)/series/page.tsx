"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getSeriesList, triggerScan, type SeriesItem } from "@/lib/api";

const TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p";

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
    } catch (error) {
      console.error("Failed to load series:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    try {
      setRefreshing(true);
      await triggerScan(100);
      await loadSeries();
    } catch (error) {
      console.error("Refresh failed:", error);
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Serie TV</h1>
          <p className="text-sm text-muted-foreground">{series.length} serie</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefresh}
          disabled={refreshing}
        >
          <RefreshCw
            className={`h-4 w-4 mr-2 ${refreshing ? "animate-spin" : ""}`}
          />
          Aggiorna
        </Button>
      </div>

      {/* Series Grid */}
      {loading ? (
        <SeriesGridSkeleton />
      ) : series.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          Nessuna serie trovata. Avvia una scansione per importare contenuti.
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {series.map((s) => (
            <SeriesCard key={s.id} series={s} />
          ))}
        </div>
      )}
    </div>
  );
}

function SeriesCard({ series }: { series: SeriesItem }) {
  const router = useRouter();
  const posterUrl = series.poster_path
    ? `${TMDB_IMAGE_BASE}/w342${series.poster_path}`
    : null;

  const year = series.first_air_date
    ? new Date(series.first_air_date).getFullYear()
    : null;

  return (
    <div
      className="group cursor-pointer"
      onClick={() => router.push(`/series/${series.id}`)}
    >
      <div className="relative aspect-[2/3] bg-zinc-800 rounded-md overflow-hidden">
        {posterUrl ? (
          <Image
            src={posterUrl}
            alt={series.title}
            fill
            className="object-cover group-hover:scale-105 transition-transform duration-300"
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-zinc-600 text-sm p-2 text-center">
            {series.title}
          </div>
        )}
      </div>
      <p className="text-sm text-white mt-2 font-medium truncate">
        {series.title}
      </p>
      <p className="text-xs text-zinc-400">
        {year && `${year} • `}
        {series.seasons_count} stagioni
      </p>
    </div>
  );
}

function SeriesGridSkeleton() {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
      {Array.from({ length: 12 }).map((_, i) => (
        <div key={i} className="animate-pulse">
          <div className="aspect-[2/3] bg-zinc-800 rounded-md" />
          <div className="h-4 w-3/4 bg-zinc-800 rounded mt-2" />
          <div className="h-3 w-1/2 bg-zinc-800 rounded mt-1" />
        </div>
      ))}
    </div>
  );
}
