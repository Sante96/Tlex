import { api, getShared } from "./client";

export interface MediaItem {
  id: number;
  tmdb_id: number | null;
  title: string;
  overview: string | null;
  poster_path: string | null;
  backdrop_path: string | null;
  release_date: string | null;
  media_type: "MOVIE" | "EPISODE";
  duration_seconds: number | null;
  series_id?: number | null;
  season_number?: number | null;
  episode_number?: number | null;
  vote_average?: number | null;
  genres?: string[] | null;
  content_rating?: string | null;
  watch_progress?: number;
  unwatched_count?: number;
}

export interface MediaStream {
  id: number;
  stream_index: number;
  codec_type: "VIDEO" | "AUDIO" | "SUBTITLE";
  codec_name: string;
  language: string | null;
  title: string | null;
  is_default: boolean;
}

export interface MediaDetails extends MediaItem {
  parts: Array<{
    id: number;
    part_index: number;
    file_size: number;
  }>;
  streams: MediaStream[];
  total_size: number;
}

export interface CastMember {
  id: number;
  name: string;
  character: string | null;
  job: string | null;
  profile_path: string | null;
  order: number;
}

export interface EpisodeInfo {
  episode_number: number;
  name: string;
  overview: string | null;
  still_path: string | null;
  air_date: string | null;
  runtime: number | null;
}

export async function getMediaList({
  skip = 0,
  limit = 20,
  ...filters
}: {
  skip?: number;
  limit?: number;
  media_type?: string;
  search?: string;
  /** "recent": newest first (the home rows); default by title */
  sort?: "title" | "recent";
} = {}) {
  // The backend paginates with page/page_size: skip/limit used to be ignored (max 20 items)
  const response = await api.get<{
    items: MediaItem[];
    total: number;
    page: number;
    page_size: number;
  }>("/api/v1/media", {
    params: { ...filters, page_size: limit, page: Math.floor(skip / limit) + 1 },
  });
  return response.data;
}

export function getMediaDetails(id: number) {
  return getShared<MediaDetails>(`/api/v1/media/${id}`);
}

export async function deleteMedia(id: number) {
  await api.delete(`/api/v1/media/${id}`);
}

export async function refreshMetadata(id: number) {
  const response = await api.post<{
    message: string;
    tmdb_id: number;
    title: string;
    poster_path: string | null;
  }>(`/api/v1/media/${id}/refresh-metadata`);
  return response.data;
}

export async function getMediaCast(id: number): Promise<CastMember[]> {
  const response = await api.get<CastMember[]>(`/api/v1/media/${id}/cast`);
  return response.data;
}

export async function getMediaTrailer(id: number): Promise<string | null> {
  const response = await api.get<{ key: string | null }>(
    `/api/v1/media/${id}/trailer`,
  );
  return response.data.key;
}

export interface NextEpisode {
  id: number;
  title: string;
  season_number: number | null;
  episode_number: number | null;
  duration_seconds: number | null;
  poster_path: string | null;
  backdrop_path: string | null;
  still_path: string | null;
}

export async function getNextEpisode(
  mediaId: number,
): Promise<NextEpisode | null> {
  try {
    const response = await api.get<NextEpisode | null>(
      `/api/v1/media/${mediaId}/next`,
    );
    return response.data;
  } catch {
    return null;
  }
}

export interface TMDBImage {
  file_path: string;
  width: number | null;
  height: number | null;
}

export interface TMDBImagesResponse {
  stills: TMDBImage[];
  posters: TMDBImage[];
  backdrops: TMDBImage[];
}

export interface MediaUpdateBody {
  title?: string;
  overview?: string;
  poster_path?: string;
  backdrop_path?: string;
  release_date?: string;
}

export async function updateMediaItem(
  id: number,
  body: MediaUpdateBody,
): Promise<MediaItem> {
  const response = await api.patch<MediaItem>(`/api/v1/media/${id}`, body);
  return response.data;
}

export async function getMediaTmdbImages(
  id: number,
): Promise<TMDBImagesResponse> {
  const response = await api.get<TMDBImagesResponse>(
    `/api/v1/media/${id}/tmdb-images`,
  );
  return response.data;
}

export async function triggerScan(limit = 100) {
  const response = await api.post("/api/v1/scanner/scan", { limit });
  return response.data;
}

export async function getScanStatus() {
  const response = await api.get("/api/v1/scanner/status");
  return response.data;
}
