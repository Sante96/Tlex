import { api, API_BASE_URL } from "./client";

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
  media_type: "MOVIE" | "EPISODE" | "CONCERT";
  position_seconds: number;
  duration_seconds: number;
  progress_percent: number;
  /** The landscape picture: an episode's still, a movie's backdrop */
  still_path?: string | null;
  /** The episode's or movie's synopsis */
  overview?: string | null;
  // Series metadata for Plex-style grouping
  series_id?: number | null;
  series_title?: string | null;
  series_poster_path?: string | null;
  season_number?: number | null;
  episode_number?: number | null;
  /** A concert's anime/game */
  franchise_title?: string | null;
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

/** For pagehide/tab-hidden: a keepalive fetch survives the page going away; axios doesn't. */
export function saveWatchProgressOnExit(
  mediaId: number,
  positionSeconds: number,
  durationSeconds: number,
) {
  fetch(`${API_BASE_URL}/api/v1/progress/${mediaId}`, {
    method: "PUT",
    keepalive: true,
    credentials: "include", // the session cookie
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      position_seconds: positionSeconds,
      duration_seconds: durationSeconds,
    }),
  }).catch(() => {});
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
