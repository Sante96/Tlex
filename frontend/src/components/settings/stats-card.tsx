"use client";

import { BarChart3, Film, Tv, Users, RefreshCw } from "lucide-react";
import { DSButton } from "@/components/ds";
import type { SystemStats } from "@/lib/api";

interface StatsCardProps {
  data: SystemStats | null;
  loading: boolean;
  onRefresh: () => void;
}

export function StatsCard({ data, loading, onRefresh }: StatsCardProps) {
  if (!data) return null;

  return (
    <div className="bg-zinc-900 rounded-lg p-6">
      <div className="flex items-center gap-3 mb-4">
        <BarChart3 className="w-5 h-5 text-plex-orange" />
        <div>
          <h2 className="font-semibold">Statistiche</h2>
          <p className="text-xs text-muted-foreground">Libreria e utenti</p>
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-[#fafafa]">Dati</span>
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
          <div className="bg-zinc-800 rounded-lg p-2 text-center">
            <Film className="w-4 h-4 mx-auto mb-1 text-blue-500" />
            <div className="text-lg font-bold">{data.media.movies}</div>
            <div className="text-xs text-muted-foreground">Film</div>
          </div>
          <div className="bg-zinc-800 rounded-lg p-2 text-center">
            <Tv className="w-4 h-4 mx-auto mb-1 text-purple-500" />
            <div className="text-lg font-bold">{data.media.episodes}</div>
            <div className="text-xs text-muted-foreground">Episodi</div>
          </div>
          <div className="bg-zinc-800 rounded-lg p-2 text-center">
            <Users className="w-4 h-4 mx-auto mb-1 text-green-500" />
            <div className="text-lg font-bold">{data.users.profiles}</div>
            <div className="text-xs text-muted-foreground">Profili</div>
          </div>
        </div>

        <div className="text-xs text-muted-foreground pt-1">
          {data.users.total} utenti · {data.media.total} media
        </div>
      </div>
    </div>
  );
}
