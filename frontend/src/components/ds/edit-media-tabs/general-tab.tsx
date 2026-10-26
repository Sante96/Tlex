/* ── Tab: Generale ────────────────────────────────────────────── */
"use client";

import { useTranslations } from "next-intl";
import { DSInput, DSDatePicker } from "@/components/ds";
import { Field } from "./field";

interface GeneralTabProps {
  title: string;
  overview: string;
  releaseDate: string;
  onTitleChange: (v: string) => void;
  onOverviewChange: (v: string) => void;
  onReleaseDateChange: (v: string) => void;
  /** A franchise (anime/game page) has no date */
  showDate?: boolean;
}

export function GeneralTab({
  title,
  overview,
  releaseDate,
  onTitleChange,
  onOverviewChange,
  onReleaseDateChange,
  showDate = true,
  children,
}: GeneralTabProps & { children?: React.ReactNode }) {
  const t = useTranslations("editMedia");
  return (
    <div className="flex flex-col gap-5">
      <Field label={t("fieldTitle")}>
        <DSInput
          type="text"
          value={title}
          onChange={(e) => onTitleChange(e.target.value)}
        />
      </Field>
      {showDate && (
        <Field label={t("releaseDate")}>
          <DSDatePicker
            value={releaseDate}
            onChange={onReleaseDateChange}
            className="w-48"
          />
        </Field>
      )}
      <Field label={t("synopsis")}>
        <textarea
          value={overview}
          onChange={(e) => onOverviewChange(e.target.value)}
          rows={5}
          className="w-full px-3 py-2.5 rounded-lg bg-[#18181b] border border-[#3f3f46] text-sm text-[#fafafa] placeholder:text-[#52525b] outline-none focus:border-plex-orange focus:border-2 transition-colors resize-none"
        />
      </Field>
      {children}
    </div>
  );
}
