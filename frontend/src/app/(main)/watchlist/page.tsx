"use client";

import { useEffect, useState } from "react";
import { Heart } from "lucide-react";
import { useTranslations } from "next-intl";
import { PosterCard } from "@/components/ds";
import { getWatchlist, type WatchlistItem } from "@/lib/api";
import { getTmdbImageUrl } from "@/lib/format";

export default function WatchlistPage() {
  const t = useTranslations();
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
    <div className="px-4 md:px-12 py-6 md:py-8">
      <div className="flex items-center gap-3 mb-6">
        <Heart className="w-8 h-8 text-red-500" />
        <h1 className="text-[28px] font-bold text-[#fafafa]">{t("watchlist.title")}</h1>
        <span className="text-[#a1a1aa] text-lg">
          ({items.length} {items.length === 1 ? t("watchlist.itemOne") : t("watchlist.itemMany")})
        </span>
      </div>

      {loading ? (
        <div className="flex overflow-x-auto md:overflow-visible md:grid md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-7 2xl:grid-cols-9 gap-3 md:gap-4 scrollbar-hide pb-3 md:pb-0">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="animate-pulse shrink-0 w-[130px] md:w-auto">
              <div className="aspect-[2/3] bg-[#27272a] rounded-lg" />
              <div className="h-4 w-3/4 bg-[#27272a] rounded mt-2" />
            </div>
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20">
          <Heart className="w-16 h-16 mb-4 text-[#52525b]" />
          <p className="text-xl text-[#a1a1aa]">{t("watchlist.empty")}</p>
          <p className="text-sm mt-2 text-[#71717a]">
            {t("watchlist.emptyHint")}
          </p>
        </div>
      ) : (
        <div className="flex overflow-x-auto md:overflow-visible md:grid md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-7 2xl:grid-cols-9 gap-3 md:gap-4 scrollbar-hide pb-3 md:pb-0">
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
                subtitle={item.item_type === "series" ? t("home.series") : undefined}
                className="shrink-0 w-[130px] md:w-full"
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
