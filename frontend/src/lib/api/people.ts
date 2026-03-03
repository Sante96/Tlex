import { api } from "./client";

export interface PersonWork {
  tmdb_id: number;
  media_type: "movie" | "tv";
  title: string;
  poster_path: string | null;
  release_date: string | null;
  character: string | null;
  job: string | null;
  in_catalog: boolean;
  catalog_id: number | null;
  catalog_type: "media" | "series" | null;
}

export interface PersonDetails {
  id: number;
  name: string;
  biography: string | null;
  birthday: string | null;
  place_of_birth: string | null;
  profile_path: string | null;
  imdb_id: string | null;
  instagram_id: string | null;
  twitter_id: string | null;
  works: PersonWork[];
}

export async function getPersonDetails(
  personId: number,
): Promise<PersonDetails> {
  const response = await api.get<PersonDetails>(`/api/v1/people/${personId}`);
  return response.data;
}
