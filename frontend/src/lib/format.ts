/**
 * Formatting utility functions
 */

export const TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p";

/**
 * Format seconds to HH:MM:SS or MM:SS
 */
export function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) {
    return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  }
  return `${m}:${s.toString().padStart(2, "0")}`;
}

/**
 * Format seconds to human readable duration (e.g., "1h 30m" or "45m")
 */
export function formatDuration(seconds: number | null): string | null {
  if (!seconds) return null;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) {
    return `${h}h ${m}m`;
  }
  return `${m}m`;
}

/**
 * Format seconds to short duration (e.g., "45 min")
 */
export function formatDurationShort(seconds: number | null): string | null {
  if (!seconds) return null;
  const m = Math.floor(seconds / 60);
  return `${m} min`;
}

/**
 * Format bytes to human readable size (KB, MB, GB)
 */
export function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  if (bytes < 1024 * 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

/**
 * Remove SxEx prefix from episode title (e.g., "S01E03 - Era Ora" -> "Era Ora")
 */
export function cleanEpisodeTitle(title: string): string {
  return title.replace(/^S\d+E\d+\s*-\s*/i, "");
}

/**
 * Build TMDB image URL
 */
export function getTmdbImageUrl(
  path: string | null,
  size: "w300" | "w500" | "w780" | "w1280" | "original" = "w500",
): string | null {
  if (!path) return null;
  return `${TMDB_IMAGE_BASE}/${size}${path}`;
}
