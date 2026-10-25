"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { DSButton, DSModal } from "@/components/ds";
import { AvatarChoices } from "./profile-avatar";

interface AvatarPickerProps {
  currentAvatar?: string;
  onSelect: (avatarSrc: string) => void;
  onClose: () => void;
}

export function AvatarPicker({
  currentAvatar,
  onSelect,
  onClose,
}: AvatarPickerProps) {
  const [selected, setSelected] = useState<string | undefined>(currentAvatar);
  const t = useTranslations();

  const handleSelect = (src: string) => {
    setSelected(src);
  };

  const handleConfirm = () => {
    if (selected) {
      onSelect(selected);
    }
    onClose();
  };

  return (
    <DSModal
      onClose={onClose}
      className="relative max-h-[90vh] overflow-y-auto"
      aria-label={t("profiles.avatar.title")}
    >
      <button
        data-modal-close
        aria-label={t("common.close")}
        className="absolute top-4 right-4 text-white/30 hover:text-white transition-colors z-10"
      >
        <X className="h-5 w-5" />
      </button>

      <h2 className="text-lg font-semibold text-white mb-5">
        {t("profiles.avatar.title")}
      </h2>

      <AvatarChoices
        selected={selected}
        onSelect={handleSelect}
        size="lg"
        className="grid-cols-3 sm:grid-cols-3 gap-4 mb-6"
      />

      <div className="flex gap-3">
        <DSButton variant="ghost" data-modal-close className="flex-1">
          {t("common.cancel")}
        </DSButton>
        <DSButton
          onClick={handleConfirm}
          disabled={!selected}
          className="flex-1"
        >
          {t("common.confirm")}
        </DSButton>
      </div>
    </DSModal>
  );
}
