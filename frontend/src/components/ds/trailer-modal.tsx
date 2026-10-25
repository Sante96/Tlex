"use client";

import { motion } from "framer-motion";
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
      <motion.div
        className="relative w-full aspect-video rounded-2xl overflow-hidden shadow-2xl"
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
      >
        <DSIconButton
          onClick={onClose}
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
      </motion.div>
    </DSModal>
  );
}
