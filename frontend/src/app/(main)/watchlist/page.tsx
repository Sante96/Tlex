"use client";

import { useEffect, useState, startTransition } from "react";
import { Heart } from "lucide-react";
import { useTranslations } from "next-intl";
import { PosterCard } from "@/components/ds";
import { getWatchlist, type WatchlistItem } from "@/lib/api";
import { POSTER_GRID, TV_POSTER_GRID } from "@/components/layout/library-page";
import { getTmdbImageUrl } from "@/lib/format";
import { PosterCardSkeleton } from "@/components/ui/skeleton";
import { useIsTV } from "@/hooks/use-platform";
import { useDelayed } from "@/hooks/use-delayed";

export default function WatchlistPage() {
  const t = useTranslations();
  const isTV = useIsTV();
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const showSkeleton = useDelayed(loading);

  const gridClass = isTV ? TV_POSTER_GRID : POSTER_GRID;

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
      // In a transition: the page fades in (the (main) layout's <ViewTransition>)
      startTransition(() => setLoading(false));
    }
  };

  return (
    <div className={isTV ? "px-8 py-8" : "px-4 md:px-12 py-6 md:py-8"}>
      <div className="flex items-center gap-3 mb-6">
        <Heart className="w-8 h-8 text-red-500" />
        <h1 className="text-[28px] font-bold text-[#fafafa]">
          {t("watchlist.title")}
        </h1>
        {/* Not "(0 titles)" while it loads */}
        {!loading && (
          <span className="text-[#a1a1aa] text-lg">
            ({items.length}{" "}
            {items.length === 1
              ? t("watchlist.itemOne")
              : t("watchlist.itemMany")}
            )
          </span>
        )}
      </div>

      {loading ? (
        showSkeleton && (
          <div className={gridClass}>
            {Array.from({ length: 7 }).map((_, i) => (
              <PosterCardSkeleton key={i} />
            ))}
          </div>
        )
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20">
          <Heart className="w-16 h-16 mb-4 text-[#52525b]" />
          <p className="text-xl text-[#a1a1aa]">{t("watchlist.empty")}</p>
          <p className="text-sm mt-2 text-[#71717a]">
            {t("watchlist.emptyHint")}
          </p>
        </div>
      ) : (
        <div className={gridClass}>
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
                subtitle={
                  item.item_type === "series" ? t("home.series") : undefined
                }
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
