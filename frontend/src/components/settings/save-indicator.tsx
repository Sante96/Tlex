"use client";

import { Check, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import type { SaveStatus } from "@/hooks/use-profile-preferences";

/** Saving… / Saved, next to the tabs: the preferences save as they change */
export function SaveIndicator({ status }: { status: SaveStatus }) {
  const t = useTranslations();
  if (status === "idle") return null;
  return (
    <span className="flex items-center gap-1.5 text-sm text-[#a1a1aa]" role="status">
      {status === "saving" ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <Check className="h-4 w-4 text-green-400" />
      )}
      {status === "saving" ? t("settings.saving") : t("settings.saved")}
    </span>
  );
}
