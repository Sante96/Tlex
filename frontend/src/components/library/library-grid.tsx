"use client";

import { MediaPoster } from "./media-poster";
import type { MediaItem } from "@/lib/api";

interface LibraryGridProps {
  items: MediaItem[];
  loading?: boolean;
}

export function LibraryGrid({ items, loading }: LibraryGridProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7 gap-4">
        {Array.from({ length: 14 }).map((_, i) => (
          <div key={i} className="space-y-2">
            <div className="aspect-[2/3] bg-zinc-800 rounded-md animate-pulse" />
            <div className="h-4 bg-zinc-800 rounded animate-pulse" />
            <div className="h-3 w-1/2 bg-zinc-800 rounded animate-pulse" />
          </div>
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="text-muted-foreground">Nessun contenuto trovato</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7 gap-4">
      {items.map((item) => (
        <MediaPoster key={item.id} media={item} />
      ))}
    </div>
  );
}
