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
 * Remove SxEx prefix from episode title (e.g., "S01E03 - Era Ora" -> "Era Ora")
 */
export function cleanEpisodeTitle(title: string): string {
  return title.replace(/^S\d+E\d+\s*-\s*/i, "");
}

/**
 * The URL of a poster/backdrop path: TMDB's ("/abc.jpg", at that size), or one of the
 * library's own images ("local:<name>": a concert's frame, an upload, a saved link),
 * served by the backend at a single size.
 */
export function getTmdbImageUrl(
  path: string | null,
  size: "w300" | "w500" | "w780" | "w1280" | "original" = "w500",
): string | null {
  if (!path) return null;
  if (path.startsWith("local:")) {
    return `${process.env.NEXT_PUBLIC_API_URL || ""}/api/v1/images/${path.slice(6)}`;
  }
  return `${TMDB_IMAGE_BASE}/${size}${path}`;
}

/** The year of a TMDB date ("2020-01-01"). new Date() reads such a date as UTC midnight:
 * west of Greenwich, January 1st fell in the year before. */
export function yearOf(date: string): string {
  return date.slice(0, 4);
}

const BYTE_UNITS = ["byte", "kilobyte", "megabyte", "gigabyte", "terabyte"] as const;

/** A size in the locale's numbers ("48,2 GB"), in steps of 1024 */
export function formatBytes(bytes: number, locale: string): string {
  let unit = 0;
  while (bytes >= 1024 && unit < BYTE_UNITS.length - 1) {
    bytes /= 1024;
    unit++;
  }
  return new Intl.NumberFormat(locale, {
    style: "unit",
    unit: BYTE_UNITS[unit],
    minimumFractionDigits: unit >= 2 ? 1 : 0,
    maximumFractionDigits: unit >= 2 ? 1 : 0,
  }).format(bytes);
}

/** A timestamp from the backend: the database keeps UTC without a zone, which new Date()
 * reads as local time (an hour or two early in Italy). */
export function serverDate(iso: string): Date {
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
}
