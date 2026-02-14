"use client";

import { useEffect, useState } from "react";
import {
  Settings,
  Volume2,
  Subtitles,
  Monitor,
  User,
  Save,
} from "lucide-react";
import {
  getWorkersStatus,
  getSystemStats,
  getAutoScanStatus,
  getScannerStatus,
  triggerManualScan,
  getRegistrationStatus,
  setRegistrationStatus,
  type WorkersStatusResponse,
  type SystemStats,
  type AutoScanStatus,
  type ScanStatus,
} from "@/lib/api";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/contexts/auth-context";
import { WorkersCard, StatsCard, ScannerCard } from "@/components/settings";
import { ChangePasswordModal } from "@/components/settings/change-password-modal";
import { AddWorkerCard } from "@/components/settings/add-worker-card";
import { DSCard, DSButton } from "@/components/ds";

interface UserPreferences {
  default_audio: string;
  default_subtitle: string;
  subtitles_enabled: boolean;
  autoplay_next: boolean;
}

export default function SettingsPage() {
  const { user } = useAuth();
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [saving, setSaving] = useState(false);
  const [preferences, setPreferences] = useState<UserPreferences>({
    default_audio: "ita",
    default_subtitle: "ita",
    subtitles_enabled: true,
    autoplay_next: true,
  });
  const [workersData, setWorkersData] = useState<WorkersStatusResponse | null>(
    null,
  );
  const [statsData, setStatsData] = useState<SystemStats | null>(null);
  const [autoScanData, setAutoScanData] = useState<AutoScanStatus | null>(null);
  const [scanStatus, setScanStatus] = useState<ScanStatus | null>(null);
  const [loadingWorkers, setLoadingWorkers] = useState(false);
  const [loadingStats, setLoadingStats] = useState(false);
  const [loadingScan, setLoadingScan] = useState(false);
  const [triggeringScan, setTriggeringScan] = useState(false);
  const [registrationOpen, setRegistrationOpen] = useState<boolean | null>(
    null,
  );
  const [togglingRegistration, setTogglingRegistration] = useState(false);

  const loadWorkersStatus = async () => {
    try {
      setLoadingWorkers(true);
      const data = await getWorkersStatus();
      setWorkersData(data);
    } catch {
    } finally {
      setLoadingWorkers(false);
    }
  };

  const loadStats = async () => {
    try {
      setLoadingStats(true);
      const data = await getSystemStats();
      setStatsData(data);
    } catch {
    } finally {
      setLoadingStats(false);
    }
  };

  const loadScanStatus = async () => {
    try {
      setLoadingScan(true);
      const [autoScan, status] = await Promise.all([
        getAutoScanStatus(),
        getScannerStatus(),
      ]);
      setAutoScanData(autoScan);
      setScanStatus(status);
    } catch {
    } finally {
      setLoadingScan(false);
    }
  };

  const handleTriggerScan = async () => {
    try {
      setTriggeringScan(true);
      await triggerManualScan();
      await loadScanStatus();
    } catch {
    } finally {
      setTriggeringScan(false);
    }
  };

  const loadRegistrationStatus = async () => {
    try {
      const data = await getRegistrationStatus();
      setRegistrationOpen(data.enabled);
    } catch {}
  };

  const handleToggleRegistration = async () => {
    if (registrationOpen === null) return;
    setTogglingRegistration(true);
    try {
      const data = await setRegistrationStatus(!registrationOpen);
      setRegistrationOpen(data.enabled);
    } catch {}
    setTogglingRegistration(false);
  };

  useEffect(() => {
    if (user?.is_admin) {
      loadWorkersStatus();
      loadStats();
      loadScanStatus();
      loadRegistrationStatus();
    }
  }, [user?.is_admin]);

  const handleSave = async () => {
    setSaving(true);
    await new Promise((resolve) => setTimeout(resolve, 500));
    setSaving(false);
  };

  return (
    <div style={{ padding: "32px 48px" }}>
      {/* Header */}
      <div className="flex items-center gap-3 mb-8">
        <Settings className="w-8 h-8 text-[#e5a00d]" />
        <h1 className="text-[28px] font-bold text-[#fafafa]">Impostazioni</h1>
      </div>

      {/* 2-column grid layout matching design */}
      <div className="flex gap-6">
        {/* Left Column */}
        <div className="flex-1 flex flex-col gap-6">
          {/* Audio */}
          <DSCard
            icon={<Volume2 className="w-5 h-5 text-[#e5a00d]" />}
            title="Audio"
          >
            <div className="flex items-center justify-between">
              <label
                htmlFor="audio-lang"
                className="text-sm font-medium text-[#fafafa]"
              >
                Lingua audio predefinita
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
                  <SelectItem value="ita">Italiano</SelectItem>
                  <SelectItem value="eng">English</SelectItem>
                  <SelectItem value="jpn">日本語</SelectItem>
                  <SelectItem value="original">Originale</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </DSCard>

          {/* Sottotitoli */}
          <DSCard
            icon={<Subtitles className="w-5 h-5 text-[#e5a00d]" />}
            title="Sottotitoli"
          >
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <label htmlFor="subtitles-enabled" className="text-[#fafafa]">
                  Mostra sottotitoli automaticamente
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
                  Lingua sottotitoli predefinita
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
                    <SelectItem value="ita">Italiano</SelectItem>
                    <SelectItem value="eng">English</SelectItem>
                    <SelectItem value="jpn">日本語</SelectItem>
                    <SelectItem value="none">Nessuno</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </DSCard>

          {/* Riproduzione */}
          <DSCard
            icon={<Monitor className="w-5 h-5 text-[#e5a00d]" />}
            title="Riproduzione"
          >
            <div className="flex items-center justify-between">
              <div>
                <label htmlFor="autoplay" className="text-[#fafafa]">
                  Autoplay episodio successivo
                </label>
                <p className="text-xs text-[#71717a] mt-0.5">
                  Riproduce automaticamente il prossimo episodio
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
            icon={<User className="w-5 h-5 text-[#e5a00d]" />}
            title="Account"
          >
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-[#fafafa]">Email</span>
                <span className="text-sm text-[#a1a1aa]">
                  {user?.email || "—"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-[#fafafa]">Ruolo</span>
                <span className="text-sm text-[#a1a1aa]">
                  {user?.is_admin ? "Amministratore" : "Utente"}
                </span>
              </div>
              <div className="h-px bg-[#27272a]" />
              <button
                onClick={() => setShowChangePassword(true)}
                className="h-9 w-full rounded-md text-sm text-[#fafafa] transition-colors hover:bg-[#27272a]"
                style={{ border: "1px solid #27272a" }}
              >
                Cambia password
              </button>
              <a
                href="/profiles"
                className="flex items-center justify-center h-9 w-full rounded-md text-sm text-[#fafafa] transition-colors hover:bg-[#27272a]"
                style={{ border: "1px solid #27272a" }}
              >
                Gestisci profili
              </a>
              {user?.is_admin && registrationOpen !== null && (
                <>
                  <div className="h-px bg-[#27272a]" />
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-sm text-[#fafafa]">
                        Registrazioni
                      </span>
                      <p className="text-xs text-[#71717a] mt-0.5">
                        {registrationOpen
                          ? "Nuovi utenti possono registrarsi"
                          : "Registrazioni chiuse"}
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
          {saving ? "Salvataggio..." : "Salva preferenze"}
        </DSButton>
      </div>

      {showChangePassword && (
        <ChangePasswordModal onClose={() => setShowChangePassword(false)} />
      )}
    </div>
  );
}
