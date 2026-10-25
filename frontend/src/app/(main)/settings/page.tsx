"use client";

import { useState, useCallback } from "react";
import {
  Volume2,
  Subtitles,
  Monitor,
  User,
  Languages,
  UserPlus,
} from "lucide-react";
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
import {
  WorkersCard,
  StatsCard,
  ScannerCard,
  UsersCard,
  BackupCard,
} from "@/components/settings";
import { ChangePasswordModal } from "@/components/settings/change-password-modal";
import { AddWorkerCard } from "@/components/settings/add-worker-card";
import { DSCard, DSButton } from "@/components/ds";
import { useSettingsData } from "@/hooks/use-settings-data";
import { useProfilePreferences } from "@/hooks/use-profile-preferences";
import { SaveIndicator } from "@/components/settings/save-indicator";
import { useIsTV } from "@/hooks/use-platform";
import { cn } from "@/lib/utils";
import { TVSettings } from "./tv-settings";

type Tab = "preferences" | "account" | "admin";

export default function SettingsPage() {
  const isTV = useIsTV();
  if (isTV) return <TVSettings />;
  return <WebSettings />;
}

function WebSettings() {
  const { user } = useAuth();
  const [showChangePassword, setShowChangePassword] = useState(false);
  const t = useTranslations();
  const applyLocale = useSetLocale();
  const [currentLocale, setCurrentLocale] = useState<Locale>(getClientLocale);
  const { preferences, update, status } = useProfilePreferences();

  // The tab survives a reload (?tab=admin)
  const [tab, setTab] = useState<Tab>(() => {
    const asked = new URLSearchParams(window.location.search).get("tab");
    return asked === "account" || asked === "admin" ? asked : "preferences";
  });
  const tabs: Tab[] = user?.is_admin ? ["preferences", "account", "admin"] : ["preferences", "account"];
  const shown = tabs.includes(tab) ? tab : "preferences";
  const openTab = (next: Tab) => {
    setTab(next);
    window.history.replaceState(window.history.state, "", `?tab=${next}`);
  };

  const handleSetLocale = useCallback(
    (loc: Locale) => {
      setCurrentLocale(loc);
      applyLocale(loc);
    },
    [applyLocale],
  );

  // The admin data loads when its tab opens, not for every visit to the settings
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
  } = useSettingsData(!!user?.is_admin && shown === "admin");

  const languageSelect = (id: string, value: string, onChange: (v: string) => void, last: "original" | "none") => (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger id={id} className="w-40">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="ita">{t("settings.audio.italian")}</SelectItem>
        <SelectItem value="eng">{t("settings.audio.english")}</SelectItem>
        <SelectItem value="jpn">{t("settings.audio.japanese")}</SelectItem>
        {last === "original" ? (
          <SelectItem value="original">{t("settings.audio.original")}</SelectItem>
        ) : (
          <SelectItem value="none">{t("settings.subtitles.none")}</SelectItem>
        )}
      </SelectContent>
    </Select>
  );

  return (
    <div className="px-4 md:px-12 py-6 md:py-8">
      <div className="flex flex-wrap items-center gap-4 mb-6">
        <div
          role="tablist"
          aria-label={t("nav.settings")}
          className="flex gap-1 p-1 rounded-xl bg-white/5 border border-white/10 w-full md:w-fit"
        >
          {tabs.map((id) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={shown === id}
              onClick={() => openTab(id)}
              className={cn(
                "flex-1 md:flex-none px-4 h-9 rounded-lg text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-plex-orange",
                shown === id
                  ? "bg-plex-orange text-black"
                  : "text-[#a1a1aa] hover:text-white hover:bg-white/5",
              )}
            >
              {t(`settings.tabs.${id}`)}
            </button>
          ))}
        </div>
        {shown === "preferences" && <SaveIndicator status={status} />}
      </div>

      {shown === "preferences" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
          <DSCard
            icon={<Volume2 className="w-5 h-5 text-plex-orange" />}
            title={t("settings.audio.title")}
          >
            <div className="flex items-center justify-between">
              <label htmlFor="audio-lang" className="text-sm font-medium text-[#fafafa]">
                {t("settings.audio.defaultLanguage")}
              </label>
              {languageSelect("audio-lang", preferences.default_audio, (v) => update({ default_audio: v }), "original")}
            </div>
          </DSCard>

          <DSCard
            icon={<Subtitles className="w-5 h-5 text-plex-orange" />}
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
                  onCheckedChange={(checked: boolean) => update({ subtitles_enabled: checked })}
                />
              </div>
              <div className="flex items-center justify-between">
                <label htmlFor="subtitle-lang" className="text-[#fafafa]">
                  {t("settings.subtitles.defaultLanguage")}
                </label>
                {languageSelect("subtitle-lang", preferences.default_subtitle, (v) => update({ default_subtitle: v }), "none")}
              </div>
            </div>
          </DSCard>

          <DSCard
            icon={<Monitor className="w-5 h-5 text-plex-orange" />}
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
                onCheckedChange={(checked: boolean) => update({ autoplay_next: checked })}
              />
            </div>
          </DSCard>

          <DSCard
            icon={<Languages className="w-5 h-5 text-plex-orange" />}
            title={t("settings.language.title")}
          >
            <div className="flex items-center justify-between">
              <span className="text-sm text-[#fafafa]">{t("settings.language.description")}</span>
              <div className="flex gap-2">
                {(["it", "en"] as Locale[]).map((loc) => (
                  <DSButton
                    key={loc}
                    variant={currentLocale === loc ? "primary" : "secondary"}
                    onClick={() => handleSetLocale(loc)}
                    className="!h-8 !px-3"
                  >
                    {loc === "en" ? t("settings.language.english") : t("settings.language.italian")}
                  </DSButton>
                ))}
              </div>
            </div>
          </DSCard>
        </div>
      )}

      {shown === "account" && (
        <div className="max-w-xl">
          <DSCard
            icon={<User className="w-5 h-5 text-plex-orange" />}
            title={t("settings.account.title")}
          >
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-[#fafafa]">{t("settings.account.email")}</span>
                <span className="text-sm text-[#a1a1aa]">{user?.email || "—"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-[#fafafa]">{t("settings.account.role")}</span>
                <span className="text-sm text-[#a1a1aa]">
                  {user?.is_admin ? t("common.admin") : t("common.user")}
                </span>
              </div>
              <div className="h-px bg-[#27272a]" />
              <DSButton variant="secondary" onClick={() => setShowChangePassword(true)} className="w-full">
                {t("settings.account.changePassword")}
              </DSButton>
              <DSButton
                variant="secondary"
                onClick={() => (window.location.href = "/profiles")}
                className="w-full"
              >
                {t("settings.account.manageProfiles")}
              </DSButton>
            </div>
          </DSCard>
        </div>
      )}

      {shown === "admin" && user?.is_admin && (
        <div className="flex flex-col md:flex-row gap-6">
          <div className="flex-1 flex flex-col gap-6">
            {registrationOpen !== null && (
              <DSCard
                icon={<UserPlus className="w-5 h-5 text-plex-orange" />}
                title={t("settings.account.registrations")}
              >
                <div className="flex items-center justify-between">
                  <p className="text-sm text-[#a1a1aa]">
                    {registrationOpen
                      ? t("settings.account.registrationsOpen")
                      : t("settings.account.registrationsClosed")}
                  </p>
                  <Switch
                    id="registration"
                    checked={registrationOpen}
                    disabled={togglingRegistration}
                    onCheckedChange={handleToggleRegistration}
                    aria-label={t("settings.account.registrations")}
                  />
                </div>
              </DSCard>
            )}
            <UsersCard
              users={usersData}
              currentUserId={user?.id ?? 0}
              loading={loadingUsers}
              onRefresh={loadUsers}
            />
            <StatsCard data={statsData} loading={loadingStats} onRefresh={loadStats} />
          </div>
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
            <WorkersCard data={workersData} loading={loadingWorkers} onRefresh={loadWorkersStatus} />
            <AddWorkerCard onWorkersChanged={loadWorkersStatus} />
            <BackupCard />
          </div>
        </div>
      )}

      {/* Credit — mobile only (desktop has it in the sidebar) */}
      <p className="md:hidden text-[10px] text-[#3f3f46] text-center pt-6 tracking-wide select-none">
        {t("common.madeBy")}
      </p>

      {showChangePassword && <ChangePasswordModal onClose={() => setShowChangePassword(false)} />}
    </div>
  );
}
