"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { DSButton } from "@/components/ds";

// A page that crashes while rendering: Next's default screen had nothing a D-pad could
// focus, so on the TV the only way out was leaving the app
export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  const t = useTranslations();
  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-4 px-4 bg-[#09090b] text-center">
      <h1 className="text-2xl font-bold text-[#fafafa]">{t("errors.crashTitle")}</h1>
      <p className="text-[#a1a1aa]">{t("errors.crashText")}</p>
      <div className="mt-2 flex gap-3">
        <DSButton onClick={reset} autoFocus>
          {t("common.retry")}
        </DSButton>
        <Link
          href="/"
          className="h-11 px-6 inline-flex items-center rounded-[10px] bg-[#27272a] text-[#fafafa] font-medium outline-none focus-visible:ring-2 focus-visible:ring-plex-orange"
        >
          {t("nav.home")}
        </Link>
      </div>
    </main>
  );
}
