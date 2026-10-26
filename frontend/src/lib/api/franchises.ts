import { api, getShared } from "./client";
import type { TMDBImagesResponse } from "./media";
import type { EpisodeWatchProgress } from "./series";

/** An anime/game of the Concerts section (a "Concerti · <name>" topic) */
export interface FranchiseSummary {
  id: number;
  title: string;
  /** Its own images, else its newest concert's (a frame of the video) */
  poster_path: string | null;
  backdrop_path: string | null;
  concerts_count: number;
}

export interface ConcertInfo {
  id: number;
  title: string;
  overview: string | null;
  poster_path: string | null;
  backdrop_path: string | null;
  release_date: string | null;
  duration_seconds: number | null;
  watch_progress: EpisodeWatchProgress | null;
}

export interface FranchiseDetails {
  id: number;
  tmdb_id: number | null;
  title: string;
  overview: string | null;
  poster_path: string | null;
  backdrop_path: string | null;
  /** Newest first */
  concerts: ConcertInfo[];
}

export interface FranchiseUpdateBody {
  title?: string;
  overview?: string;
  poster_path?: string;
  backdrop_path?: string;
}

export async function getFranchises(params?: {
  page?: number;
  page_size?: number;
  search?: string;
}) {
  const response = await api.get<{ items: FranchiseSummary[]; total: number }>(
    "/api/v1/franchises",
    { params },
  );
  return response.data;
}

export function getFranchise(id: number): Promise<FranchiseDetails> {
  return getShared<FranchiseDetails>(`/api/v1/franchises/${id}`);
}

/** Shared: the library's, for everyone */
export async function updateFranchise(id: number, body: FranchiseUpdateBody) {
  const response = await api.patch<FranchiseDetails>(`/api/v1/franchises/${id}`, body);
  return response.data;
}

export async function getFranchiseTmdbImages(id: number): Promise<TMDBImagesResponse> {
  const response = await api.get<TMDBImagesResponse>(`/api/v1/franchises/${id}/tmdb-images`);
  return response.data;
}
