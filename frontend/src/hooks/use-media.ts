"use client";

import { useState, useEffect, useCallback } from "react";
import { getMediaList, getMediaDetails } from "@/lib/api";
import type { MediaItem, MediaDetails, PaginatedResponse } from "@/types/api";

interface UseMediaListOptions {
  limit?: number;
  mediaType?: "MOVIE" | "EPISODE";
  search?: string;
}

export function useMediaList(options: UseMediaListOptions = {}) {
  const { limit = 50, mediaType, search } = options;

  const [data, setData] = useState<PaginatedResponse<MediaItem> | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchMedia = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const result = await getMediaList({
        limit,
        media_type: mediaType,
        search,
      });
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Failed to fetch media"));
    } finally {
      setIsLoading(false);
    }
  }, [limit, mediaType, search]);

  useEffect(() => {
    fetchMedia();
  }, [fetchMedia]);

  return {
    items: data?.items ?? [],
    total: data?.total ?? 0,
    isLoading,
    error,
    refetch: fetchMedia,
  };
}

export function useMediaDetails(mediaId: number | null) {
  const [data, setData] = useState<MediaDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!mediaId) {
      setIsLoading(false);
      return;
    }

    const fetchDetails = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const result = await getMediaDetails(mediaId);
        setData(result);
      } catch (err) {
        setError(
          err instanceof Error
            ? err
            : new Error("Failed to fetch media details"),
        );
      } finally {
        setIsLoading(false);
      }
    };

    fetchDetails();
  }, [mediaId]);

  return { data, isLoading, error };
}
