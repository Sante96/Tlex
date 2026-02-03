"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search, LogOut, UserCircle, Users } from "lucide-react";
import { Input } from "@/components/ui/input";
import { ProfileAvatar } from "@/components/ui/profile-avatar";
import { AvatarPicker } from "@/components/ui/avatar-picker";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/contexts/auth-context";
import { useProfile } from "@/contexts/profile-context";
import { updateProfile } from "@/lib/api";

const DEFAULT_AVATAR = "/avatars/avatar-01.png";

export function TopBar() {
  const router = useRouter();
  const { logout } = useAuth();
  const { profile, clearProfile, refreshProfiles } = useProfile();
  const [showAvatarPicker, setShowAvatarPicker] = useState(false);

  const handleAvatarChange = async (newAvatarSrc: string) => {
    if (!profile) return;
    try {
      await updateProfile(profile.id, { avatar_url: newAvatarSrc });
      await refreshProfiles();
    } catch (error) {
      console.error("Failed to update avatar:", error);
    }
  };

  const handleSwitchProfile = () => {
    clearProfile();
    router.push("/profiles");
  };

  const handleLogout = () => {
    clearProfile();
    logout();
  };

  return (
    <header className="h-14 flex items-center justify-between px-6 bg-background/80 backdrop-blur-sm border-b border-border">
      {/* Search */}
      <div className="flex items-center gap-4 flex-1 max-w-md">
        <div className="relative w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Cerca..."
            className="pl-9 bg-muted/50 border-0 focus-visible:ring-1"
          />
        </div>
      </div>

      {/* User menu */}
      <div className="flex items-center gap-2">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="rounded-full p-0 h-9 w-9 hover:ring-2 hover:ring-plex-orange/50 transition-all"
            >
              <ProfileAvatar
                src={profile?.avatar_url || DEFAULT_AVATAR}
                name={profile?.name || "User"}
                size="sm"
                selected
                className="pointer-events-none"
              />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-52">
            <div className="px-2 py-1.5">
              <p className="text-sm font-medium text-white">
                {profile?.name || "Profilo"}
              </p>
              {!profile?.has_worker && (
                <p className="text-xs text-yellow-500">
                  ⚠ Nessun worker assegnato
                </p>
              )}
            </div>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => setShowAvatarPicker(true)}>
              <UserCircle className="mr-2 h-4 w-4" />
              Cambia Avatar
            </DropdownMenuItem>
            <DropdownMenuItem onClick={handleSwitchProfile}>
              <Users className="mr-2 h-4 w-4" />
              Cambia Profilo
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={handleLogout}
              className="text-destructive"
            >
              <LogOut className="mr-2 h-4 w-4" />
              Esci
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Avatar Picker Modal */}
      {showAvatarPicker && (
        <AvatarPicker
          currentAvatar={profile?.avatar_url || DEFAULT_AVATAR}
          onSelect={handleAvatarChange}
          onClose={() => setShowAvatarPicker(false)}
        />
      )}
    </header>
  );
}
