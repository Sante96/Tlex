import { api } from "./client";
import type { CastMember, TMDBImagesResponse } from "./media";

export interface SeriesItem {
  id: number;
  tmdb_id: number | null;
  title: string;
  overview: string | null;
  poster_path: string | null;
  backdrop_path: string | null;
  first_air_date: string | null;
  genres: string[];
  vote_average: number | null;
  content_rating: string | null;
  seasons_count: number;
  episodes_count: number;
}

export interface EpisodeWatchProgress {
  position_seconds: number;
  duration_seconds: number;
  progress_percent: number;
  is_completed: boolean;
}

export interface SeasonInfo {
  season_number: number;
  poster_path: string | null;
  episodes_count: number;
  episodes: Array<{
    id: number;
    episode_number: number | null;
    title: string;
    overview: string | null;
    still_path: string | null;
    release_date: string | null;
    duration_seconds: number | null;
    watch_progress: EpisodeWatchProgress | null;
  }>;
}

export interface SeriesDetails extends SeriesItem {
  seasons: SeasonInfo[];
}

export async function getSeriesList(params?: {
  page?: number;
  page_size?: number;
  search?: string;
}) {
  const response = await api.get<{
    items: SeriesItem[];
    total: number;
    page: number;
    page_size: number;
  }>("/api/v1/series/", { params });
  return response.data;
}

export async function getSeriesDetails(id: number): Promise<SeriesDetails> {
  const response = await api.get<SeriesDetails>(`/api/v1/series/${id}`);
  return response.data;
}

export async function refreshSeriesMetadata(id: number) {
  const response = await api.post<{
    message: string;
    tmdb_id: number;
    title: string;
  }>(`/api/v1/series/${id}/refresh-metadata`);
  return response.data;
}

export async function getSeriesCast(id: number): Promise<CastMember[]> {
  const response = await api.get<CastMember[]>(`/api/v1/series/${id}/cast`);
  return response.data;
}

export interface SeriesUpdateBody {
  title?: string;
  overview?: string;
  poster_path?: string;
  backdrop_path?: string;
  first_air_date?: string;
}

export async function updateSeries(id: number, body: SeriesUpdateBody) {
  const response = await api.patch(`/api/v1/series/${id}`, body);
  return response.data;
}

export async function getSeriesTmdbImages(
  id: number,
): Promise<TMDBImagesResponse> {
  const response = await api.get<TMDBImagesResponse>(
    `/api/v1/series/${id}/tmdb-images`,
  );
  return response.data;
}

export async function updateSeasonPoster(
  seriesId: number,
  seasonNumber: number,
  posterPath: string,
) {
  const response = await api.patch(
    `/api/v1/series/${seriesId}/season/${seasonNumber}`,
    {
      poster_path: posterPath,
    },
  );
  return response.data;
}

export async function getSeasonTmdbImages(
  seriesId: number,
  seasonNumber: number,
): Promise<TMDBImagesResponse> {
  const response = await api.get<TMDBImagesResponse>(
    `/api/v1/series/${seriesId}/season/${seasonNumber}/tmdb-images`,
  );
  return response.data;
}
