"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { useProfile } from "@/contexts/profile-context";
import { useToast } from "@/components/ui/toast";
import { updateProfile } from "@/lib/api";

export interface UserPreferences {
  default_audio: string;
  default_subtitle: string;
  subtitles_enabled: boolean;
  autoplay_next: boolean;
}

export type SaveStatus = "idle" | "saving" | "saved";

/**
 * The active profile's player preferences, saved as soon as one changes (a Save button
 * at the bottom of the page was easy to miss). Only the changed key is sent (the backend
 * merges): sending the whole form wrote its defaults over the profile's own values, a
 * null subtitle language became "ita". Saves run one after the other, so quick changes
 * land in order; the player reads the profile in memory, refreshed after each.
 */
export function useProfilePreferences() {
  const { profile, refreshProfiles } = useProfile();
  const toast = useToast();
  const t = useTranslations();

  const profilePrefs = useMemo<UserPreferences>(() => {
    const p = (profile?.preferences ?? {}) as Record<string, unknown>;
    return {
      default_audio: (p.default_audio as string) || "ita",
      default_subtitle: (p.default_subtitle as string) || "ita",
      subtitles_enabled: p.subtitles_enabled !== false,
      autoplay_next: p.autoplay_next !== false,
    };
  }, [profile?.preferences]);

  const [local, setLocal] = useState<UserPreferences | null>(null);
  const [status, setStatus] = useState<SaveStatus>("idle");
  const preferences = local ?? profilePrefs;
  const latest = useRef(preferences);
  useEffect(() => {
    latest.current = preferences;
  }, [preferences]);
  const queue = useRef<Promise<void>>(Promise.resolve());
  const pending = useRef(0);
  const failed = useRef(false);
  const savedTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(savedTimer.current), []);

  const update = useCallback(
    (patch: Partial<UserPreferences>) => {
      if (!profile) return;
      const next = { ...latest.current, ...patch };
      latest.current = next;
      setLocal(next);
      setStatus("saving");
      clearTimeout(savedTimer.current);
      pending.current++;
      queue.current = queue.current
        .then(async () => {
          await updateProfile(profile.id, { preferences: patch });
          await refreshProfiles();
        })
        .catch(() => {
          // Back to what the profile holds: the screen mustn't show an unsaved choice
          failed.current = true;
          setLocal(null);
          toast(t("settings.saveError"), "error");
        })
        .finally(() => {
          if (--pending.current > 0) return;
          const ok = !failed.current;
          failed.current = false;
          setStatus(ok ? "saved" : "idle");
          if (ok) savedTimer.current = setTimeout(() => setStatus("idle"), 2000);
        });
    },
    [profile, refreshProfiles, toast, t],
  );

  return { preferences, update, status };
}
