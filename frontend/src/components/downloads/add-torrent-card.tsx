"use client";

import { useRef, useState } from "react";
import { isAxiosError } from "axios";
import { FileUp, Loader2, Plus, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { DSButton, DSCard, DSIconButton, DSInput } from "@/components/ds";
import { useToast } from "@/components/ui/toast";
import {
  addDownload,
  errorText,
  previewTorrent,
  type DownloadKind,
} from "@/lib/api";
import { cn } from "@/lib/utils";

export const KINDS: DownloadKind[] = ["film", "series", "anime", "concert"];

/** Series and anime go to one topic per season */
export const hasSeason = (kind: DownloadKind) =>
  kind === "series" || kind === "anime";

/** The topic the files go to: the backend's rule (plan.destination_topic) */
export function destinationTopic(
  kind: DownloadKind,
  name: string,
  season: number | null,
) {
  if (kind === "film") return "Movie Archive";
  if (!name) return null;
  if (kind === "concert") return `Concerti · ${name}`;
  return `${name} - Stagione ${season ?? 1}`;
}

/** A season field's text as the API wants it */
export const seasonValue = (text: string) =>
  text.trim() === "" ? null : Number(text);

export function KindPicker({
  value,
  onChange,
}: {
  value: DownloadKind;
  onChange: (kind: DownloadKind) => void;
}) {
  const t = useTranslations("downloads");
  return (
    <div
      role="radiogroup"
      aria-label={t("kind")}
      className="inline-flex gap-0.5 p-[3px] rounded-[10px] bg-[#27272a]"
    >
      {KINDS.map((kind) => (
        <button
          key={kind}
          type="button"
          role="radio"
          aria-checked={value === kind}
          onClick={() => onChange(kind)}
          className={cn(
            "h-8 px-3 rounded-lg text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-plex-orange",
            value === kind
              ? "bg-plex-orange text-black font-semibold"
              : "text-[#a1a1aa] hover:text-white",
          )}
        >
          {t(`kinds.${kind}`)}
        </button>
      ))}
    </div>
  );
}

export function AddTorrentCard({ onAdded }: { onAdded: () => void }) {
  const t = useTranslations("downloads");
  const toast = useToast();
  const [magnet, setMagnet] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [kind, setKind] = useState<DownloadKind>("film");
  const [name, setName] = useState("");
  const [season, setSeason] = useState("");
  const [dragging, setDragging] = useState(false);
  const [adding, setAdding] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  // Only the latest source's preview fills the form
  const previewId = useRef(0);

  const preview = async (input: { magnet?: string; torrent?: File }) => {
    const id = ++previewId.current;
    try {
      const found = await previewTorrent(input);
      if (id !== previewId.current) return;
      if (found.name) setName(found.name);
      if (found.season !== null) setSeason(String(found.season));
    } catch {
      // No preview: the fields stay as they are, the add says what is wrong
    }
  };

  const pickFile = (picked: File | undefined) => {
    if (!picked) return;
    setFile(picked);
    void preview({ torrent: picked });
  };

  const topic = destinationTopic(
    kind,
    name.trim(),
    hasSeason(kind) ? seasonValue(season) : null,
  );
  const ready =
    (!!magnet.trim() || !!file) &&
    (kind === "film" || !!name.trim()) &&
    !adding;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ready) return;
    setAdding(true);
    try {
      await addDownload({
        ...(file ? { torrent: file } : { magnet: magnet.trim() }),
        kind,
        name: name.trim() || undefined,
        season: hasSeason(kind)
          ? (seasonValue(season) ?? undefined)
          : undefined,
      });
      setMagnet("");
      setFile(null);
      setName("");
      setSeason("");
      onAdded();
    } catch (err) {
      toast(
        isAxiosError(err) && err.response?.status === 409
          ? t("alreadyAdded")
          : errorText(err, t("addFailed")),
        "error",
      );
    } finally {
      setAdding(false);
    }
  };

  return (
    <DSCard level="secondary" className="p-4 gap-3 shadow-none">
      <form onSubmit={submit} className="flex flex-col gap-3">
        {/* The whole field takes a dropped .torrent */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            pickFile(e.dataTransfer.files[0]);
          }}
          className={cn("rounded-lg", dragging && "ring-2 ring-plex-orange")}
        >
          {file ? (
            <div className="flex items-center gap-2 h-10 rounded-lg bg-[#18181b] border border-[#3f3f46] pl-3 pr-1 text-sm text-[#fafafa]">
              <FileUp className="w-4 h-4 shrink-0 text-plex-orange" />
              <span className="flex-1 min-w-0 truncate">{file.name}</span>
              <DSIconButton
                type="button"
                aria-label={t("clearFile")}
                title={t("clearFile")}
                onClick={() => setFile(null)}
                icon={<X className="w-4 h-4" />}
              />
            </div>
          ) : (
            <DSInput
              aria-label={t("magnet")}
              placeholder={t("magnetPlaceholder")}
              value={magnet}
              onChange={(e) => {
                setMagnet(e.target.value);
                if (e.target.value.trim().startsWith("magnet:"))
                  void preview({ magnet: e.target.value.trim() });
              }}
              suffix={
                <button
                  type="button"
                  aria-label={t("chooseFile")}
                  title={t("chooseFile")}
                  onClick={() => fileInput.current?.click()}
                  className="text-[#71717a] hover:text-[#fafafa] transition-colors"
                >
                  <FileUp className="h-4 w-4" />
                </button>
              }
            />
          )}
          <input
            ref={fileInput}
            type="file"
            accept=".torrent,application/x-bittorrent"
            hidden
            onChange={(e) => {
              pickFile(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <KindPicker value={kind} onChange={setKind} />
          <DSInput
            aria-label={t("name")}
            placeholder={t(kind === "film" ? "nameOptional" : "name")}
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="flex-1 min-w-[180px]"
          />
          {hasSeason(kind) && (
            <DSInput
              aria-label={t("season")}
              placeholder={t("season")}
              type="number"
              min={0}
              value={season}
              onChange={(e) => setSeason(e.target.value)}
              className="w-[110px]"
            />
          )}
          <DSButton
            type="submit"
            disabled={!ready}
            icon={
              adding ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Plus className="w-4 h-4" />
              )
            }
          >
            {t("add")}
          </DSButton>
        </div>

        <p className="text-xs text-[#71717a]">
          {topic ? (
            <>
              {t.rich("topic", {
                topic,
                b: (chunks) => (
                  <b className="font-semibold text-[#d4d4d8]">{chunks}</b>
                ),
              })}{" "}
              · {t("topicHint")}
            </>
          ) : (
            t("nameNeeded")
          )}
        </p>
      </form>
    </DSCard>
  );
}
