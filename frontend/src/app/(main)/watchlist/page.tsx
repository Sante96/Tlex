"use client";

import { useEffect, useState } from "react";
import { Heart } from "lucide-react";
import { PosterCard } from "@/components/ds";
import { getWatchlist, type WatchlistItem } from "@/lib/api";
import { getTmdbImageUrl } from "@/lib/format";

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadWatchlist();
  }, []);

  const loadWatchlist = async () => {
    try {
      setLoading(true);
      const data = await getWatchlist();
      setItems(data.items);
    } catch {
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: "32px 48px" }}>
      <div className="flex items-center gap-3 mb-6">
        <Heart className="w-8 h-8 text-red-500" />
        <h1 className="text-[28px] font-bold text-[#fafafa]">La Mia Lista</h1>
        <span className="text-[#a1a1aa] text-lg">
          ({items.length} {items.length === 1 ? "titolo" : "titoli"})
        </span>
      </div>

      {loading ? (
        <div className="flex flex-wrap gap-5">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="w-[180px] animate-pulse">
              <div className="h-[270px] bg-[#27272a] rounded-lg" />
              <div className="h-4 w-3/4 bg-[#27272a] rounded mt-2" />
            </div>
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20">
          <Heart className="w-16 h-16 mb-4 text-[#52525b]" />
          <p className="text-xl text-[#a1a1aa]">La tua lista è vuota</p>
          <p className="text-sm mt-2 text-[#71717a]">
            Aggiungi film e serie ai preferiti per trovarli qui
          </p>
        </div>
      ) : (
        <div className="flex flex-wrap gap-5">
          {items.map((item) => {
            const href =
              item.item_type === "series"
                ? `/series/${item.series_id}`
                : `/media/${item.media_item_id}`;
            const key = item.series_id
              ? `series-${item.series_id}`
              : `media-${item.media_item_id}`;
            return (
              <PosterCard
                key={key}
                href={href}
                imageUrl={getTmdbImageUrl(item.poster_path, "w300")}
                title={item.title}
                subtitle={item.item_type === "series" ? "Serie TV" : undefined}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
