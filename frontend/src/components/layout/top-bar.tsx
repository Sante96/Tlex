"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter, usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { LogOut, UserCircle, Users, Search, X } from "lucide-react";
import {
  DSAvatar,
  DSDropdownMenu,
  DSBreadcrumb,
  DSIconButton,
  TVButton,
  DSButton,
} from "@/components/ds";
import { AvatarPicker } from "@/components/ui/avatar-picker";
import { SearchBar } from "@/components/layout/search-bar";
import { useAuth } from "@/contexts/auth-context";
import { useProfile } from "@/contexts/profile-context";
import { useIsTV, useTVTier } from "@/hooks/use-platform";
import { updateProfile, getSeriesDetails, getMediaDetails } from "@/lib/api";

const DEFAULT_AVATAR = "/avatars/avatar-01.png";

function useBreadcrumbItems(): { label: string; href?: string }[] | null {
  const pathname = usePathname();
  const t = useTranslations();
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
      { label: t("nav.series"), href: "/series" },
      { label: name, href: `/series/${seasonMatch[1]}` },
      { label: `${t("topbar.seasonLabel")} ${seasonMatch[2]}` },
    ];
  }

  if (seriesMatch) {
    const name = titleCache[`series-${seriesMatch[1]}`] || "...";
    return [{ label: t("nav.series"), href: "/series" }, { label: name }];
  }

  if (mediaMatch) {
    const name = titleCache[`media-${mediaMatch[1]}`] || "...";
    return [{ label: t("nav.movies"), href: "/movies" }, { label: name }];
  }

  return null;
}

export function TopBar() {
  const router = useRouter();
  const t = useTranslations();
  const { logout } = useAuth();
  const { profile, clearProfile, refreshProfiles } = useProfile();
  const isTV = useIsTV();
  const tvTier = useTVTier();
  const avatarSize = tvTier === "4k" ? 36 : tvTier === "1080" ? 28 : 24;
  const [showAvatarPicker, setShowAvatarPicker] = useState(false);
  const [showMobileSearch, setShowMobileSearch] = useState(false);
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

  if (isTV) {
    return (
      <header
        className="h-10 tv-1080:h-12 tv-4k:h-14 flex items-center gap-3 tv-1080:gap-4 tv-4k:gap-5 px-4 tv-4k:px-6 sticky top-0 z-30 relative"
        style={{ borderBottom: "1px solid rgba(39, 39, 42, 0.15)" }}
      >
        <div className="absolute inset-0 -z-10 pointer-events-none" style={{ background: "rgba(9, 9, 11, 0.60)" }} />

        {/* Breadcrumb or page title */}
        <div className="flex-shrink-0">
          {breadcrumbItems ? (
            <DSBreadcrumb items={breadcrumbItems} />
          ) : (
            <span className="text-sm tv-4k:text-base font-semibold text-white">{t("nav.home")}</span>
          )}
        </div>

        {/* Search bar — D-pad focusable */}
        <div className="flex-1 max-w-[220px] tv-1080:max-w-xs tv-4k:max-w-sm">
          <SearchBar className="w-full" compact={tvTier === "720"} />
        </div>

        {/* Profile area + actions */}
        <div className="flex items-center gap-2 tv-1080:gap-3 tv-4k:gap-4 ml-auto shrink-0">
          <DSAvatar letter={profileLetter} src={profile?.avatar_url ?? undefined} size={avatarSize} />
          <span className="text-xs tv-1080:text-sm font-medium text-white">{profile?.name}</span>
          <TVButton
            variant="ghost"
            icon={<Users className="h-3.5 w-3.5 tv-1080:h-4 tv-1080:w-4" />}
            onClick={handleSwitchProfile}
            className="h-7 tv-1080:h-8 tv-4k:h-9 px-2.5 tv-1080:px-3 text-xs tv-1080:text-sm"
          >
            {t("topbar.switchProfile")}
          </TVButton>
          <DSButton
            variant="destructive"
            icon={<LogOut className="h-3.5 w-3.5 tv-1080:h-4 tv-1080:w-4" />}
            onClick={handleLogout}
            className="h-7 tv-1080:h-8 tv-4k:h-9 px-2.5 tv-1080:px-3 text-xs tv-1080:text-sm"
          >
            {t("topbar.logout")}
          </DSButton>
        </div>
      </header>
    );
  }

  return (
    <header
      className="h-14 flex items-center px-4 md:px-6 gap-3 sticky top-0 z-30 relative"
      style={{ borderBottom: "1px solid rgba(39, 39, 42, 0.5)" }}
    >
      {/* Blur layer as sibling — keeps header from creating a stacking context */}
      <div
        className="absolute inset-0 -z-10 pointer-events-none backdrop-blur-xl"
        style={{ background: "rgba(9, 9, 11, 0.80)" }}
      />
      <AnimatePresence mode="wait" initial={false}>
        {showMobileSearch ? (
          <motion.div
            key="search"
            className="flex flex-1 items-center gap-2"
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 16 }}
            transition={{ duration: 0.18, ease: [0.4, 0, 0.2, 1] }}
          >
            <SearchBar className="flex-1 min-w-0" />
            <DSIconButton
              onClick={() => setShowMobileSearch(false)}
              className="shrink-0 w-9 h-9 hover:text-[#fafafa]"
              icon={<X className="h-5 w-5" />}
            />
          </motion.div>
        ) : (
          <motion.div
            key="normal"
            className="flex flex-1 items-center justify-between"
            initial={{ opacity: 0, x: -16 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -16 }}
            transition={{ duration: 0.18, ease: [0.4, 0, 0.2, 1] }}
          >
            {/* Left side */}
            <div className="flex-1 min-w-0">
              {breadcrumbItems ? (
                <DSBreadcrumb items={breadcrumbItems} />
              ) : (
                <>
                  {/* Logo on mobile */}
                  <Link
                    href="/"
                    className="md:hidden text-xl font-extrabold tracking-tight text-[#e5a00d]"
                  >
                    TLEX
                  </Link>
                  {/* SearchBar on desktop */}
                  <div className="hidden md:block">
                    <SearchBar />
                  </div>
                </>
              )}
            </div>

            {/* Right side */}
            <div className="flex items-center gap-1 shrink-0">
              {/* Search icon — mobile only, hidden when breadcrumb is shown */}
              {!breadcrumbItems && (
                <DSIconButton
                  onClick={() => setShowMobileSearch(true)}
                  className="md:hidden w-9 h-9 hover:text-[#fafafa]"
                  icon={<Search className="h-5 w-5" />}
                />
              )}
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
                    label: t("topbar.changeAvatar"),
                    onClick: () => setShowAvatarPicker(true),
                  },
                  {
                    icon: <Users className="h-4 w-4" />,
                    label: t("topbar.switchProfile"),
                    onClick: handleSwitchProfile,
                  },
                  { label: "", separator: true },
                  {
                    icon: <LogOut className="h-4 w-4" />,
                    label: t("topbar.logout"),
                    onClick: handleLogout,
                    destructive: true,
                  },
                ]}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

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
