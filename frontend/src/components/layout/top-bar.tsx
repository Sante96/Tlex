"use client";

import { useState, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { LogOut, UserCircle, Users } from "lucide-react";
import { DSAvatar, DSDropdownMenu, DSBreadcrumb } from "@/components/ds";
import { AvatarPicker } from "@/components/ui/avatar-picker";
import { SearchBar } from "@/components/layout/search-bar";
import { useAuth } from "@/contexts/auth-context";
import { useProfile } from "@/contexts/profile-context";
import { updateProfile, getSeriesDetails, getMediaDetails } from "@/lib/api";

const DEFAULT_AVATAR = "/avatars/avatar-01.png";

function useBreadcrumbItems(): { label: string; href?: string }[] | null {
  const pathname = usePathname();
  const [titleCache, setTitleCache] = useState<Record<string, string>>({});

  // Extract IDs from pathname
  const seasonMatch = pathname.match(/^\/series\/(\d+)\/season\/(\d+)/);
  const seriesMatch = pathname.match(/^\/series\/(\d+)$/);
  const mediaMatch = pathname.match(/^\/media\/(\d+)$/);

  const seriesId = seasonMatch?.[1] || seriesMatch?.[1];
  const mediaId = mediaMatch?.[1];

  useEffect(() => {
    if (seriesId && !titleCache[`series-${seriesId}`]) {
      getSeriesDetails(Number(seriesId))
        .then((data) =>
          setTitleCache((prev) => ({
            ...prev,
            [`series-${seriesId}`]: data.title,
          })),
        )
        .catch(() => {});
    }
    if (mediaId && !titleCache[`media-${mediaId}`]) {
      getMediaDetails(Number(mediaId))
        .then((data) =>
          setTitleCache((prev) => ({
            ...prev,
            [`media-${mediaId}`]: data.title,
          })),
        )
        .catch(() => {});
    }
  }, [seriesId, mediaId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (seasonMatch) {
    const name = titleCache[`series-${seasonMatch[1]}`] || "...";
    return [
      { label: "Serie TV", href: "/series" },
      { label: name, href: `/series/${seasonMatch[1]}` },
      { label: `Stagione ${seasonMatch[2]}` },
    ];
  }

  if (seriesMatch) {
    const name = titleCache[`series-${seriesMatch[1]}`] || "...";
    return [{ label: "Serie TV", href: "/series" }, { label: name }];
  }

  if (mediaMatch) {
    const name = titleCache[`media-${mediaMatch[1]}`] || "...";
    return [{ label: "Film", href: "/movies" }, { label: name }];
  }

  return null;
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
      className="h-14 flex items-center justify-between px-6 sticky top-0 z-30"
      style={{
        background: "rgba(9, 9, 11, 0.80)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        borderBottom: "1px solid rgba(39, 39, 42, 0.5)",
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
