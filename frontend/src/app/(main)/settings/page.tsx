"use client";

import { useEffect, useState } from "react";
import {
  Settings,
  Volume2,
  Subtitles,
  Monitor,
  User,
  Save,
  Server,
  RefreshCw,
  BarChart3,
  Film,
  Tv,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  getWorkersStatus,
  getSystemStats,
  type WorkersStatusResponse,
  type SystemStats,
} from "@/lib/api";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "@/contexts/auth-context";

interface UserPreferences {
  default_audio: string;
  default_subtitle: string;
  subtitles_enabled: boolean;
  autoplay_next: boolean;
}

export default function SettingsPage() {
  const { user } = useAuth();
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
  const [loadingWorkers, setLoadingWorkers] = useState(false);
  const [loadingStats, setLoadingStats] = useState(false);

  const loadWorkersStatus = async () => {
    try {
      setLoadingWorkers(true);
      const data = await getWorkersStatus();
      setWorkersData(data);
    } catch (error) {
      console.error("Failed to load workers status:", error);
    } finally {
      setLoadingWorkers(false);
    }
  };

  const loadStats = async () => {
    try {
      setLoadingStats(true);
      const data = await getSystemStats();
      setStatsData(data);
    } catch (error) {
      console.error("Failed to load stats:", error);
    } finally {
      setLoadingStats(false);
    }
  };

  useEffect(() => {
    if (user?.is_admin) {
      loadWorkersStatus();
      loadStats();
    }
  }, [user?.is_admin]);

  const handleSave = async () => {
    setSaving(true);
    // TODO: Save preferences to backend
    await new Promise((resolve) => setTimeout(resolve, 500));
    setSaving(false);
  };

  return (
    <div className="max-w-8xl">
      <div className="flex items-center gap-3 mb-8">
        <Settings className="w-8 h-8 text-plex-orange" />
        <h1 className="text-3xl font-bold">Impostazioni</h1>
      </div>

      <div className="space-y-8">
        {/* Audio Settings */}
        <SettingsSection
          icon={Volume2}
          title="Audio"
          description="Preferenze per le tracce audio"
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label htmlFor="audio-lang">Lingua audio predefinita</Label>
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
          </div>
        </SettingsSection>

        {/* Subtitle Settings */}
        <SettingsSection
          icon={Subtitles}
          title="Sottotitoli"
          description="Preferenze per i sottotitoli"
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label htmlFor="subtitles-enabled">
                Sottotitoli attivi di default
              </Label>
              <Switch
                id="subtitles-enabled"
                checked={preferences.subtitles_enabled}
                onCheckedChange={(checked: boolean) =>
                  setPreferences({ ...preferences, subtitles_enabled: checked })
                }
              />
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="subtitle-lang">
                Lingua sottotitoli predefinita
              </Label>
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
        </SettingsSection>

        {/* Playback Settings */}
        <SettingsSection
          icon={Monitor}
          title="Riproduzione"
          description="Preferenze di riproduzione"
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="autoplay">Autoplay episodio successivo</Label>
                <p className="text-xs text-muted-foreground">
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
          </div>
        </SettingsSection>

        {/* Account Settings */}
        <SettingsSection
          icon={User}
          title="Account"
          description="Informazioni account"
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>Email</Label>
              <span className="text-muted-foreground">
                {user?.email || "—"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <Label>Ruolo</Label>
              <span className="text-muted-foreground">
                {user?.is_admin ? "Amministratore" : "Utente"}
              </span>
            </div>
            <Separator />
            <Button variant="outline" className="w-full">
              Cambia password
            </Button>
            <Button variant="outline" className="w-full" asChild>
              <a href="/profiles">Gestisci profili</a>
            </Button>
          </div>
        </SettingsSection>

        {/* Admin Section: Stats + Workers side by side */}
        {user?.is_admin && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* System Stats */}
            {statsData && (
              <SettingsSection
                icon={BarChart3}
                title="Statistiche"
                description="Libreria e utenti"
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Label>Dati</Label>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={loadStats}
                      disabled={loadingStats}
                    >
                      <RefreshCw
                        className={`w-4 h-4 ${loadingStats ? "animate-spin" : ""}`}
                      />
                    </Button>
                  </div>

                  <div className="grid grid-cols-3 gap-2">
                    <div className="bg-zinc-800 rounded-lg p-2 text-center">
                      <Film className="w-4 h-4 mx-auto mb-1 text-blue-500" />
                      <div className="text-lg font-bold">
                        {statsData.media.movies}
                      </div>
                      <div className="text-xs text-muted-foreground">Film</div>
                    </div>
                    <div className="bg-zinc-800 rounded-lg p-2 text-center">
                      <Tv className="w-4 h-4 mx-auto mb-1 text-purple-500" />
                      <div className="text-lg font-bold">
                        {statsData.media.episodes}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Episodi
                      </div>
                    </div>
                    <div className="bg-zinc-800 rounded-lg p-2 text-center">
                      <Users className="w-4 h-4 mx-auto mb-1 text-green-500" />
                      <div className="text-lg font-bold">
                        {statsData.users.profiles}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Profili
                      </div>
                    </div>
                  </div>

                  <div className="text-xs text-muted-foreground pt-1">
                    {statsData.users.total} utenti · {statsData.media.total}{" "}
                    media
                  </div>
                </div>
              </SettingsSection>
            )}

            {/* Workers Status */}
            <SettingsSection
              icon={Server}
              title="Workers"
              description="Telegram streaming"
            >
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <Label>Stato</Label>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={loadWorkersStatus}
                    disabled={loadingWorkers}
                  >
                    <RefreshCw
                      className={`w-4 h-4 ${loadingWorkers ? "animate-spin" : ""}`}
                    />
                  </Button>
                </div>

                {workersData && (
                  <>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div className="bg-zinc-800 rounded-lg p-3 text-center">
                        <div className="text-2xl font-bold text-green-500">
                          {workersData.summary.active}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          Attivi
                        </div>
                      </div>
                      <div className="bg-zinc-800 rounded-lg p-3 text-center">
                        <div className="text-2xl font-bold text-yellow-500">
                          {workersData.summary.flood_wait}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          FloodWait
                        </div>
                      </div>
                    </div>

                    <Separator />

                    <div className="space-y-2">
                      {workersData.workers.map((worker) => (
                        <div
                          key={worker.id}
                          className="flex items-center justify-between bg-zinc-800 rounded-lg p-3"
                        >
                          <div className="flex items-center gap-3">
                            <div
                              className={`w-2 h-2 rounded-full ${
                                worker.status === "active"
                                  ? "bg-green-500"
                                  : worker.status === "flood_wait"
                                    ? "bg-yellow-500"
                                    : "bg-red-500"
                              }`}
                            />
                            <div>
                              <div className="text-sm font-medium">
                                Worker #{worker.id}
                                {worker.is_premium && (
                                  <span className="ml-2 text-xs text-plex-orange">
                                    Premium
                                  </span>
                                )}
                              </div>
                              <div className="text-xs text-muted-foreground">
                                ****{worker.phone}
                              </div>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-sm">
                              Load: {worker.current_load}
                            </div>
                            {worker.flood_wait_remaining_seconds && (
                              <div className="text-xs text-yellow-500">
                                FloodWait:{" "}
                                {Math.ceil(
                                  worker.flood_wait_remaining_seconds / 60,
                                )}
                                m
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </SettingsSection>
          </div>
        )}

        {/* Save Button */}
        <div className="flex justify-end pt-4">
          <Button
            onClick={handleSave}
            disabled={saving}
            className="bg-plex-orange hover:bg-plex-orange/90 text-black"
          >
            <Save className="w-4 h-4 mr-2" />
            {saving ? "Salvataggio..." : "Salva preferenze"}
          </Button>
        </div>
      </div>
    </div>
  );
}

interface SettingsSectionProps {
  icon: React.ElementType;
  title: string;
  description: string;
  children: React.ReactNode;
}

function SettingsSection({
  icon: Icon,
  title,
  description,
  children,
}: SettingsSectionProps) {
  return (
    <div className="bg-zinc-900 rounded-lg p-6">
      <div className="flex items-center gap-3 mb-4">
        <Icon className="w-5 h-5 text-plex-orange" />
        <div>
          <h2 className="font-semibold">{title}</h2>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
      </div>
      {children}
    </div>
  );
}
