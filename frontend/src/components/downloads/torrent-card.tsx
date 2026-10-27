"use client";

import { useState } from "react";
import { Check, Loader2, Pause, Pencil, Play, X } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import {
  DSButton,
  DSCard,
  DSIconButton,
  DSInput,
  DSModal,
} from "@/components/ds";
import { useToast } from "@/components/ui/toast";
import {
  errorText,
  pauseDownload,
  removeDownload,
  resumeDownload,
  updateDownload,
  type Download,
  type DownloadKind,
} from "@/lib/api";
import { formatBytes, formatDuration, serverDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import {
  destinationTopic,
  hasSeason,
  KindPicker,
  NAME_MAX,
  SEASON_MAX,
  seasonValue,
} from "./add-torrent-card";

const BADGE: Record<DownloadKind, string> = {
  film: "bg-[#1e3a5f] text-[#93c5fd]",
  series: "bg-[#3b2a52] text-[#d8b4fe]",
  anime: "bg-[#5a2440] text-[#f9a8d4]",
  concert: "bg-[#1f4a3a] text-[#86efac]",
};

// qBittorrent's "never"
const NO_ETA = 8640000;

/** "~26 min", "~2h 5m"; nothing when unknown */
function eta(seconds: number | null | undefined) {
  if (seconds == null || seconds < 0 || seconds >= NO_ETA) return null;
  return seconds < 3600
    ? `~${Math.max(1, Math.round(seconds / 60))} min`
    : `~${formatDuration(seconds)}`;
}

function Bar({ value, className }: { value: number; className: string }) {
  return (
    <div className="h-1.5 rounded-full bg-[#27272a] overflow-hidden">
      <div
        className={cn(
          "h-full rounded-full transition-[width] duration-500",
          className,
        )}
        style={{ width: `${Math.min(100, Math.max(0, value * 100))}%` }}
      />
    </div>
  );
}

const Stats = ({ items }: { items: (React.ReactNode | false | null)[] }) => (
  <span className="text-xs text-[#a1a1aa]">
    {items.filter(Boolean).map((item, i) => (
      <span key={i}>
        {i > 0 && " · "}
        {item}
      </span>
    ))}
  </span>
);

export function TorrentCard({
  download: d,
  onChanged,
}: {
  download: Download;
  onChanged: () => void;
}) {
  const t = useTranslations("downloads");
  const tc = useTranslations("common");
  const locale = useLocale();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const size = (bytes: number) => formatBytes(bytes, locale);
  const percent = (value: number) =>
    new Intl.NumberFormat(locale, {
      style: "percent",
      maximumFractionDigits: 0,
    }).format(value);

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await action();
      onChanged();
    } catch (e) {
      toast(errorText(e, tc("actionFailed")), "error");
    } finally {
      setBusy(false);
    }
  };

  const active =
    d.status === "queued" ||
    d.status === "downloading" ||
    d.status === "uploading";
  const inLibrary = d.status === "library";
  // A film's topic is the films topic's id
  const topics = d.topics.length
    ? d.topics.map((topic) =>
        typeof topic === "number" ? "Movie Archive" : topic,
      )
    : [destinationTopic(d.kind, d.name ?? "", d.season)];
  const totalSize =
    d.files.reduce((sum, f) => sum + f.size, 0) || d.live?.size || 0;
  const uploaded = d.files.filter((f) => f.uploaded).length;
  const live = d.live;
  const up = d.upload;
  const onTelegram =
    d.files.length > 0 &&
    t("onTelegram", { done: uploaded, total: d.files.length });
  // The agent goes on trying these: the download isn't over
  const failing = d.files.filter((f) => f.error && !f.uploaded);

  return (
    <>
      <DSCard
        level="secondary"
        className={cn(
          "p-4 gap-2 shadow-none backdrop-blur-none",
          inLibrary && "opacity-80",
        )}
      >
        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
          <div className="flex items-start gap-2 min-w-0 flex-1 basis-60">
            <span
              className={cn(
                "shrink-0 mt-0.5 px-2 py-0.5 rounded-full text-[11px] font-medium",
                BADGE[d.kind],
              )}
            >
              {t(`kinds.${d.kind}`)}
            </span>
            <span className="text-sm font-semibold text-[#fafafa] wrap-anywhere">
              {d.torrent_name ?? d.name ?? t("resolving")}
            </span>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            {inLibrary && (
              <span className="flex items-center gap-1 text-xs text-green-300 mr-1">
                <Check className="w-3.5 h-3.5" />
                {t("library")}
              </span>
            )}
            {active && (
              <DSButton
                variant="secondary"
                className="h-8 px-3 text-xs"
                disabled={busy}
                onClick={() =>
                  void run(() =>
                    d.paused ? resumeDownload(d.id) : pauseDownload(d.id),
                  )
                }
                icon={
                  d.paused ? (
                    <Play className="w-3.5 h-3.5" />
                  ) : (
                    <Pause className="w-3.5 h-3.5" />
                  )
                }
              >
                {t(d.paused ? "resume" : "pause")}
              </DSButton>
            )}
            <DSButton
              variant="secondary"
              className="h-8 px-3 text-xs"
              onClick={() => setEditing(true)}
              icon={<Pencil className="w-3.5 h-3.5" />}
            >
              {t("edit")}
            </DSButton>
            {d.status !== "removing" && !inLibrary && (
              <DSIconButton
                aria-label={t("remove")}
                title={t("remove")}
                disabled={busy}
                className="bg-[#27272a] text-[#e4e4e7] hover:bg-[#3f3f46] hover:text-red-400"
                onClick={() => {
                  if (confirm(t("removeConfirm")))
                    void run(() => removeDownload(d.id));
                }}
                icon={
                  busy ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <X className="w-4 h-4" />
                  )
                }
              />
            )}
          </div>
        </div>

        <p className="text-xs text-[#71717a] wrap-anywhere">
          →{" "}
          {[
            topics.filter(Boolean).join(" · "),
            d.files.length > 0 && t("files", { n: d.files.length }),
            totalSize > 0 && size(totalSize),
            d.finished_at &&
              t("finishedAt", {
                time: serverDate(d.finished_at).toLocaleString(locale, {
                  day: "2-digit",
                  month: "2-digit",
                  hour: "2-digit",
                  minute: "2-digit",
                }),
              }),
          ]
            .filter(Boolean)
            .join(" · ")}
        </p>

        {d.error && (
          <p className="text-xs text-red-400 wrap-anywhere">
            {tc("error")}: {d.error}
          </p>
        )}

        {failing.length > 0 && (
          <p className="text-xs text-amber-400 wrap-anywhere">
            {t("fileError", {
              file: failing[0].path.split("/").pop() ?? "",
              error: failing[0].error ?? "",
              more: failing.length - 1,
            })}
          </p>
        )}

        {active && (
          <div className="flex flex-col gap-1 mt-1">
            <Bar value={live?.progress ?? 0} className="bg-plex-orange" />
            {up && <Bar value={up.percent / 100} className="bg-sky-400" />}
            <div className="flex flex-wrap justify-between gap-x-4 gap-y-1 mt-1">
              <div className="flex flex-col gap-0.5">
                {(!up || (live && live.progress < 1)) && (
                  <Stats
                    items={
                      d.status === "queued" && !live
                        ? [d.paused ? t("paused") : t("queued")]
                        : [
                            <b
                              key="dl"
                              className="font-semibold text-plex-orange"
                            >
                              {d.paused ? t("paused") : t("download")}{" "}
                              {percent(live?.progress ?? 0)}
                            </b>,
                            !d.paused &&
                              live &&
                              live.progress < 1 &&
                              `↓ ${size(live.dlspeed)}/s`,
                            !d.paused &&
                              live &&
                              live.progress < 1 &&
                              t("peers", {
                                peers: live.num_peers,
                                seeds: live.num_seeds,
                              }),
                            !d.paused &&
                              live &&
                              live.progress < 1 &&
                              eta(live.eta),
                          ]
                    }
                  />
                )}
                {up && (
                  <Stats
                    items={[
                      <b key="up" className="font-semibold text-sky-400">
                        {t("upload")} {percent(up.percent / 100)}
                      </b>,
                      up.parts > 1 &&
                        t("part", { part: up.part, parts: up.parts }),
                      `${size(up.speed)}/s`,
                      eta(up.eta),
                    ]}
                  />
                )}
              </div>
              {onTelegram && (
                <span className="text-xs text-[#a1a1aa]">{onTelegram}</span>
              )}
            </div>
          </div>
        )}

        {(d.status === "scanning" || d.status === "removing") && (
          <div className="flex flex-wrap justify-between gap-x-4 text-xs text-[#a1a1aa]">
            <span className="flex items-center gap-1.5">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              {t(d.status)}
            </span>
            {onTelegram && <span>{onTelegram}</span>}
          </div>
        )}
      </DSCard>
      {/* Beside the card: the library card's opacity must not reach the modal */}
      {editing && (
        <EditDownloadModal
          download={d}
          onClose={() => setEditing(false)}
          onSaved={onChanged}
        />
      )}
    </>
  );
}

function EditDownloadModal({
  download: d,
  onClose,
  onSaved,
}: {
  download: Download;
  onClose: () => void;
  onSaved: () => void;
}) {
  const t = useTranslations("downloads");
  const tc = useTranslations("common");
  const toast = useToast();
  const [kind, setKind] = useState(d.kind);
  const [name, setName] = useState(d.name ?? "");
  const [season, setSeason] = useState(
    d.season === null ? "" : String(d.season),
  );
  const [saving, setSaving] = useState(false);
  const topic = destinationTopic(
    kind,
    name.trim(),
    hasSeason(kind) ? seasonValue(season) : null,
  );
  const moves = d.files.some((f) => f.uploaded);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await updateDownload(d.id, {
        kind,
        name: name.trim() || null,
        season: hasSeason(kind) ? seasonValue(season) : null,
      });
      onSaved();
      onClose();
    } catch (err) {
      toast(errorText(err, tc("actionFailed")), "error");
      setSaving(false);
    }
  };

  return (
    <DSModal onClose={onClose} aria-label={t("editTitle")}>
      <div className="flex justify-between items-start mb-5">
        <h2 className="text-xl font-semibold text-white">{t("editTitle")}</h2>
        <DSIconButton
          data-modal-close
          aria-label={tc("close")}
          className="hover:text-white text-white/50"
          icon={<X className="h-5 w-5" />}
        />
      </div>
      <form onSubmit={save} className="flex flex-col gap-4">
        <KindPicker value={kind} onChange={setKind} />
        <DSInput
          label={t("name")}
          value={name}
          maxLength={NAME_MAX}
          onChange={(e) => setName(e.target.value)}
          data-autofocus
        />
        {hasSeason(kind) && (
          <DSInput
            label={t("season")}
            type="number"
            min={0}
            max={SEASON_MAX}
            placeholder="1"
            value={season}
            onChange={(e) => setSeason(e.target.value)}
          />
        )}
        <p className="text-xs text-[#71717a]">
          {topic
            ? t.rich("topic", {
                topic,
                b: (chunks) => (
                  <b className="font-semibold text-[#d4d4d8]">{chunks}</b>
                ),
              })
            : t("nameNeeded")}
          {moves && topic && <> · {t("moveHint")}</>}
        </p>
        <div className="flex items-center justify-end gap-3 pt-1">
          <DSButton type="button" variant="ghost" data-modal-close>
            {tc("cancel")}
          </DSButton>
          <DSButton
            type="submit"
            disabled={saving || !topic}
            icon={
              saving ? <Loader2 className="w-4 h-4 animate-spin" /> : undefined
            }
          >
            {t("save")}
          </DSButton>
        </div>
      </form>
    </DSModal>
  );
}
