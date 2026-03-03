"use client";

import { useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { ProfileAvatar, PROFILE_AVATARS } from "./profile-avatar";
import { cn } from "@/lib/utils";

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

  // Don't render on server
  if (typeof window === "undefined") {
    return null;
  }

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div
        className="relative rounded-2xl p-6 max-w-md w-full max-h-[90vh] overflow-y-auto shadow-[0_24px_48px_rgba(0,0,0,0.6)]"
        style={{
          backgroundColor: "rgba(10,10,10,0.88)",
          backdropFilter: "blur(24px)",
          border: "1px solid rgba(255,255,255,0.07)",
        }}
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-white/30 hover:text-white transition-colors z-10"
        >
          <X className="h-5 w-5" />
        </button>

        <h2 className="text-lg font-semibold text-white mb-5">
          {t("profiles.avatar.title")}
        </h2>

        <div className="grid grid-cols-3 gap-4 mb-6">
          {PROFILE_AVATARS.map((avatar) => (
            <div key={avatar.id} className="flex justify-center">
              <ProfileAvatar
                src={avatar.src}
                name={avatar.name}
                size="lg"
                selected={selected === avatar.src}
                onClick={() => handleSelect(avatar.src)}
              />
            </div>
          ))}
        </div>

        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 h-10 rounded-lg text-sm font-medium text-white/70 hover:bg-white/[0.08] transition-colors border border-white/10"
          >
            {t("common.cancel")}
          </button>
          <button
            onClick={handleConfirm}
            disabled={!selected}
            className={cn(
              "flex-1 h-10 rounded-lg text-sm font-semibold transition-colors",
              selected
                ? "bg-[#e5a00d] text-black hover:bg-[#f0b429]"
                : "bg-white/5 text-white/25 cursor-not-allowed border border-white/10",
            )}
          >
            {t("common.confirm")}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
