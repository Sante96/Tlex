"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Pencil } from "lucide-react";
import { ProfileAvatar, PROFILE_AVATARS } from "@/components/ui/profile-avatar";
import { CreateProfileModal, EditProfileModal } from "@/components/profiles";
import { useProfile } from "@/contexts/profile-context";
import { useAuth } from "@/contexts/auth-context";
import type { Profile } from "@/lib/api";

export default function ProfilesPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { profiles, selectProfile, hasProfiles, isLoading } = useProfile();

  const [isEditing, setIsEditing] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingProfile, setEditingProfile] = useState<Profile | null>(null);

  // Redirect to login if not authenticated
  if (!authLoading && !isAuthenticated) {
    router.replace("/login");
    return null;
  }

  // Show loading state
  if (isLoading || authLoading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="w-12 h-12 border-4 border-plex-orange border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const handleSelectProfile = (profile: Profile) => {
    if (isEditing) {
      setEditingProfile(profile);
      return;
    }
    selectProfile(profile);
    router.push("/");
  };

  const handleCreateProfile = () => {
    setShowCreateModal(true);
  };

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center px-4">
      <h1 className="text-3xl md:text-4xl font-medium text-white mb-2">
        Chi sta guardando?
      </h1>

      {isEditing && (
        <p className="text-zinc-400 mb-8">Seleziona un profilo da modificare</p>
      )}

      <div className="flex flex-wrap justify-center gap-6 mt-8 max-w-3xl">
        {profiles.map((profile) => (
          <div
            key={profile.id}
            className="flex flex-col items-center gap-3 group"
          >
            <div className="relative">
              <ProfileAvatar
                src={profile.avatar_url || PROFILE_AVATARS[0].src}
                name={profile.name}
                size="xl"
                onClick={() => handleSelectProfile(profile)}
                selected={false}
                borderColor={isEditing ? "ring-zinc-500" : "ring-plex-orange"}
              />
              {isEditing && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/50 rounded-full">
                  <Pencil className="w-8 h-8 text-white" />
                </div>
              )}
              {!profile.has_worker && (
                <div className="absolute -bottom-1 -right-1 w-5 h-5 bg-yellow-500 rounded-full flex items-center justify-center">
                  <span className="text-xs font-bold text-black">!</span>
                </div>
              )}
            </div>
            <span className="text-zinc-400 group-hover:text-white transition-colors text-lg">
              {profile.name}
            </span>
            {profile.is_kids && (
              <span className="text-xs text-blue-400 -mt-2">KIDS</span>
            )}
          </div>
        ))}

        {/* Add Profile Button */}
        {profiles.length < 5 && (
          <div className="flex flex-col items-center gap-3">
            <button
              onClick={handleCreateProfile}
              className="w-32 h-32 rounded-full bg-zinc-800 hover:bg-zinc-700 border-2 border-dashed border-zinc-600 hover:border-zinc-500 flex items-center justify-center transition-all"
            >
              <Plus className="w-12 h-12 text-zinc-400" />
            </button>
            <span className="text-zinc-400 text-lg">Aggiungi profilo</span>
          </div>
        )}
      </div>

      {/* Manage Profiles Button */}
      {hasProfiles && (
        <button
          onClick={() => setIsEditing(!isEditing)}
          className="mt-12 px-6 py-2 border border-zinc-600 text-zinc-400 hover:text-white hover:border-white transition-colors"
        >
          {isEditing ? "Fatto" : "Gestisci profili"}
        </button>
      )}

      {/* Create Profile Modal */}
      {showCreateModal && (
        <CreateProfileModal onClose={() => setShowCreateModal(false)} />
      )}

      {/* Edit Profile Modal */}
      {editingProfile && (
        <EditProfileModal
          profile={editingProfile}
          onClose={() => setEditingProfile(null)}
          canDelete={profiles.length > 1}
        />
      )}
    </div>
  );
}
