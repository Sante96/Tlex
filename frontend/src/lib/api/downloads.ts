import { api } from "./client";

export type DownloadKind = "film" | "series" | "anime" | "concert";
export type DownloadStatus =
  | "queued"
  | "downloading"
  | "uploading"
  | "scanning"
  | "removing"
  | "library"
  | "error";

export interface SeedboxStatus {
  connected: boolean;
  /** Epoch seconds of the agent's last sync */
  last_seen: number | null;
  free_bytes: number | null;
  dl_speed: number | null;
  up_speed: number | null;
}

export interface DownloadFile {
  path: string;
  size: number;
  /** A topic name, or the films topic's id */
  topic: string | number;
  topic_id: number | null;
  progress: number;
  message_ids: number[];
  uploaded: boolean;
}

/** The torrent in qBittorrent, as the agent last reported it */
export interface DownloadLive {
  hash: string;
  state: string;
  progress: number;
  dlspeed: number;
  upspeed: number;
  num_peers: number;
  num_seeds: number;
  /** Seconds; qBittorrent says 8640000 for "never" */
  eta: number;
  size: number;
}

/** The file going to Telegram right now */
export interface DownloadUpload {
  path: string;
  part: number;
  parts: number;
  percent: number;
  speed: number;
  eta: number | null;
}

export interface Download {
  id: number;
  kind: DownloadKind;
  name: string | null;
  season: number | null;
  torrent_name: string | null;
  status: DownloadStatus;
  paused: boolean;
  error: string | null;
  files: DownloadFile[];
  live: DownloadLive | null;
  upload: DownloadUpload | null;
  topics: (string | number)[];
  created_at: string;
  finished_at: string | null;
}

export interface TorrentPreview {
  torrent_name: string | null;
  name: string | null;
  season: number | null;
}

// The client's default JSON type would turn a form into JSON: this one lets the browser
// write the multipart boundary
const MULTIPART = { headers: { "Content-Type": "multipart/form-data" } };

function form(
  fields: Record<string, string | number | File | undefined>,
): FormData {
  const data = new FormData();
  for (const [key, value] of Object.entries(fields)) {
    if (value !== undefined && value !== "")
      data.append(key, value instanceof File ? value : String(value));
  }
  return data;
}

export async function getDownloads(): Promise<{
  seedbox: SeedboxStatus;
  downloads: Download[];
}> {
  const { data } = await api.get<{
    seedbox: SeedboxStatus;
    downloads: Download[];
  }>("/api/v1/downloads");
  return data;
}

/** The torrent's name, and the name and season the form starts from */
export async function previewTorrent(input: {
  magnet?: string;
  torrent?: File;
}): Promise<TorrentPreview> {
  const { data } = await api.post<TorrentPreview>(
    "/api/v1/downloads/preview",
    form(input),
    MULTIPART,
  );
  return data;
}

/** Rejects with 400 (bad input, the reason in `detail`) or 409 (that magnet is already here) */
export async function addDownload(input: {
  magnet?: string;
  torrent?: File;
  kind: DownloadKind;
  name?: string;
  season?: number;
}): Promise<Download> {
  const { data } = await api.post<Download>(
    "/api/v1/downloads",
    form(input),
    MULTIPART,
  );
  return data;
}

/** Saved at once; files already on Telegram move to the new topic in the background */
export async function updateDownload(
  id: number,
  body: { kind: DownloadKind; name: string | null; season: number | null },
): Promise<Download> {
  const { data } = await api.patch<Download>(`/api/v1/downloads/${id}`, body);
  return data;
}

export async function pauseDownload(id: number): Promise<void> {
  await api.post(`/api/v1/downloads/${id}/pause`);
}

export async function resumeDownload(id: number): Promise<void> {
  await api.post(`/api/v1/downloads/${id}/resume`);
}

/** Off the seedbox only: what is already in the library stays */
export async function removeDownload(id: number): Promise<void> {
  await api.delete(`/api/v1/downloads/${id}`);
}
