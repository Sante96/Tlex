"use client";

import { useLocale, useTranslations } from "next-intl";
import type { SeedboxStatus as Seedbox } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import { cn } from "@/lib/utils";

/** The header's line: free space and speeds, or how to start the agent */
export function SeedboxStatus({
  seedbox,
  telegramSpeed,
}: {
  seedbox: Seedbox;
  /** The upload to Telegram running now, bytes/s */
  telegramSpeed: number | null;
}) {
  const t = useTranslations("downloads");
  const locale = useLocale();
  const size = (bytes: number) => formatBytes(bytes, locale);

  const parts = seedbox.connected
    ? [
        seedbox.free_bytes !== null &&
          t("seedboxFree", { size: size(seedbox.free_bytes) }),
        seedbox.dl_speed !== null && `↓ ${size(seedbox.dl_speed)}/s`,
        telegramSpeed !== null &&
          t("seedboxToTelegram", { speed: `${size(telegramSpeed)}/s` }),
      ]
    : [
        t("seedboxOffline"),
        seedbox.last_seen !== null &&
          t("seedboxLastSeen", {
            time: new Date(seedbox.last_seen * 1000).toLocaleString(locale, {
              day: "2-digit",
              month: "2-digit",
              hour: "2-digit",
              minute: "2-digit",
            }),
          }),
      ];

  return (
    <div className="flex flex-col gap-1 text-xs text-[#a1a1aa] md:items-end">
      <p className="flex items-center gap-2">
        <span
          className={cn(
            "w-2 h-2 rounded-full shrink-0",
            seedbox.connected ? "bg-green-500" : "bg-red-500",
          )}
        />
        <span>Seedbox: {parts.filter(Boolean).join(" · ")}</span>
      </p>
      {!seedbox.connected && (
        <p>
          {t("seedboxStart")}{" "}
          <code className="inline-block whitespace-nowrap px-1.5 py-0.5 rounded bg-[#27272a] text-[#fafafa] font-mono select-all">
            bash ~/tlex-upload/start-agent.sh
          </code>
        </p>
      )}
    </div>
  );
}
