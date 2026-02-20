/* ── Tab: Image Picker (Locandina / Sfondo) ───────────────────── */
import Image from "next/image";
import { Image as ImageIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { type TMDBImage } from "@/lib/api";
import { getTmdbImageUrl } from "@/lib/format";

interface ImagePickerTabProps {
  label: string;
  images: TMDBImage[];
  selected: string;
  onSelect: (path: string) => void;
  loading: boolean;
  aspect: "still" | "backdrop" | "poster";
}

export function ImagePickerTab({
  label,
  images,
  selected,
  onSelect,
  loading,
  aspect,
}: ImagePickerTabProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="w-6 h-6 border-2 border-[#e5a00d] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (images.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-[#71717a]">
        <ImageIcon className="h-10 w-10 mb-3 opacity-50" />
        <p className="text-sm">Nessuna immagine disponibile da TMDB</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-[#a1a1aa]">
        Seleziona una {label.toLowerCase()} dalle immagini disponibili su TMDB
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
                  ? "ring-2 ring-[#e5a00d] ring-offset-2 ring-offset-[#18181b]"
                  : "hover:ring-1 hover:ring-white/30 opacity-70 hover:opacity-100",
              )}
            >
              {url && (
                <Image src={url} alt={label} fill className="object-cover" />
              )}
              {isSelected && (
                <div className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-[#e5a00d] flex items-center justify-center">
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
