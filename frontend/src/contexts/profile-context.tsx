"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
} from "react";
import type { ReactNode } from "react";
import Cookies from "js-cookie";
import { getProfiles, createProfile, type Profile } from "@/lib/api";
import { useAuth } from "./auth-context";

interface ProfileContextValue {
  profile: Profile | null;
  profiles: Profile[];
  isLoading: boolean;
  hasProfiles: boolean;
  needsProfileSelection: boolean;
  selectProfile: (profile: Profile) => void;
  createNewProfile: (
    name: string,
    avatarUrl?: string,
    isKids?: boolean,
  ) => Promise<Profile>;
  refreshProfiles: () => Promise<void>;
  clearProfile: () => void;
}

const ProfileContext = createContext<ProfileContextValue | null>(null);

const PROFILE_COOKIE_KEY = "selected_profile_id";

export function ProfileProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const [profile, setProfile] = useState<Profile | null>(null);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [hasProfiles, setHasProfiles] = useState(false);

  const refreshProfiles = useCallback(async () => {
    if (!isAuthenticated) {
      setProfiles([]);
      setHasProfiles(false);
      setIsLoading(false);
      return;
    }

    try {
      const data = await getProfiles();
      setProfiles(data.profiles);
      setHasProfiles(data.has_profiles);

      // Try to restore selected profile from cookie
      const savedProfileId = Cookies.get(PROFILE_COOKIE_KEY);
      if (savedProfileId) {
        const savedProfile = data.profiles.find(
          (p) => p.id === parseInt(savedProfileId, 10),
        );
        if (savedProfile) {
          setProfile(savedProfile);
        }
      }
    } catch (error) {
      console.error("Failed to fetch profiles:", error);
      setProfiles([]);
      setHasProfiles(false);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (!authLoading) {
      refreshProfiles();
    }
  }, [authLoading, refreshProfiles]);

  const selectProfile = useCallback((selectedProfile: Profile) => {
    setProfile(selectedProfile);
    Cookies.set(PROFILE_COOKIE_KEY, String(selectedProfile.id), {
      expires: 30,
    });
  }, []);

  const createNewProfile = useCallback(
    async (
      name: string,
      avatarUrl?: string,
      isKids = false,
    ): Promise<Profile> => {
      const newProfile = await createProfile({
        name,
        avatar_url: avatarUrl,
        is_kids: isKids,
      });

      // Refresh profiles list
      await refreshProfiles();

      // Auto-select the new profile
      selectProfile(newProfile);

      return newProfile;
    },
    [refreshProfiles, selectProfile],
  );

  const clearProfile = useCallback(() => {
    setProfile(null);
    Cookies.remove(PROFILE_COOKIE_KEY);
  }, []);

  // Determine if we need to show profile selection
  const needsProfileSelection =
    isAuthenticated && !authLoading && !isLoading && !profile;

  return (
    <ProfileContext.Provider
      value={{
        profile,
        profiles,
        isLoading: isLoading || authLoading,
        hasProfiles,
        needsProfileSelection,
        selectProfile,
        createNewProfile,
        refreshProfiles,
        clearProfile,
      }}
    >
      {children}
    </ProfileContext.Provider>
  );
}

export function useProfile() {
  const context = useContext(ProfileContext);
  if (!context) {
    throw new Error("useProfile must be used within ProfileProvider");
  }
  return context;
}
