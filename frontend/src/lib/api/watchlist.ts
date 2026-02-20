import { api } from "./client";

export interface WatchlistItem {
  id: number;
  media_item_id: number | null;
  series_id: number | null;
  item_type: string; // "movie", "episode", or "series"
  added_at: string;
  title: string;
  poster_path: string | null;
  media_type: string | null;
  duration_seconds: number | null;
}

export interface WatchlistResponse {
  items: WatchlistItem[];
  total: number;
}

export async function getWatchlist(): Promise<WatchlistResponse> {
  const response = await api.get<WatchlistResponse>("/api/v1/watchlist/");
  return response.data;
}

export async function addToWatchlist(mediaId: number): Promise<void> {
  await api.post(`/api/v1/watchlist/${mediaId}`);
}

export async function removeFromWatchlist(mediaId: number): Promise<void> {
  await api.delete(`/api/v1/watchlist/${mediaId}`);
}

export async function checkWatchlistStatus(mediaId: number): Promise<boolean> {
  const response = await api.get<{ in_watchlist: boolean }>(
    `/api/v1/watchlist/${mediaId}/status`,
  );
  return response.data.in_watchlist;
}

export async function addSeriesToWatchlist(seriesId: number): Promise<void> {
  await api.post(`/api/v1/watchlist/series/${seriesId}`);
}

export async function removeSeriesFromWatchlist(
  seriesId: number,
): Promise<void> {
  await api.delete(`/api/v1/watchlist/series/${seriesId}`);
}

export async function checkSeriesWatchlistStatus(
  seriesId: number,
): Promise<boolean> {
  const response = await api.get<{ in_watchlist: boolean }>(
    `/api/v1/watchlist/series/${seriesId}/status`,
  );
  return response.data.in_watchlist;
}
