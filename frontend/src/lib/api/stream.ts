import { api, API_BASE_URL } from "./client";

export function getStreamUrl(
  mediaId: number,
  options?: {
    audio?: number;
    video?: number;
    t?: number;
  },
) {
  const params = new URLSearchParams();
  if (options?.audio !== undefined) params.set("audio", String(options.audio));
  if (options?.video !== undefined) params.set("video", String(options.video));
  if (options?.t !== undefined) params.set("t", String(options.t));

  const query = params.toString();
  // Use Next.js rewrite (/api/v1/* → backend) for proper disconnect handling
  return `${API_BASE_URL}/api/v1/stream/play/${mediaId}${query ? `?${query}` : ""}`;
}

export function getSubtitleUrl(mediaId: number, track = 0, format = "ass") {
  return `/api/v1/subtitles/${mediaId}?track=${track}&format=${format}`;
}

export async function getSubtitleTracks(mediaId: number) {
  const response = await api.get<{
    media_id: number;
    tracks: Array<{
      index: number;
      codec: string;
      language: string | null;
      title: string | null;
      is_default: boolean;
    }>;
    count: number;
  }>(`/api/v1/subtitles/${mediaId}/tracks`);
  return response.data;
}

/**
 * Pre-warm the Telegram file_id cache for faster playback start.
 * Call this when user opens video page, before they click play.
 */
export async function warmStream(mediaId: number) {
  try {
    const response = await api.post<{ status: string; elapsed_ms: number }>(
      `/api/v1/stream/warm/${mediaId}`,
    );
    return response.data;
  } catch {
    return null;
  }
}
