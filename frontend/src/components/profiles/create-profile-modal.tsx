"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { DSButton, DSInput, DSModal } from "@/components/ds";
import { afterOverlayClose } from "@/hooks/use-back-to-close";
import { AvatarChoices, PROFILE_AVATARS } from "@/components/ui/profile-avatar";
import { useProfile } from "@/contexts/profile-context";

interface CreateProfileModalProps {
  onClose: () => void;
}

export function CreateProfileModal({ onClose }: CreateProfileModalProps) {
  const router = useRouter();
  const { createNewProfile } = useProfile();

  const [name, setName] = useState("");
  const [selectedAvatar, setSelectedAvatar] = useState<string>(
    PROFILE_AVATARS[0].src,
  );
  const [isKids, setIsKids] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const t = useTranslations();

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!name.trim()) {
      setError(t("profiles.create.namePlaceholder"));
      return;
    }

    setIsSubmitting(true);
    setError("");

    try {
      await createNewProfile(name.trim(), selectedAvatar, isKids);
      onClose();
      afterOverlayClose(() => router.push("/"));
    } catch {
      setError(t("common.error"));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <DSModal onClose={onClose} aria-label={t("profiles.create.title")}>
      <h2 className="text-xl font-semibold text-white mb-6">
        {t("profiles.create.title")}
      </h2>

      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        {/* Avatar Selection */}
        <div>
          <label className="block text-sm text-white/70 mb-3">
            {t("profiles.create.chooseAvatar")}
          </label>
          <AvatarChoices selected={selectedAvatar} onSelect={setSelectedAvatar} />
        </div>

        <DSInput
          label={t("profiles.create.nameLabel")}
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t("profiles.create.namePlaceholder")}
          maxLength={20}
          data-autofocus
        />

        {/* Kids toggle */}
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={isKids}
            onChange={(e) => setIsKids(e.target.checked)}
            className="w-5 h-5 shrink-0 accent-plex-orange cursor-pointer [color-scheme:dark]"
          />
          <div>
            <span className="text-sm text-white">
              {t("profiles.create.kidsProfile")}
            </span>
            <p className="text-xs text-[#71717a]">
              {t("profiles.create.kidsDescription")}
            </p>
          </div>
        </label>

        {error && <p className="text-red-400 text-sm text-center">{error}</p>}

        {/* Actions */}
        <div className="flex gap-3 pt-1">
          <DSButton
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={isSubmitting}
            className="flex-1"
          >
            {t("common.cancel")}
          </DSButton>
          <DSButton
            type="submit"
            disabled={isSubmitting || !name.trim()}
            className="flex-1"
          >
            {isSubmitting
              ? t("profiles.create.loading")
              : t("profiles.create.submit")}
          </DSButton>
        </div>
      </form>
    </DSModal>
  );
}
