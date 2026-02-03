export interface User {
  id: number;
  email: string;
  is_admin: boolean;
}

export interface Profile {
  id: number;
  user_id: number;
  name: string;
  avatar_url: string | null;
}

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
}

export interface MediaPart {
  id: number;
  part_index: number;
  file_size: number;
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
  parts: MediaPart[];
  streams: MediaStream[];
  total_size: number;
}

export interface SubtitleTrack {
  index: number;
  codec: string;
  language: string | null;
  title: string | null;
  is_default: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export interface AuthTokens {
  access_token: string;
  token_type: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}
