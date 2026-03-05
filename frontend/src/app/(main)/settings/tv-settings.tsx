"use client";

import { useState, useMemo, useCallback } from "react";
import { Save, Volume2, Subtitles, Monitor, Languages, User } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSetLocale, getClientLocale, type Locale } from "@/lib/locale";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DSCard, TVButton } from "@/components/ds";
import { useAuth } from "@/contexts/auth-context";
import { useProfile } from "@/contexts/profile-context";
import { updateProfile } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { useSettingsData } from "@/hooks/use-settings-data";
import { ChangePasswordModal } from "@/components/settings/change-password-modal";

interface UserPreferences {
  default_audio: string;
  default_subtitle: string;
  subtitles_enabled: boolean;
  autoplay_next: boolean;
}

/* ─── Sub-components ─────────────────────────────────────── */

function TVSection({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <DSCard className="!p-0 overflow-hidden">
      <div className="flex items-center gap-3 px-5 pt-5 pb-3">
        {icon}
        <h3 className="text-base font-semibold text-[#fafafa]">{title}</h3>
      </div>
      <div className="divide-y divide-[#27272a]">
        {children}
      </div>
    </DSCard>
  );
}

function TVRow({
  label,
  description,
  children,
}: {
  label?: string;
  description?: string;
  children: React.ReactNode;
}) {
  if (!label) {
    return (
      <div className="flex items-center justify-center px-5 py-4 min-h-[60px]">
        {children}
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between gap-6 px-5 py-4 min-h-[60px]">
      <div className="flex flex-col gap-0.5">
        <span className="text-[15px] text-[#fafafa]">{label}</span>
        {description && (
          <span className="text-xs text-[#71717a]">{description}</span>
        )}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

/* ─── Main TV Settings Component ────────────────────────── */

export function TVSettings() {
  const { user } = useAuth();
  const { profile } = useProfile();
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [saving, setSaving] = useState(false);
  const toast = useToast();
  const t = useTranslations();
  const applyLocale = useSetLocale();
  const [currentLocale, setCurrentLocale] = useState<Locale>(getClientLocale);

  const handleSetLocale = useCallback(
    (loc: Locale) => {
      setCurrentLocale(loc);
      applyLocale(loc);
    },
    [applyLocale],
  );

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

  const { registrationOpen, togglingRegistration, handleToggleRegistration } =
    useSettingsData(!!user?.is_admin);

  const handleSave = async () => {
    setSaving(true);
    try {
      if (profile) {
        await updateProfile(profile.id, {
          preferences: preferences as unknown as Record<string, unknown>,
        });
      }
      localStorage.setItem("pref_autoplay_next", String(preferences.autoplay_next));
      localStorage.setItem("pref_subtitles_enabled", String(preferences.subtitles_enabled));
      toast(t("settings.saved"), "success");
    } catch {
      toast(t("settings.saveError"), "error");
    }
    setSaving(false);
  };

  return (
    <div className="min-h-full px-16 py-12 flex flex-col gap-8">

      {/* 2-column grid — uses full TV width */}
      <div className="grid grid-cols-2 gap-6 items-start">

        {/* Left: playback preferences */}
        <div className="flex flex-col gap-5">
          <TVSection icon={<Volume2 className="w-4 h-4 text-[#e5a00d]" />} title={t("settings.audio.title")}>
            <TVRow label={t("settings.audio.defaultLanguage")}>
              <Select
                value={preferences.default_audio}
                onValueChange={(v) => setPreferences({ ...preferences, default_audio: v })}
              >
                <SelectTrigger className="w-40" style={{ height: "40px" }}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent position="popper" style={{ maxHeight: "200px", overflowY: "auto" }}>
                  <SelectItem value="ita">{t("settings.audio.italian")}</SelectItem>
                  <SelectItem value="eng">{t("settings.audio.english")}</SelectItem>
                  <SelectItem value="jpn">{t("settings.audio.japanese")}</SelectItem>
                  <SelectItem value="original">{t("settings.audio.original")}</SelectItem>
                </SelectContent>
              </Select>
            </TVRow>
          </TVSection>

          <TVSection icon={<Subtitles className="w-4 h-4 text-[#e5a00d]" />} title={t("settings.subtitles.title")}>
            <TVRow label={t("settings.subtitles.autoShow")}>
              <Switch
                checked={preferences.subtitles_enabled}
                onCheckedChange={(v) => setPreferences({ ...preferences, subtitles_enabled: v })}
              />
            </TVRow>
            <TVRow label={t("settings.subtitles.defaultLanguage")}>
              <Select
                value={preferences.default_subtitle}
                onValueChange={(v) => setPreferences({ ...preferences, default_subtitle: v })}
              >
                <SelectTrigger className="w-40" style={{ height: "40px" }}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent position="popper" style={{ maxHeight: "200px", overflowY: "auto" }}>
                  <SelectItem value="ita">{t("settings.audio.italian")}</SelectItem>
                  <SelectItem value="eng">{t("settings.audio.english")}</SelectItem>
                  <SelectItem value="jpn">{t("settings.audio.japanese")}</SelectItem>
                  <SelectItem value="none">{t("settings.subtitles.none")}</SelectItem>
                </SelectContent>
              </Select>
            </TVRow>
          </TVSection>

          <TVSection icon={<Monitor className="w-4 h-4 text-[#e5a00d]" />} title={t("settings.playback.title")}>
            <TVRow label={t("settings.playback.autoplayNext")} description={t("settings.playback.autoplayDescription")}>
              <Switch
                checked={preferences.autoplay_next}
                onCheckedChange={(v) => setPreferences({ ...preferences, autoplay_next: v })}
              />
            </TVRow>
          </TVSection>
        </div>

        {/* Right: language & account */}
        <div className="flex flex-col gap-5">
          <TVSection icon={<Languages className="w-4 h-4 text-[#e5a00d]" />} title={t("settings.language.title")}>
            <TVRow label={t("settings.language.description")}>
              <div className="flex gap-2">
                {(["it", "en"] as Locale[]).map((loc) => (
                  <TVButton
                    key={loc}
                    variant={currentLocale === loc ? "primary" : "ghost"}
                    onClick={() => handleSetLocale(loc)}
                  >
                    {loc === "en" ? t("settings.language.english") : t("settings.language.italian")}
                  </TVButton>
                ))}
              </div>
            </TVRow>
          </TVSection>

          <TVSection icon={<User className="w-4 h-4 text-[#e5a00d]" />} title={t("settings.account.title")}>
            <TVRow label={t("settings.account.email")}>
              <span className="text-sm text-[#a1a1aa]">{user?.email || "—"}</span>
            </TVRow>
            <TVRow label={t("settings.account.role")}>
              <span className="text-sm text-[#a1a1aa]">
                {user?.is_admin ? t("common.admin") : t("common.user")}
              </span>
            </TVRow>
            <TVRow>
              <TVButton variant="ghost" onClick={() => setShowChangePassword(true)}>
                {t("settings.account.changePassword")}
              </TVButton>
            </TVRow>
            <TVRow>
              <TVButton variant="ghost" onClick={() => (window.location.href = "/profiles")}>
                {t("settings.account.manageProfiles")}
              </TVButton>
            </TVRow>
            {user?.is_admin && registrationOpen !== null && (
              <TVRow
                label={t("settings.account.registrations")}
                description={registrationOpen ? t("settings.account.registrationsOpen") : t("settings.account.registrationsClosed")}
              >
                <Switch
                  checked={registrationOpen}
                  disabled={togglingRegistration}
                  onCheckedChange={handleToggleRegistration}
                />
              </TVRow>
            )}
          </TVSection>
        </div>
      </div>

      {/* Save */}
      <div className="flex justify-center pt-2">
        <TVButton
          onClick={handleSave}
          disabled={saving}
          icon={<Save className="w-4 h-4" />}
        >
          {saving ? t("settings.saving") : t("settings.save")}
        </TVButton>
      </div>

      {showChangePassword && (
        <ChangePasswordModal onClose={() => setShowChangePassword(false)} />
      )}
    </div>
  );
}
