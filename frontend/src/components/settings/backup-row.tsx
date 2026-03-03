"use client";

import {
  RefreshCw,
  Trash2,
  Loader2,
  ToggleLeft,
  ToggleRight,
  ArrowUpCircle,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { DSIconButton, DSCard } from "@/components/ds";
import type { BackupChannel } from "@/lib/api/backup";

interface BackupRowProps {
  backup: BackupChannel;
  syncingId: number | null;
  togglingId: number | null;
  deletingId: number | null;
  promotingId: number | null;
  onSync: (id: number) => void;
  onToggle: (id: number) => void;
  onDelete: (id: number) => void;
  onPromote: (id: number) => void;
}

function getHealthColor(b: BackupChannel) {
  if (b.is_promoted) return "bg-zinc-600";
  if (b.failure_count === 0) return "bg-green-500";
  if (b.failure_count < b.max_failures) return "bg-yellow-400";
  return "bg-red-500";
}

export function BackupRow({
  backup: b,
  syncingId,
  togglingId,
  deletingId,
  promotingId,
  onSync,
  onToggle,
  onDelete,
  onPromote,
}: BackupRowProps) {
  const t = useTranslations("backup");

  return (
    <DSCard
      level="secondary"
      className="p-3 rounded-lg shadow-none backdrop-blur-none gap-2"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={`w-2 h-2 rounded-full shrink-0 ${getHealthColor(b)}`}
            title={`${b.failure_count}/${b.max_failures} failures`}
          />
          <span
            className={`inline-flex items-center h-5 px-2 rounded text-[10px] font-semibold ${
              b.is_promoted
                ? "bg-blue-500/15 text-blue-400"
                : b.is_active
                  ? "bg-green-500/15 text-green-400"
                  : "bg-zinc-700 text-zinc-400"
            }`}
          >
            {b.is_promoted
              ? t("promoted")
              : b.is_active
                ? t("active")
                : t("inactive")}
          </span>
          <span className="text-sm font-medium text-[#fafafa] truncate">
            {b.title}
          </span>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <DSIconButton
            onClick={() => onSync(b.id)}
            disabled={syncingId === b.id}
            title={t("sync")}
            icon={
              syncingId === b.id ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4" />
              )
            }
          />

          <DSIconButton
            onClick={() => onToggle(b.id)}
            disabled={togglingId === b.id}
            className="hover:text-[#e5a00d]"
            title={b.is_active ? t("inactive") : t("active")}
            icon={
              togglingId === b.id ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : b.is_active ? (
                <ToggleRight className="w-4 h-4 text-green-400" />
              ) : (
                <ToggleLeft className="w-4 h-4" />
              )
            }
          />

          {!b.is_promoted && (
            <DSIconButton
              onClick={() => onPromote(b.id)}
              disabled={promotingId === b.id}
              className="hover:text-blue-400"
              title={t("promoteToMain")}
              icon={
                promotingId === b.id ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <ArrowUpCircle className="w-4 h-4" />
                )
              }
            />
          )}

          <DSIconButton
            onClick={() => onDelete(b.id)}
            disabled={deletingId === b.id}
            className="hover:text-red-400"
            icon={
              deletingId === b.id ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Trash2 className="w-4 h-4" />
              )
            }
          />
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 text-xs text-[#71717a]">
        <span>
          {t("mainChannel")} {b.main_channel_id}
        </span>
        <span>·</span>
        <span>
          {t("syncedMessages")}: {b.synced_count}
        </span>
        {b.failure_count > 0 && (
          <>
            <span>·</span>
            <span
              className={
                b.failure_count >= b.max_failures
                  ? "text-red-400"
                  : "text-yellow-400"
              }
            >
              {t("failures")}: {b.failure_count}/{b.max_failures}
            </span>
          </>
        )}
        {b.last_sync_at && (
          <>
            <span>·</span>
            <span>
              {t("lastSync")}:{" "}
              {new Date(b.last_sync_at).toLocaleString(undefined, {
                day: "2-digit",
                month: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          </>
        )}
      </div>

      {b.topics.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {b.topics.map((topic) => (
            <span
              key={topic.main_topic_id}
              className="inline-flex items-center h-5 px-2 rounded bg-[#27272a] text-[#a1a1aa] text-[10px] font-medium"
            >
              {topic.name}
            </span>
          ))}
        </div>
      )}
    </DSCard>
  );
}
