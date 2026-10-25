"use client";

import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { DSIconButton } from "./icon-button";
import { DSModal } from "./modal";

interface TrailerModalProps {
  youtubeKey: string;
  onClose: () => void;
}

export function TrailerModal({ youtubeKey, onClose }: TrailerModalProps) {
  const t = useTranslations();
  return (
    <DSModal onClose={onClose} bare className="max-w-3xl" aria-label="Trailer">
      <div className="relative w-full aspect-video rounded-2xl overflow-hidden shadow-2xl">
        <DSIconButton
          data-modal-close
          aria-label={t("common.close")}
          className="absolute top-3 right-3 z-10 rounded-full bg-black/60 text-white/80 hover:text-white"
          icon={<X className="h-4 w-4" />}
        />
        <iframe
          src={`https://www.youtube.com/embed/${youtubeKey}?autoplay=1&rel=0`}
          title="Trailer"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
          className="w-full h-full"
        />
      </div>
    </DSModal>
  );
}
