"use client";

import { useEffect, useState } from "react";
import { Download as DownloadIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { AddTorrentCard } from "@/components/downloads/add-torrent-card";
import { SeedboxStatus } from "@/components/downloads/seedbox-status";
import { TorrentCard } from "@/components/downloads/torrent-card";
import {
  getDownloads,
  type Download,
  type SeedboxStatus as Seedbox,
} from "@/lib/api";

const POLL_MS = 3000;

export default function DownloadsPage() {
  const t = useTranslations("downloads");
  const [data, setData] = useState<{
    seedbox: Seedbox;
    downloads: Download[];
  } | null>(null);

  const load = async () => {
    try {
      setData(await getDownloads());
    } catch {
      // The next round tries again
    }
  };

  // Every 3 s while the page is in sight; one round at a time
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    let stopped = false;
    const tick = async () => {
      if (document.visibilityState === "visible") await load();
      if (!stopped) timer = setTimeout(tick, POLL_MS);
    };
    void tick();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, []);

  const uploading = data?.downloads.find((d) => d.upload)?.upload;

  return (
    <div className="px-4 md:px-12 py-6 md:py-8 flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
        <div>
          <h1 className="text-[28px] font-bold text-[#fafafa]">{t("title")}</h1>
          <p className="text-xs text-[#71717a]">{t("subtitle")}</p>
        </div>
        {data && (
          <SeedboxStatus
            seedbox={data.seedbox}
            telegramSpeed={uploading?.speed ?? null}
          />
        )}
      </div>

      <AddTorrentCard onAdded={load} />

      {data?.downloads.map((d) => (
        <TorrentCard key={d.id} download={d} onChanged={load} />
      ))}

      {data?.downloads.length === 0 && (
        <div className="flex flex-col items-center py-16 text-center">
          <DownloadIcon className="w-12 h-12 mb-3 text-[#52525b]" />
          <p className="text-[#a1a1aa]">{t("empty")}</p>
        </div>
      )}
    </div>
  );
}
