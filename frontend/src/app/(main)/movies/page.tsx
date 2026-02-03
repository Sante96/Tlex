"use client";

import { useEffect, useState } from "react";
import { LibraryGrid, LibraryHeader } from "@/components/library";
import { getMediaList, triggerScan, type MediaItem } from "@/lib/api";

export default function MoviesPage() {
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
    } catch (error) {
      console.error("Failed to load movies:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    try {
      setRefreshing(true);
      await triggerScan(100);
      await loadMovies();
    } catch (error) {
      console.error("Refresh failed:", error);
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div>
      <LibraryHeader
        title="Film"
        totalCount={movies.length}
        onRefresh={handleRefresh}
        isRefreshing={refreshing}
      />
      <LibraryGrid items={movies} loading={loading} />
    </div>
  );
}
