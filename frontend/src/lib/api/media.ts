import { api } from "./client";

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
  season_number?: number | null;
  episode_number?: number | null;
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

export async function getMediaList(params?: {
  skip?: number;
  limit?: number;
  media_type?: string;
  search?: string;
}) {
  const response = await api.get<{
    items: MediaItem[];
    total: number;
    skip: number;
    limit: number;
  }>("/api/v1/media/", { params });
  return response.data;
}

export async function getMediaDetails(id: number) {
  const response = await api.get<MediaDetails>(`/api/v1/media/${id}`);
  return response.data;
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

export async function getMediaEpisodes(id: number): Promise<EpisodeInfo[]> {
  const response = await api.get<EpisodeInfo[]>(`/api/v1/media/${id}/episodes`);
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
