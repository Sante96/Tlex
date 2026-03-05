"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Pencil, Check } from "lucide-react";
import { useTranslations } from "next-intl";
import dynamic from "next/dynamic";
import { ProfileAvatar, PROFILE_AVATARS } from "@/components/ui/profile-avatar";
import { TVBackground } from "@/components/ds";
import { CreateProfileModal, EditProfileModal } from "@/components/profiles";
import { useProfile } from "@/contexts/profile-context";
import { useAuth } from "@/contexts/auth-context";
import { useIsTV } from "@/hooks/use-platform";
import type { Profile } from "@/lib/api";
import { assignWorkerToProfile } from "@/lib/api";

const MeshGradient = dynamic(
  () => import("@paper-design/shaders-react").then((m) => ({ default: m.MeshGradient })),
  { ssr: false },
);

export default function ProfilesPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { profiles, selectProfile, hasProfiles, isLoading, refreshProfiles } = useProfile();
  const t = useTranslations();
  const isTV = useIsTV();

  const [isEditing, setIsEditing] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingProfile, setEditingProfile] = useState<Profile | null>(null);
  const [assigningId, setAssigningId] = useState<number | null>(null);

  const handleAssignWorker = async (e: React.MouseEvent, profileId: number) => {
    e.stopPropagation();
    setAssigningId(profileId);
    try {
      await assignWorkerToProfile(profileId);
      await refreshProfiles();
    } catch { /* ignore */ } finally {
      setAssigningId(null);
    }
  };

  React.useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [authLoading, isAuthenticated, router]);

  if (!authLoading && !isAuthenticated) return null;

  if (isLoading || authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#09090b]">
        <div className="w-10 h-10 border-2 border-[#e5a00d] border-t-transparent rounded-full animate-spin" />
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

  if (isTV) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center relative overflow-hidden">
        <TVBackground />

        <div className="relative z-10 flex flex-col items-center gap-12">
          {/* Heading */}
          <div className="text-center">
            <h1 className="text-4xl font-semibold text-white">
              {t("profiles.whoIsWatching")}
            </h1>
          </div>

          {/* Profile grid */}
          <div className="flex flex-wrap justify-center gap-10">
            {profiles.map((profile) => (
              <button
                key={profile.id}
                onClick={() => handleSelectProfile(profile)}
                className="flex flex-col items-center gap-4 group outline-none"
              >
                <div className="relative">
                  <div
                    className="relative w-44 h-44 rounded-full transition-all duration-200 ring-4 ring-transparent focus-visible:ring-[#e5a00d] group-focus-visible:ring-[#e5a00d] group-focus-visible:scale-105 group-focus-visible:ring-offset-4 group-focus-visible:ring-offset-[#09090b]"
                    style={{ "--tw-ring-offset-color": "#09090b" } as React.CSSProperties}
                  >
                    <ProfileAvatar
                      src={profile.avatar_url || PROFILE_AVATARS[0].src}
                      name={profile.name}
                      size="2xl"
                      selected={false}
                    />
                  </div>
                  {!profile.has_worker && (
                    <div
                      onClick={(e) => handleAssignWorker(e, profile.id)}
                      role="button"
                      tabIndex={0}
                      title="Assegna worker"
                      className="absolute -bottom-0.5 -right-0.5 w-6 h-6 bg-yellow-500 hover:bg-yellow-400 rounded-full flex items-center justify-center ring-2 ring-[#09090b] transition-colors cursor-pointer"
                    >
                      <span className="text-xs font-bold text-black">{assigningId === profile.id ? "…" : "!"}</span>
                    </div>
                  )}
                </div>
                <span className="text-lg font-medium text-[#a1a1aa] group-focus-visible:text-white transition-colors">
                  {profile.name}
                  {profile.is_kids && (
                    <span className="ml-2 text-sm font-semibold text-blue-400 uppercase tracking-wider">
                      {t("profiles.kids")}
                    </span>
                  )}
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 relative overflow-hidden">
      {/* Animated background */}
      <div className="fixed inset-0 z-0">
        <MeshGradient
          style={{ width: "100%", height: "100%" }}
          colors={["#09090b", "#1c1500", "#09090b"]}
          distortion={1}
          swirl={0.1}
          grainMixer={0}
          grainOverlay={0}
          speed={0.3}
        />
        <div
          className="absolute inset-0"
          style={{ backgroundColor: "rgba(9,9,11,0.45)" }}
        />
      </div>

      <div className="relative z-10 flex flex-col items-center w-full">
        {/* Heading */}
        <div className="text-center mb-10">
          <h1 className="text-3xl md:text-4xl font-semibold text-white">
            {isEditing
              ? t("profiles.editProfile")
              : t("profiles.whoIsWatching")}
          </h1>
          {isEditing && (
            <p className="text-sm text-[#71717a] mt-2">
              {t("profiles.selectToEdit")}
            </p>
          )}
        </div>

        {/* Profile grid */}
        <div className="flex flex-wrap justify-center gap-5 md:gap-8 max-w-2xl">
          {profiles.map((profile) => (
            <button
              key={profile.id}
              onClick={() => handleSelectProfile(profile)}
              className="flex flex-col items-center gap-3 group outline-none"
            >
              <div className="relative">
                {/* Avatar wrapper with hover ring */}
                <div
                  className={`
                  relative w-32 h-32 rounded-full transition-all duration-200
                  ring-2 ring-transparent group-hover:ring-[#e5a00d] group-hover:ring-offset-2
                  group-hover:scale-105
                  ${isEditing ? "ring-white/20" : ""}
                `}
                  style={
                    {
                      "--tw-ring-offset-color": "#09090b",
                    } as React.CSSProperties
                  }
                >
                  <ProfileAvatar
                    src={profile.avatar_url || PROFILE_AVATARS[0].src}
                    name={profile.name}
                    size="xl"
                    selected={false}
                  />
                  {/* Edit overlay */}
                  {isEditing && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/60 rounded-full">
                      <Pencil className="w-7 h-7 text-white" />
                    </div>
                  )}
                </div>
                {/* Worker warning badge */}
                {!profile.has_worker && (
                  <div
                    onClick={(e) => handleAssignWorker(e, profile.id)}
                    role="button"
                    tabIndex={0}
                    title="Assegna worker"
                    className="absolute -bottom-0.5 -right-0.5 w-5 h-5 bg-yellow-500 hover:bg-yellow-400 rounded-full flex items-center justify-center ring-2 ring-[#09090b] transition-colors cursor-pointer"
                  >
                    <span className="text-[10px] font-bold text-black">{assigningId === profile.id ? "…" : "!"}</span>
                  </div>
                )}
              </div>
              <div className="flex flex-col items-center gap-0.5">
                <span className="text-[#a1a1aa] group-hover:text-white transition-colors text-sm font-medium">
                  {profile.name}
                </span>
                {profile.is_kids && (
                  <span className="text-[10px] font-semibold text-blue-400 tracking-wider uppercase">
                    {t("profiles.kids")}
                  </span>
                )}
              </div>
            </button>
          ))}

          {/* Add profile */}
          {profiles.length < 5 && !isEditing && (
            <button
              onClick={() => setShowCreateModal(true)}
              className="flex flex-col items-center gap-3 group outline-none"
            >
              <div className="w-32 h-32 rounded-full border-2 border-dashed border-white/20 group-hover:border-[#e5a00d]/60 flex items-center justify-center transition-all duration-200 group-hover:scale-105 bg-white/[0.03]">
                <Plus className="w-9 h-9 text-white/30 group-hover:text-[#e5a00d]/70 transition-colors duration-200" />
              </div>
              <span className="text-[#52525b] group-hover:text-[#a1a1aa] transition-colors text-sm font-medium">
                {t("profiles.addProfile")}
              </span>
            </button>
          )}
        </div>

        {/* Manage / Done button */}
        {hasProfiles && (
          <button
            onClick={() => setIsEditing(!isEditing)}
            className={`mt-12 flex items-center gap-2 px-6 py-2 rounded-full text-sm font-medium transition-all duration-200 ${
              isEditing
                ? "bg-[#e5a00d]/15 border border-[#e5a00d]/40 text-[#e5a00d] hover:bg-[#e5a00d]/25"
                : "bg-white/[0.06] border border-white/10 text-[#a1a1aa] hover:bg-white/[0.12] hover:text-white"
            }`}
          >
            {isEditing ? (
              <>
                <Check className="w-4 h-4" />
                {t("profiles.done")}
              </>
            ) : (
              <>
                <Pencil className="w-3.5 h-3.5" />
                {t("profiles.manage")}
              </>
            )}
          </button>
        )}
      </div>

      {showCreateModal && (
        <CreateProfileModal onClose={() => setShowCreateModal(false)} />
      )}
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
