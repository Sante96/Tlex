"use client";

import { BarChart3, Film, Tv, Users, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { DSButton, DSCard } from "@/components/ds";
import type { SystemStats } from "@/lib/api";

interface StatsCardProps {
  data: SystemStats | null;
  loading: boolean;
  onRefresh: () => void;
}

export function StatsCard({ data, loading, onRefresh }: StatsCardProps) {
  const t = useTranslations();
  if (!data) return null;

  return (
    <DSCard
      icon={<BarChart3 className="w-5 h-5 text-[#e5a00d]" />}
      title={t("stats.title")}
      description={t("stats.description")}
    >
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-[#fafafa]">{t("stats.data")}</span>
          <DSButton
            variant="ghost"
            onClick={onRefresh}
            disabled={loading}
            className="!h-8 !w-8 !px-0"
            icon={
              <RefreshCw
                className={`w-4 h-4 ${loading ? "animate-spin" : ""}`}
              />
            }
          />
        </div>

        <div className="grid grid-cols-3 gap-2">
          <div className="bg-white/[0.05] border border-white/[0.06] rounded-lg p-2 text-center">
            <Film className="w-4 h-4 mx-auto mb-1 text-blue-400" />
            <div className="text-lg font-bold">{data.media.movies}</div>
            <div className="text-xs text-[#71717a]">{t("home.movies")}</div>
          </div>
          <div className="bg-white/[0.05] border border-white/[0.06] rounded-lg p-2 text-center">
            <Tv className="w-4 h-4 mx-auto mb-1 text-purple-400" />
            <div className="text-lg font-bold">{data.media.episodes}</div>
            <div className="text-xs text-[#71717a]">{t("stats.episodes")}</div>
          </div>
          <div className="bg-white/[0.05] border border-white/[0.06] rounded-lg p-2 text-center">
            <Users className="w-4 h-4 mx-auto mb-1 text-green-400" />
            <div className="text-lg font-bold">{data.users.profiles}</div>
            <div className="text-xs text-[#71717a]">{t("stats.profiles")}</div>
          </div>
        </div>

        <div className="text-xs text-[#71717a] pt-1">
          {data.users.total} {t("stats.users")} · {data.media.total} media
        </div>
      </div>
    </DSCard>
  );
}
