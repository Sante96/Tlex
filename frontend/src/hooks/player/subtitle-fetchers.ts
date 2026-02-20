/**
 * Utility functions for fetching subtitle content and font metadata.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

export function getSubtitleUrl(mediaId: number, track: number): string {
  const cacheBuster = Date.now();
  return `${API_BASE_URL}/api/v1/subtitles/${mediaId}?track=${track}&format=ass&_=${cacheBuster}`;
}

export async function fetchAvailableFonts(
  mediaId: number,
): Promise<Record<string, string>> {
  const fonts: Record<string, string> = { default: "/lib/default.woff2" };

  try {
    const url = `${API_BASE_URL}/api/v1/subtitles/${mediaId}/fonts?_=${Date.now()}`;
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

export async function fetchSubtitleContent(
  mediaId: number,
  track: number,
): Promise<string | null> {
  try {
    const resp = await fetch(getSubtitleUrl(mediaId, track));
    if (resp.ok) return await resp.text();
  } catch {
    // Error fetching subtitles
  }
  return null;
}
