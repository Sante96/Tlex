import { api } from "./client";

export interface WatchProgress {
  media_item_id: number;
  position_seconds: number;
  duration_seconds: number;
  progress_percent: number;
  completed: boolean;
}

export interface ContinueWatchingItem {
  id: number;
  title: string;
  poster_path: string | null;
  backdrop_path: string | null;
  media_type: "MOVIE" | "EPISODE";
  position_seconds: number;
  duration_seconds: number;
  progress_percent: number;
}

export async function getWatchProgress(
  mediaId: number,
): Promise<WatchProgress | null> {
  try {
    const response = await api.get<WatchProgress | null>(
      `/api/v1/progress/${mediaId}`,
    );
    return response.data;
  } catch {
    return null;
  }
}

export async function updateWatchProgress(
  mediaId: number,
  positionSeconds: number,
  durationSeconds: number,
): Promise<WatchProgress> {
  const response = await api.put<WatchProgress>(`/api/v1/progress/${mediaId}`, {
    position_seconds: positionSeconds,
    duration_seconds: durationSeconds,
  });
  return response.data;
}

export async function getContinueWatching(
  limit = 10,
): Promise<ContinueWatchingItem[]> {
  try {
    const response = await api.get<ContinueWatchingItem[]>(
      "/api/v1/progress/",
      {
        params: { limit },
      },
    );
    return response.data;
  } catch {
    return [];
  }
}
