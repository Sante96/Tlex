"use client";

import { RefreshCw, Server } from "lucide-react";
import { useTranslations } from "next-intl";
import { DSButton, DSCard } from "@/components/ds";
import type { WorkersStatusResponse } from "@/lib/api";

interface WorkersCardProps {
  data: WorkersStatusResponse | null;
  loading: boolean;
  onRefresh: () => void;
}

export function WorkersCard({ data, loading, onRefresh }: WorkersCardProps) {
  const t = useTranslations();
  return (
    <DSCard
      icon={<Server className="w-5 h-5 text-[#e5a00d]" />}
      title={t("workers.title")}
      description={t("workers.description")}
    >
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-[#fafafa]">{t("workers.status")}</span>
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

        {data && (
          <>
            {/* Summary Stats */}
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="bg-white/[0.05] border border-white/[0.06] rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-green-500">
                  {data.summary.active}
                </div>
                <div className="text-xs text-[#71717a]">{t("workers.active")}</div>
              </div>
              <div className="bg-white/[0.05] border border-white/[0.06] rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-yellow-500">
                  {data.summary.flood_wait}
                </div>
                <div className="text-xs text-[#71717a]">{t("workers.floodWait")}</div>
              </div>
            </div>

            {/* Client Pool Stats */}
            <div className="bg-white/[0.05] border border-white/[0.06] rounded-lg p-3">
              <div className="text-sm font-medium text-[#fafafa] mb-2">
                {t("workers.clientPool")}
              </div>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <div className="text-lg font-bold text-blue-400">
                    {data.summary.total_clients}
                  </div>
                  <div className="text-xs text-[#71717a]">{t("workers.total")}</div>
                </div>
                <div>
                  <div className="text-lg font-bold text-orange-400">
                    {data.summary.clients_in_use}
                  </div>
                  <div className="text-xs text-[#71717a]">{t("common.on")}</div>
                </div>
                <div>
                  <div className="text-lg font-bold text-green-400">
                    {data.summary.clients_available}
                  </div>
                  <div className="text-xs text-[#71717a]">{t("workers.inactive")}</div>
                </div>
              </div>
            </div>

            <div className="h-px bg-[#27272a]" />

            {/* Worker List */}
            <div className="space-y-2">
              {data.workers.map((worker) => (
                <div
                  key={worker.id}
                  className="flex items-center justify-between bg-white/[0.05] border border-white/[0.06] rounded-lg p-3"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-2 h-2 rounded-full ${
                        worker.status === "ACTIVE"
                          ? "bg-green-500"
                          : worker.status === "FLOOD_WAIT"
                            ? "bg-yellow-500"
                            : "bg-red-500"
                      }`}
                    />
                    <div>
                      <div className="text-sm font-medium">
                        Worker #{worker.id}
                        {worker.is_premium && (
                          <span className="ml-2 text-xs text-[#e5a00d]">
                            Premium
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-[#71717a]">
                        ****{worker.phone}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm">
                      {worker.clients_in_use}/{worker.clients_total} client
                    </div>
                    {worker.flood_wait_remaining_seconds && (
                      <div className="text-xs text-yellow-500">
                        FloodWait:{" "}
                        {Math.ceil(worker.flood_wait_remaining_seconds / 60)}m
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </DSCard>
  );
}
