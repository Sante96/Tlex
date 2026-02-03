"use client";

import { useState } from "react";
import { Trash2, X } from "lucide-react";
import { ProfileAvatar, PROFILE_AVATARS } from "@/components/ui/profile-avatar";
import { useProfile } from "@/contexts/profile-context";
import { deleteProfile, type Profile } from "@/lib/api";

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
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [error, setError] = useState("");

  const handleDelete = async () => {
    setIsDeleting(true);
    setError("");

    try {
      await deleteProfile(profile.id);
      await refreshProfiles();
      onClose();
    } catch (err) {
      setError("Errore nell'eliminazione del profilo");
      console.error(err);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-zinc-900 rounded-xl p-6 max-w-sm w-full border border-zinc-800">
        <div className="flex justify-between items-start mb-6">
          <h2 className="text-xl font-semibold text-white">Modifica profilo</h2>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-white transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex flex-col items-center mb-6">
          <ProfileAvatar
            src={profile.avatar_url || PROFILE_AVATARS[0].src}
            name={profile.name}
            size="xl"
          />
          <p className="text-white text-lg mt-3">{profile.name}</p>
          {profile.is_kids && (
            <span className="text-xs text-blue-400 mt-1">KIDS</span>
          )}
        </div>

        {error && (
          <p className="text-red-500 text-sm mb-4 text-center">{error}</p>
        )}

        {showDeleteConfirm ? (
          <div className="space-y-3">
            <p className="text-zinc-300 text-center text-sm">
              Sei sicuro di voler eliminare questo profilo? Questa azione non
              può essere annullata.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="flex-1 px-4 py-2 rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition-colors"
                disabled={isDeleting}
              >
                Annulla
              </button>
              <button
                onClick={handleDelete}
                disabled={isDeleting}
                className="flex-1 px-4 py-2 rounded-lg bg-red-600 text-white font-medium hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {isDeleting ? "Eliminazione..." : "Elimina"}
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {canDelete && (
              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-zinc-800 text-red-400 hover:bg-zinc-700 hover:text-red-300 transition-colors"
              >
                <Trash2 className="h-4 w-4" />
                Elimina profilo
              </button>
            )}
            <button
              onClick={onClose}
              className="w-full px-4 py-3 rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition-colors"
            >
              Chiudi
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
