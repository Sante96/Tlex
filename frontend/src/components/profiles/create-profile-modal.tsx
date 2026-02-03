"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!name.trim()) {
      setError("Inserisci un nome per il profilo");
      return;
    }

    setIsSubmitting(true);
    setError("");

    try {
      await createNewProfile(name.trim(), selectedAvatar, isKids);
      router.push("/");
    } catch (err) {
      setError("Errore nella creazione del profilo");
      console.error(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
      <div className="bg-zinc-900 rounded-xl p-8 max-w-lg w-full mx-4 border border-zinc-800">
        <h2 className="text-2xl font-semibold text-white mb-6">
          Crea nuovo profilo
        </h2>

        <form onSubmit={handleSubmit}>
          {/* Avatar Selection */}
          <div className="mb-6">
            <label className="block text-sm text-zinc-400 mb-3">
              Scegli un avatar
            </label>
            <div className="grid grid-cols-5 gap-3">
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
          <div className="mb-6">
            <label className="block text-sm text-zinc-400 mb-2">
              Nome del profilo
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Es. Mario"
              className="w-full px-4 py-3 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-plex-orange"
              maxLength={20}
              autoFocus
            />
          </div>

          {/* Kids Profile Toggle */}
          <div className="mb-6">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={isKids}
                onChange={(e) => setIsKids(e.target.checked)}
                className="w-5 h-5 rounded border-zinc-600 bg-zinc-800 text-plex-orange focus:ring-plex-orange"
              />
              <span className="text-white">Profilo per bambini</span>
            </label>
            <p className="text-sm text-zinc-500 mt-1 ml-8">
              Mostra solo contenuti adatti ai minori
            </p>
          </div>

          {error && <p className="text-red-500 text-sm mb-4">{error}</p>}

          {/* Actions */}
          <div className="flex gap-3">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-3 rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition-colors"
              disabled={isSubmitting}
            >
              Annulla
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !name.trim()}
              className="flex-1 px-4 py-3 rounded-lg bg-plex-orange text-black font-medium hover:bg-plex-orange/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? "Creazione..." : "Crea profilo"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
