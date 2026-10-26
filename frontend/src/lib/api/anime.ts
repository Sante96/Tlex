import { api } from "./client";

/** A title of the Anime section: a series or a film */
export interface AnimeItem {
  kind: "series" | "movie";
  id: number;
  title: string;
  poster_path: string | null;
  backdrop_path: string | null;
  /** First air date or release date */
  date: string | null;
  seasons_count: number | null;
  /** What orders "recent": a film's id, a series' newest episode's */
  added: number;
}

/** Japanese animation, series and films together */
export async function getAnimeList(params: {
  page?: number;
  page_size?: number;
  sort?: "title" | "recent";
}) {
  const response = await api.get<{
    items: AnimeItem[];
    total: number;
    page: number;
    page_size: number;
  }>("/api/v1/anime", { params });
  return response.data;
}
