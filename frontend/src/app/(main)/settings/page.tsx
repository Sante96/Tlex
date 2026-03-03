"use client";

import { useState, useMemo, useCallback } from "react";
import { Volume2, Subtitles, Monitor, User, Save, Languages } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSetLocale, getClientLocale, type Locale } from "@/lib/locale";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/contexts/auth-context";
import { useProfile } from "@/contexts/profile-context";
import { updateProfile } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import {
  WorkersCard,
  StatsCard,
  ScannerCard,
  UsersCard,
} from "@/components/settings";
import { ChangePasswordModal } from "@/components/settings/change-password-modal";
import { AddWorkerCard } from "@/components/settings/add-worker-card";
import { DSCard, DSButton } from "@/components/ds";
import { useSettingsData } from "@/hooks/use-settings-data";

interface UserPreferences {
  default_audio: string;
  default_subtitle: string;
  subtitles_enabled: boolean;
  autoplay_next: boolean;
}

export default function SettingsPage() {
  const { user } = useAuth();
  const { profile } = useProfile();
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [saving, setSaving] = useState(false);
  const toast = useToast();
  const t = useTranslations();
  const applyLocale = useSetLocale();
  const [currentLocale, setCurrentLocale] = useState<Locale>(getClientLocale);

  const handleSetLocale = useCallback((loc: Locale) => {
    setCurrentLocale(loc);
    applyLocale(loc);
  }, [applyLocale]);
  const profilePrefs = useMemo<UserPreferences>(() => {
    const p = (profile?.preferences ?? {}) as Record<string, unknown>;
    return {
      default_audio: (p.default_audio as string) || "ita",
      default_subtitle: (p.default_subtitle as string) || "ita",
      subtitles_enabled: p.subtitles_enabled !== false,
      autoplay_next: p.autoplay_next !== false,
    };
  }, [profile?.preferences]);

  const [localPrefs, setLocalPrefs] = useState<UserPreferences | null>(null);
  const preferences = localPrefs ?? profilePrefs;
  const setPreferences = (p: UserPreferences) => setLocalPrefs(p);

  const {
    workersData,
    statsData,
    autoScanData,
    setAutoScanData,
    scanStatus,
    loadingWorkers,
    loadingStats,
    loadingScan,
    triggeringScan,
    registrationOpen,
    togglingRegistration,
    usersData,
    loadingUsers,
    loadWorkersStatus,
    loadStats,
    loadScanStatus,
    handleTriggerScan,
    handleToggleRegistration,
    loadUsers,
  } = useSettingsData(!!user?.is_admin);

  const handleSave = async () => {
    setSaving(true);
    try {
      if (profile) {
        await updateProfile(profile.id, {
          preferences: preferences as unknown as Record<string, unknown>,
        });
      }
      localStorage.setItem(
        "pref_autoplay_next",
        String(preferences.autoplay_next),
      );
      localStorage.setItem(
        "pref_subtitles_enabled",
        String(preferences.subtitles_enabled),
      );
      toast(t("settings.saved"), "success");
    } catch {
      toast(t("settings.saveError"), "error");
    }
    setSaving(false);
  };

  return (
    <div className="px-4 md:px-12 py-6 md:py-8">
      {/* 2-column grid layout matching design */}
      <div className="flex flex-col md:flex-row gap-6">
        {/* Left Column */}
        <div className="flex-1 flex flex-col gap-6">
          {/* Audio */}
          <DSCard
            icon={<Volume2 className="w-5 h-5 text-[#e5a00d]" />}
            title={t("settings.audio.title")}
          >
            <div className="flex items-center justify-between">
              <label
                htmlFor="audio-lang"
                className="text-sm font-medium text-[#fafafa]"
              >
                {t("settings.audio.defaultLanguage")}
              </label>
              <Select
                value={preferences.default_audio}
                onValueChange={(value) =>
                  setPreferences({ ...preferences, default_audio: value })
                }
              >
                <SelectTrigger id="audio-lang" className="w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ita">{t("settings.audio.italian")}</SelectItem>
                  <SelectItem value="eng">{t("settings.audio.english")}</SelectItem>
                  <SelectItem value="jpn">{t("settings.audio.japanese")}</SelectItem>
                  <SelectItem value="original">{t("settings.audio.original")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </DSCard>

          {/* Sottotitoli */}
          <DSCard
            icon={<Subtitles className="w-5 h-5 text-[#e5a00d]" />}
            title={t("settings.subtitles.title")}
          >
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <label htmlFor="subtitles-enabled" className="text-[#fafafa]">
                  {t("settings.subtitles.autoShow")}
                </label>
                <Switch
                  id="subtitles-enabled"
                  checked={preferences.subtitles_enabled}
                  onCheckedChange={(checked: boolean) =>
                    setPreferences({
                      ...preferences,
                      subtitles_enabled: checked,
                    })
                  }
                />
              </div>
              <div className="flex items-center justify-between">
                <label htmlFor="subtitle-lang" className="text-[#fafafa]">
                  {t("settings.subtitles.defaultLanguage")}
                </label>
                <Select
                  value={preferences.default_subtitle}
                  onValueChange={(value) =>
                    setPreferences({ ...preferences, default_subtitle: value })
                  }
                >
                  <SelectTrigger id="subtitle-lang" className="w-40">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ita">{t("settings.audio.italian")}</SelectItem>
                    <SelectItem value="eng">{t("settings.audio.english")}</SelectItem>
                    <SelectItem value="jpn">{t("settings.audio.japanese")}</SelectItem>
                    <SelectItem value="none">{t("settings.subtitles.none")}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </DSCard>

          {/* Riproduzione */}
          <DSCard
            icon={<Monitor className="w-5 h-5 text-[#e5a00d]" />}
            title={t("settings.playback.title")}
          >
            <div className="flex items-center justify-between">
              <div>
                <label htmlFor="autoplay" className="text-[#fafafa]">
                  {t("settings.playback.autoplayNext")}
                </label>
                <p className="text-xs text-[#71717a] mt-0.5">
                  {t("settings.playback.autoplayDescription")}
                </p>
              </div>
              <Switch
                id="autoplay"
                checked={preferences.autoplay_next}
                onCheckedChange={(checked: boolean) =>
                  setPreferences({ ...preferences, autoplay_next: checked })
                }
              />
            </div>
          </DSCard>

          {/* Account */}
          <DSCard
            icon={<Languages className="w-5 h-5 text-[#e5a00d]" />}
            title={t("settings.language.title")}
          >
            <div className="flex items-center justify-between">
              <span className="text-sm text-[#fafafa]">{t("settings.language.description")}</span>
              <div className="flex gap-2">
                {(["it", "en"] as Locale[]).map((loc) => (
                  <button
                    key={loc}
                    onClick={() => handleSetLocale(loc)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                      currentLocale === loc
                        ? "bg-[#e5a00d] text-black"
                        : "bg-white/5 border border-white/10 text-white/70 hover:bg-white/10"
                    }`}
                  >
                    {loc === "en" ? t("settings.language.english") : t("settings.language.italian")}
                  </button>
                ))}
              </div>
            </div>
          </DSCard>

          <DSCard
            icon={<User className="w-5 h-5 text-[#e5a00d]" />}
            title={t("settings.account.title")}
          >
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-[#fafafa]">{t("settings.account.email")}</span>
                <span className="text-sm text-[#a1a1aa]">
                  {user?.email || "—"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-[#fafafa]">{t("settings.account.role")}</span>
                <span className="text-sm text-[#a1a1aa]">
                  {user?.is_admin ? t("common.admin") : t("common.user")}
                </span>
              </div>
              <div className="h-px bg-[#27272a]" />
              <button
                onClick={() => setShowChangePassword(true)}
                className="h-9 w-full rounded-md text-sm text-[#fafafa] transition-colors hover:bg-[#27272a]"
                style={{ border: "1px solid #27272a" }}
              >
                {t("settings.account.changePassword")}
              </button>
              <a
                href="/profiles"
                className="flex items-center justify-center h-9 w-full rounded-md text-sm text-[#fafafa] transition-colors hover:bg-[#27272a]"
                style={{ border: "1px solid #27272a" }}
              >
                {t("settings.account.manageProfiles")}
              </a>
              {user?.is_admin && registrationOpen !== null && (
                <>
                  <div className="h-px bg-[#27272a]" />
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-sm text-[#fafafa]">
                        {t("settings.account.registrations")}
                      </span>
                      <p className="text-xs text-[#71717a] mt-0.5">
                        {registrationOpen
                          ? t("settings.account.registrationsOpen")
                          : t("settings.account.registrationsClosed")}
                      </p>
                    </div>
                    <Switch
                      id="registration"
                      checked={registrationOpen}
                      disabled={togglingRegistration}
                      onCheckedChange={handleToggleRegistration}
                    />
                  </div>
                </>
              )}
            </div>
          </DSCard>

          {/* Gestione Utenti (admin only) */}
          {user?.is_admin && (
            <UsersCard
              users={usersData}
              currentUserId={user?.id ?? 0}
              loading={loadingUsers}
              onRefresh={loadUsers}
            />
          )}
        </div>

        {/* Right Column (admin only) */}
        {user?.is_admin && (
          <div className="flex-1 flex flex-col gap-6">
            <ScannerCard
              autoScanData={autoScanData}
              scanStatus={scanStatus}
              loading={loadingScan}
              triggering={triggeringScan}
              onRefresh={loadScanStatus}
              onTriggerScan={handleTriggerScan}
              onAutoScanChange={setAutoScanData}
            />
            <StatsCard
              data={statsData}
              loading={loadingStats}
              onRefresh={loadStats}
            />
            <WorkersCard
              data={workersData}
              loading={loadingWorkers}
              onRefresh={loadWorkersStatus}
            />
            <AddWorkerCard
              workers={workersData?.workers ?? []}
              onWorkersChanged={loadWorkersStatus}
            />
          </div>
        )}
      </div>

      {/* Save Button */}
      <div className="flex justify-end pt-8">
        <DSButton
          onClick={handleSave}
          disabled={saving}
          icon={<Save className="w-4 h-4" />}
        >
          {saving ? t("settings.saving") : t("settings.save")}
        </DSButton>
      </div>

      {/* Credit — mobile only (desktop has it in the sidebar) */}
      <p className="md:hidden text-[10px] text-[#3f3f46] text-center pt-6 tracking-wide select-none">
        made by Sante
      </p>

      {showChangePassword && (
        <ChangePasswordModal onClose={() => setShowChangePassword(false)} />
      )}
    </div>
  );
}
