/**
 * Utility functions for fetching subtitle content and font metadata.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

// No cache buster: a track's file never changes once extracted, and the backend lets the
// browser keep it a day (202 "still extracting" answers are not cached)
function getSubtitleUrl(mediaId: number, track: number, format: SubtitleFormat): string {
  return `${API_BASE_URL}/api/v1/subtitles/${mediaId}?track=${track}&format=${format}`;
}

/** ass: a text track, for libass. sup: a PGS (Blu-ray picture) track, for libpgs */
export type SubtitleFormat = "ass" | "sup";

export async function fetchAvailableFonts(
  mediaId: number,
): Promise<Record<string, string>> {
  const fonts: Record<string, string> = { default: "/lib/default.woff2" };

  try {
    const url = `${API_BASE_URL}/api/v1/subtitles/${mediaId}/fonts`;
    const resp = await fetch(url);
    if (!resp.ok) return fonts;

    const data = await resp.json();
    for (const font of data.fonts || []) {
      const fontUrl = `${API_BASE_URL}${font.url}`;
      const filename = font.filename
        .toLowerCase()
        .replace(/\.(ttf|otf|woff|woff2)$/i, "");

      // Register by filename
      fonts[filename] = fontUrl;

      // Register by internal font names (Family, Full Name, PostScript)
      for (const name of (font.names || []) as string[]) {
        if (name) fonts[name.toLowerCase()] = fontUrl;
      }

      // Filename-based aliases (e.g., "arialb" → "arial")
      const baseMatch = filename.match(/^(.+?)(b|i|z|bold|italic|regular)?$/i);
      if (baseMatch) {
        const base = baseMatch[1].replace(/[-_]$/, "");
        if (base !== filename) fonts[base] = fontUrl;
      }

      // Spaced variant (e.g., "open-sans" → "open sans")
      const spaced = filename.replace(/[-_]/g, " ");
      if (spaced !== filename) fonts[spaced] = fontUrl;
    }
  } catch {
    // Could not fetch fonts, using fallback
  }

  return fonts;
}

/**
 * The backend answers 202 (+ Retry-After) while it extracts a track that isn't cached
 * yet; keep asking until it's ready or the caller no longer wants it (isStale).
 * Returns the ready response, to read as text (ass) or bytes (sup).
 */
export async function fetchSubtitleFile(
  mediaId: number,
  track: number,
  format: SubtitleFormat,
  isStale: () => boolean = () => false,
): Promise<Response | null> {
  try {
    while (!isStale()) {
      const resp = await fetch(getSubtitleUrl(mediaId, track, format));
      if (resp.status === 202) {
        const retryAfter = Number(resp.headers.get("Retry-After")) || 5;
        await new Promise((resolve) => setTimeout(resolve, retryAfter * 1000));
        continue;
      }
      return resp.ok ? resp : null;
    }
  } catch {
    // Error fetching subtitles
  }
  return null;
}
