import { api } from "./client";

// This tab's id: the backend keeps one reader (and its Telegram clients) per player, so
// two devices on one title each get their own, and one closing its player doesn't cut
// the other's stream. Not crypto.randomUUID: it's missing on http:// from the LAN
const VIEWER = Math.random().toString(36).slice(2, 10);

export function getStreamUrl(
  mediaId: number,
  options?: {
    audio?: number;
    video?: number;
    t?: number;
    /** Seek counter: makes the URL change even when seeking to the same time */
    seek?: number;
  },
) {
  const params = new URLSearchParams();
  if (options?.audio !== undefined) params.set("audio", String(options.audio));
  if (options?.video !== undefined) params.set("video", String(options.video));
  if (options?.t !== undefined) params.set("t", String(options.t));
  if (options?.seek) params.set("s", String(options.seek));
  params.set("v", VIEWER);

  const query = params.toString();
  // Use Next.js route handler (/api/stream/*) for proper streaming support
  // The route handler streams with ReadableStream + abort signal propagation
  // The rewrite (/api/v1/*) buffers the entire response — breaks Cloudflare streaming
  return `/api/stream/play/${mediaId}${query ? `?${query}` : ""}`;
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

export interface PoolStatus {
  total_clients: number;
  clients_in_use: number;
  clients_available: number;
  pool_pressure: number;
}

/**
 * Get lightweight pool status for frontend warnings.
 * No DB session required on backend — reads in-memory pool state.
 */
export async function getPoolStatus(): Promise<PoolStatus | null> {
  try {
    const response = await api.get<PoolStatus>("/api/v1/stream/pool-status");
    return response.data;
  } catch {
    return null;
  }
}

/** The Telegram clients a title's stream holds now, of the pool's (the player's ring) */
export async function getStreamClients(
  mediaId: number,
): Promise<{ inUse: number; total: number } | null> {
  try {
    const response = await api.get<{ in_use: number; total: number }>(
      `/api/v1/stream/clients/${mediaId}?v=${VIEWER}`,
    );
    return { inUse: response.data.in_use, total: response.data.total };
  } catch {
    return null;
  }
}

/**
 * Release a cached stream reader and its Telegram clients.
 * Call this when the player unmounts (user navigates away).
 */
export async function releaseStream(mediaId: number) {
  try {
    await api.post(`/api/v1/stream/release/${mediaId}?v=${VIEWER}`);
  } catch {
    // Best-effort — don't block navigation
  }
}
