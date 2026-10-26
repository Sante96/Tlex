/* ── Tab: Image Picker (Locandina / Sfondo) ───────────────────── */
"use client";

import { useRef, useState } from "react";
import { useTranslations } from "next-intl";
import Image from "next/image";
import { Image as ImageIcon, Upload } from "lucide-react";
import { cn } from "@/lib/utils";
import { errorText, imageFromUrl, uploadImage, type TMDBImage } from "@/lib/api";
import { getTmdbImageUrl } from "@/lib/format";
import { DSButton } from "@/components/ds/button";
import { DSInput } from "@/components/ds/input";
import { useToast } from "@/components/ui/toast";

interface ImagePickerTabProps {
  label: string;
  images: TMDBImage[];
  selected: string;
  onSelect: (path: string) => void;
  loading: boolean;
  aspect: "still" | "backdrop" | "poster";
  /** Concerts and their franchises: TMDB rarely has them, so a pasted link or a file */
  allowCustom?: boolean;
}

/** An own image: a pasted link (the backend downloads and keeps it) or a file */
function CustomImageField({
  selected,
  onSelect,
  aspect,
}: {
  selected: string;
  onSelect: (path: string) => void;
  aspect: ImagePickerTabProps["aspect"];
}) {
  const t = useTranslations("editMedia");
  const toast = useToast();
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const use = async (pick: () => Promise<string>) => {
    setBusy(true);
    try {
      onSelect(await pick());
      setUrl("");
    } catch (e) {
      toast(errorText(e, t("imageFailed")), "error");
    }
    setBusy(false);
  };
  const preview = selected.startsWith("local:") ? getTmdbImageUrl(selected) : null;

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-white/10 p-3">
      <div className="flex flex-col sm:flex-row gap-2">
        <DSInput
          type="url"
          value={url}
          placeholder={t("imageUrl")}
          aria-label={t("imageUrl")}
          onChange={(e) => setUrl(e.target.value)}
          className="flex-1"
        />
        <DSButton
          variant="secondary"
          disabled={busy || !url.trim()}
          onClick={() => use(() => imageFromUrl(url.trim()))}
        >
          {t("useUrl")}
        </DSButton>
        <DSButton
          variant="secondary"
          disabled={busy}
          icon={<Upload className="h-4 w-4" />}
          onClick={() => fileRef.current?.click()}
        >
          {t("upload")}
        </DSButton>
        <input
          ref={fileRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = ""; // the same file can be picked again
            if (file) use(() => uploadImage(file));
          }}
        />
      </div>
      {preview && (
        // The tab's shape, at the size of the grid's pictures (a flex child stretched to
        // the full width before: a poster or a backdrop squashed into a strip)
        <div
          className={cn(
            "relative self-start rounded-md overflow-hidden ring-2 ring-plex-orange",
            aspect === "poster" ? "w-28 aspect-2/3" : "w-56 aspect-video",
          )}
        >
          <Image src={preview} alt="" fill className="object-cover" />
        </div>
      )}
    </div>
  );
}

export function ImagePickerTab({
  label,
  images,
  selected,
  onSelect,
  loading,
  aspect,
  allowCustom = false,
}: ImagePickerTabProps) {
  const t = useTranslations("editMedia");
  const custom = allowCustom && (
    <CustomImageField selected={selected} onSelect={onSelect} aspect={aspect} />
  );
  if (loading) {
    return (
      <div className="flex flex-col gap-4">
        {custom}
        <div className="flex items-center justify-center py-16">
          <div className="w-6 h-6 border-2 border-plex-orange border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (images.length === 0) {
    if (custom) return <div className="flex flex-col gap-4">{custom}</div>;
    return (
      <div className="flex flex-col items-center justify-center py-16 text-[#71717a]">
        <ImageIcon className="h-10 w-10 mb-3 opacity-50" />
        <p className="text-sm">{t("noImages")}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {custom}
      <p className="text-sm text-[#a1a1aa]">
        {t("selectImage", { label: label.toLowerCase() })}
      </p>
      <div
        className={cn(
          "grid gap-3",
          aspect === "poster"
            ? "grid-cols-4"
            : aspect === "still"
              ? "grid-cols-3"
              : "grid-cols-2",
        )}
      >
        {images.map((img) => {
          const isSelected = selected === img.file_path;
          const url = getTmdbImageUrl(img.file_path, "w300");
          return (
            <button
              key={img.file_path}
              onClick={() => onSelect(img.file_path)}
              className={cn(
                "relative rounded-lg overflow-hidden transition-all",
                aspect === "poster" ? "aspect-[2/3]" : "aspect-video",
                isSelected
                  ? "ring-2 ring-plex-orange ring-offset-2 ring-offset-[#18181b]"
                  : "hover:ring-1 hover:ring-white/30 opacity-70 hover:opacity-100",
              )}
            >
              {url && (
                <Image src={url} alt={label} fill className="object-cover" />
              )}
              {isSelected && (
                <div className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-plex-orange flex items-center justify-center">
                  <svg
                    className="h-3 w-3 text-black"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={3}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
