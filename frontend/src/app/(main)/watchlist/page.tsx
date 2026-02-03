"use client";

import { useEffect, useState } from "react";
import { Heart } from "lucide-react";
import { LibraryGrid } from "@/components/library";
import { getWatchlist, type MediaItem } from "@/lib/api";

export default function WatchlistPage() {
  const [items, setItems] = useState<MediaItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadWatchlist();
  }, []);

  const loadWatchlist = async () => {
    try {
      setLoading(true);
      const data = await getWatchlist();
      const mediaItems: MediaItem[] = data.items.map((item) => ({
        id: item.media_item_id,
        title: item.title,
        poster_path: item.poster_path,
        media_type: item.media_type as "MOVIE" | "EPISODE",
        duration_seconds: item.duration_seconds,
        overview: null,
        backdrop_path: null,
        release_date: null,
        tmdb_id: null,
        season_number: null,
        episode_number: null,
        total_size: null,
        parts_count: 0,
      }));
      setItems(mediaItems);
    } catch (error) {
      console.error("Failed to load watchlist:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Heart className="w-8 h-8 text-red-500" />
          <h1 className="text-3xl font-bold">La Mia Lista</h1>
          <span className="text-muted-foreground text-lg">
            ({items.length} {items.length === 1 ? "titolo" : "titoli"})
          </span>
        </div>
      </div>

      {!loading && items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
          <Heart className="w-16 h-16 mb-4 opacity-50" />
          <p className="text-xl">La tua lista è vuota</p>
          <p className="text-sm mt-2">
            Aggiungi film e serie ai preferiti per trovarli qui
          </p>
        </div>
      ) : (
        <LibraryGrid items={items} loading={loading} />
      )}
    </div>
  );
}
