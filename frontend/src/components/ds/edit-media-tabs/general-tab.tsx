/* ── Tab: Generale ────────────────────────────────────────────── */
"use client";

import { useTranslations } from "next-intl";
import { Field } from "./field";

interface GeneralTabProps {
  title: string;
  overview: string;
  releaseDate: string;
  onTitleChange: (v: string) => void;
  onOverviewChange: (v: string) => void;
  onReleaseDateChange: (v: string) => void;
}

export function GeneralTab({
  title,
  overview,
  releaseDate,
  onTitleChange,
  onOverviewChange,
  onReleaseDateChange,
}: GeneralTabProps) {
  const t = useTranslations("editMedia");
  return (
    <div className="flex flex-col gap-5">
      <Field label={t("fieldTitle")}>
        <input
          type="text"
          value={title}
          onChange={(e) => onTitleChange(e.target.value)}
          className="w-full h-10 px-3 rounded-lg bg-white/5 border border-white/10 text-sm text-[#fafafa] placeholder:text-[#52525b] outline-none focus:border-[#e5a00d] transition-colors"
        />
      </Field>
      <Field label={t("releaseDate")}>
        <input
          type="date"
          value={releaseDate}
          onChange={(e) => onReleaseDateChange(e.target.value)}
          className="w-48 h-10 px-3 rounded-lg bg-white/5 border border-white/10 text-sm text-[#fafafa] outline-none focus:border-[#e5a00d] transition-colors"
        />
      </Field>
      <Field label={t("synopsis")}>
        <textarea
          value={overview}
          onChange={(e) => onOverviewChange(e.target.value)}
          rows={5}
          className="w-full px-3 py-2.5 rounded-lg bg-white/5 border border-white/10 text-sm text-[#fafafa] placeholder:text-[#52525b] outline-none focus:border-[#e5a00d] transition-colors resize-none"
        />
      </Field>
    </div>
  );
}
