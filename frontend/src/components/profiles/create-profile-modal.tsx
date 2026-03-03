"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { ProfileAvatar, PROFILE_AVATARS } from "@/components/ui/profile-avatar";
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
      router.push("/");
    } catch {
      setError(t("common.error"));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div
        className="rounded-2xl p-6 max-w-md w-full shadow-[0_24px_48px_rgba(0,0,0,0.6)]"
        style={{
          backgroundColor: "rgba(10,10,10,0.8)",
          backdropFilter: "blur(24px)",
          border: "1px solid rgba(255,255,255,0.07)",
        }}
      >
        <h2 className="text-xl font-semibold text-white mb-6">
          {t("profiles.create.title")}
        </h2>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          {/* Avatar Selection */}
          <div>
            <label className="block text-sm text-white/70 mb-3">
              {t("profiles.create.chooseAvatar")}
            </label>
            <div className="grid grid-cols-5 gap-2">
              {PROFILE_AVATARS.map((avatar) => (
                <ProfileAvatar
                  key={avatar.id}
                  src={avatar.src}
                  name={avatar.name}
                  size="md"
                  selected={selectedAvatar === avatar.src}
                  onClick={() => setSelectedAvatar(avatar.src)}
                />
              ))}
            </div>
          </div>

          {/* Name Input */}
          <div className="flex flex-col gap-1.5">
            <label className="text-sm text-white/70">{t("profiles.create.nameLabel")}</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Es. Mario"
              className="h-10 px-3 rounded-lg bg-white/5 border border-white/10 text-white text-sm placeholder:text-white/25 focus:outline-none focus:border-[#e5a00d] transition-colors"
              maxLength={20}
              autoFocus
            />
          </div>

          {/* Kids toggle */}
          <label className="flex items-center gap-3 cursor-pointer">
            <div
              onClick={() => setIsKids(!isKids)}
              className={`w-5 h-5 rounded flex items-center justify-center transition-colors border ${
                isKids
                  ? "bg-[#e5a00d] border-[#e5a00d]"
                  : "bg-white/5 border-white/20"
              }`}
            >
              {isKids && (
                <span className="text-[10px] font-bold text-black">✓</span>
              )}
            </div>
            <div>
              <span className="text-sm text-white">{t("profiles.create.kidsProfile")}</span>
              <p className="text-xs text-[#71717a]">
                {t("profiles.create.kidsDescription")}
              </p>
            </div>
          </label>

          {error && <p className="text-red-400 text-sm text-center">{error}</p>}

          {/* Actions */}
          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="flex-1 h-10 rounded-lg text-sm font-medium text-white/70 hover:bg-white/[0.08] transition-colors"
              style={{ border: "1px solid rgba(255,255,255,0.1)" }}
            >
              {t("common.cancel")}
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !name.trim()}
              className="flex-1 h-10 rounded-lg bg-[#e5a00d] hover:bg-[#f0b429] text-black text-sm font-semibold transition-colors disabled:opacity-50"
            >
              {isSubmitting ? t("profiles.create.loading") : t("profiles.create.submit")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
