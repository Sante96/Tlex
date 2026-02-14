"use client";

import { useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { LogOut, UserCircle, Users } from "lucide-react";
import { DSAvatar, DSDropdownMenu, DSBreadcrumb } from "@/components/ds";
import { AvatarPicker } from "@/components/ui/avatar-picker";
import { SearchBar } from "@/components/layout/search-bar";
import { useAuth } from "@/contexts/auth-context";
import { useProfile } from "@/contexts/profile-context";
import { updateProfile } from "@/lib/api";

const DEFAULT_AVATAR = "/avatars/avatar-01.png";

function useBreadcrumbItems(): { label: string; href?: string }[] | null {
  const pathname = usePathname();

  // /series/[id]/season/[season] → Serie TV / Serie Name (handled by page context, use generic)
  const seasonMatch = pathname.match(/^\/series\/(\d+)\/season\/(\d+)/);
  if (seasonMatch) {
    return [
      { label: "Serie TV", href: "/series" },
      { label: "Serie", href: `/series/${seasonMatch[1]}` },
      { label: `Stagione ${seasonMatch[2]}` },
    ];
  }

  // /series/[id] → Serie TV / Serie Name
  const seriesMatch = pathname.match(/^\/series\/(\d+)$/);
  if (seriesMatch) {
    return [{ label: "Serie TV", href: "/series" }, { label: "Dettaglio" }];
  }

  // /media/[id] → Film / Movie Name
  const mediaMatch = pathname.match(/^\/media\/(\d+)$/);
  if (mediaMatch) {
    return [{ label: "Film", href: "/movies" }, { label: "Dettaglio" }];
  }

  return null; // No breadcrumb on other pages
}

export function TopBar() {
  const router = useRouter();
  const { logout } = useAuth();
  const { profile, clearProfile, refreshProfiles } = useProfile();
  const [showAvatarPicker, setShowAvatarPicker] = useState(false);
  const breadcrumbItems = useBreadcrumbItems();

  const handleAvatarChange = async (newAvatarSrc: string) => {
    if (!profile) return;
    try {
      await updateProfile(profile.id, { avatar_url: newAvatarSrc });
      await refreshProfiles();
    } catch {}
  };

  const handleSwitchProfile = () => {
    clearProfile();
    router.push("/profiles");
  };

  const handleLogout = () => {
    clearProfile();
    logout();
  };

  const profileLetter = profile?.name?.charAt(0) || "U";

  return (
    <header
      className="h-14 flex items-center justify-between px-6"
      style={{
        backgroundColor: "#18181b",
        borderBottom: "1px solid #27272a",
      }}
    >
      {/* Left side: breadcrumb on detail pages, searchbar elsewhere */}
      {breadcrumbItems ? (
        <DSBreadcrumb items={breadcrumbItems} />
      ) : (
        <SearchBar />
      )}

      {/* User menu */}
      <DSDropdownMenu
        trigger={
          <DSAvatar
            letter={profileLetter}
            src={profile?.avatar_url ?? undefined}
          />
        }
        items={[
          {
            icon: <UserCircle className="h-4 w-4" />,
            label: "Cambia Avatar",
            onClick: () => setShowAvatarPicker(true),
          },
          {
            icon: <Users className="h-4 w-4" />,
            label: "Cambia Profilo",
            onClick: handleSwitchProfile,
          },
          { label: "", separator: true },
          {
            icon: <LogOut className="h-4 w-4" />,
            label: "Esci",
            onClick: handleLogout,
            destructive: true,
          },
        ]}
      />

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
