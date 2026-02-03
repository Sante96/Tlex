"use client";

import { useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
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
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="relative bg-zinc-900 rounded-xl p-6 max-w-md w-full border border-zinc-800 max-h-[90vh] overflow-y-auto shadow-2xl">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-zinc-400 hover:text-white transition-colors z-10"
        >
          <X className="h-5 w-5" />
        </button>

        <h2 className="text-xl font-semibold text-white mb-6">
          Scegli il tuo avatar
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
            className="flex-1 px-4 py-2 rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition-colors"
          >
            Annulla
          </button>
          <button
            onClick={handleConfirm}
            disabled={!selected}
            className={cn(
              "flex-1 px-4 py-2 rounded-lg font-medium transition-colors",
              selected
                ? "bg-plex-orange text-black hover:bg-plex-orange/90"
                : "bg-zinc-700 text-zinc-500 cursor-not-allowed",
            )}
          >
            Conferma
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
