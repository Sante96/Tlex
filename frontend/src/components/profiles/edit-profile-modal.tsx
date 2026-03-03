"use client";

import { useState, type FormEvent } from "react";
import { Trash2, X, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { ProfileAvatar, PROFILE_AVATARS } from "@/components/ui/profile-avatar";
import { useProfile } from "@/contexts/profile-context";
import { deleteProfile, updateProfile, type Profile } from "@/lib/api";

interface EditProfileModalProps {
  profile: Profile;
  onClose: () => void;
  canDelete: boolean;
}

export function EditProfileModal({
  profile,
  onClose,
  canDelete,
}: EditProfileModalProps) {
  const { refreshProfiles } = useProfile();

  const [name, setName] = useState(profile.name);
  const [selectedAvatar, setSelectedAvatar] = useState(
    profile.avatar_url || PROFILE_AVATARS[0].src,
  );
  const [isKids, setIsKids] = useState(profile.is_kids);

  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [error, setError] = useState("");
  const t = useTranslations();

  const handleSave = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!name.trim()) return;
    setIsSaving(true);
    setError("");
    try {
      await updateProfile(profile.id, {
        name: name.trim(),
        avatar_url: selectedAvatar,
        is_kids: isKids,
      });
      await refreshProfiles();
      onClose();
    } catch {
      setError(t("common.error"));
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    setError("");
    try {
      await deleteProfile(profile.id);
      await refreshProfiles();
      onClose();
    } catch {
      setError(t("common.error"));
    } finally {
      setIsDeleting(false);
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
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-semibold text-white">{t("profiles.edit.title")}</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/10 transition-colors text-white/50 hover:text-white"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {showDeleteConfirm ? (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col items-center gap-2 py-2">
              <ProfileAvatar src={selectedAvatar} name={name} size="lg" />
              <p className="text-[#a1a1aa] text-sm text-center mt-2">
                {t("profiles.edit.deleteConfirm")}{" "}
                <span className="text-white font-medium">{profile.name}</span>?{" "}
                {t("profiles.edit.deleteWarning")}
              </p>
            </div>
            {error && (
              <p className="text-red-400 text-sm text-center">{error}</p>
            )}
            <div className="flex gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                disabled={isDeleting}
                className="flex-1 h-10 rounded-lg text-sm font-medium text-white/70 hover:bg-white/[0.08] transition-colors border border-white/10"
              >
                {t("common.cancel")}
              </button>
              <button
                onClick={handleDelete}
                disabled={isDeleting}
                className="flex-1 h-10 rounded-lg bg-red-500/90 hover:bg-red-500 text-white text-sm font-semibold transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {isDeleting && <Loader2 className="w-4 h-4 animate-spin" />}
                {isDeleting ? t("profiles.edit.deleting") : t("common.delete")}
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSave} className="flex flex-col gap-5">
            {/* Avatar picker */}
            <div>
              <label className="block text-sm text-white/70 mb-3">{t("profiles.edit.avatar")}</label>
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

            {/* Name */}
            <div className="flex flex-col gap-1.5">
              <label className="text-sm text-white/70">{t("profiles.edit.name")}</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="h-10 px-3 rounded-lg bg-white/5 border border-white/10 text-white text-sm placeholder:text-white/25 focus:outline-none focus:border-[#e5a00d] transition-colors"
                maxLength={20}
                required
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
                <span className="text-sm text-white">{t("profiles.edit.kidsProfile")}</span>
                <p className="text-xs text-[#71717a]">
                  {t("profiles.edit.kidsDescription")}
                </p>
              </div>
            </label>

            {error && (
              <p className="text-red-400 text-sm text-center">{error}</p>
            )}

            {/* Actions */}
            <div className="flex gap-3 pt-1">
              {canDelete && (
                <button
                  type="button"
                  onClick={() => setShowDeleteConfirm(true)}
                  className="h-10 w-10 flex items-center justify-center rounded-lg text-red-400 hover:bg-red-500/10 hover:text-red-300 transition-colors border border-red-500/20 shrink-0"
                  title={t("profiles.edit.deleteTitle")}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
              <button
                type="button"
                onClick={onClose}
                className="flex-1 h-10 rounded-lg text-sm font-medium text-white/70 hover:bg-white/[0.08] transition-colors border border-white/10"
              >
                {t("common.cancel")}
              </button>
              <button
                type="submit"
                disabled={isSaving || !name.trim()}
                className="flex-1 h-10 rounded-lg bg-[#e5a00d] hover:bg-[#f0b429] text-black text-sm font-semibold transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {isSaving && <Loader2 className="w-4 h-4 animate-spin" />}
                {isSaving ? t("profiles.edit.saving") : t("profiles.edit.save")}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
