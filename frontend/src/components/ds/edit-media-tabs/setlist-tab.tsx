/* ── Tab: Scaletta (concerts) ─────────────────────────────────── */
"use client";

import { useTranslations } from "next-intl";
import type { Chapter } from "@/lib/api";
import { formatTime } from "@/lib/format";

/** The setlist as saved: a trimmed title per line ("" for an untitled song), the blank
 * lines at the end dropped */
export function setlistLines(value: string): string[] {
  const lines = value.split("\n").map((line) => line.trim());
  while (lines.length && !lines[lines.length - 1]) lines.pop();
  return lines;
}

interface SetlistTabProps {
  chapters: Chapter[];
  value: string;
  onChange: (value: string) => void;
}

/**
 * A title per line, in song order, so a whole tracklist can be pasted in; the file's
 * chapters beside it, line for line, to check they match.
 */
export function SetlistTab({ chapters, value, onChange }: SetlistTabProps) {
  const t = useTranslations();
  if (chapters.length === 0) {
    return <p className="text-sm text-[#a1a1aa]">{t("editMedia.noChapters")}</p>;
  }
  const lines = setlistLines(value).length;
  const mismatch = value.trim() !== "" && lines !== chapters.length;

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-[#a1a1aa]">{t("editMedia.setlistHint")}</p>
      {mismatch && (
        <p role="status" className="text-sm text-amber-400">
          {t("editMedia.setlistMismatch", { lines, songs: chapters.length })}
        </p>
      )}
      <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-4">
        <textarea
          aria-label={t("editMedia.setlist")}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={Math.min(Math.max(chapters.length, 6), 40)}
          wrap="off"
          className="w-full px-3 py-2.5 rounded-lg bg-[#18181b] border border-[#3f3f46] text-sm leading-6 text-[#fafafa] outline-none focus:border-plex-orange transition-colors resize-y"
        />
        {/* Same line height and top padding as the field: song N sits beside line N */}
        <ol className="hidden md:block pt-[11px] text-xs leading-6 text-[#a1a1aa] tabular-nums whitespace-nowrap">
          {chapters.map((chapter, i) => (
            <li key={i}>
              {t("player.song", { n: i + 1 })} · {formatTime(chapter.start)}
              {chapter.title ? ` · ${chapter.title}` : ""}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
