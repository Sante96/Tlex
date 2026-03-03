"use client";

import { useState, useEffect } from "react";
import { DatabaseBackup, Loader2, Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { DSButton, DSCard } from "@/components/ds";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  listBackupChannels,
  createBackupChannel,
  syncBackupChannel,
  toggleBackupChannel,
  deleteBackupChannel,
  promoteBackupChannel,
  getBackupSyncInterval,
  setBackupSyncInterval,
  type BackupChannel,
} from "@/lib/api/backup";
import { getConfiguredChannels } from "@/lib/api/scanner";
import { BackupRow } from "./backup-row";
import { BackupForm } from "./backup-form";

export function BackupCard() {
  const t = useTranslations("backup");

  const [backups, setBackups] = useState<BackupChannel[]>([]);
  const [channelIds, setChannelIds] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [intervalHours, setIntervalHours] = useState(6);
  const [showForm, setShowForm] = useState(false);

  // Form state
  const [mainChannelId, setMainChannelId] = useState("");
  const [backupTitle, setBackupTitle] = useState("");
  const [inviteMembers, setInviteMembers] = useState(true);
  const [creating, setCreating] = useState(false);

  // Per-row action state
  const [syncingId, setSyncingId] = useState<number | null>(null);
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [promotingId, setPromotingId] = useState<number | null>(null);

  const load = async () => {
    try {
      const [channels, interval, configured] = await Promise.all([
        listBackupChannels(),
        getBackupSyncInterval(),
        getConfiguredChannels(),
      ]);
      setBackups(channels);
      setIntervalHours(interval.interval_hours);
      setChannelIds(configured.channel_ids);
      if (configured.channel_ids.length > 0) {
        setMainChannelId(String(configured.channel_ids[0]));
      }
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const handleCreate = async () => {
    const id = parseInt(mainChannelId);
    if (!id || !backupTitle.trim()) return;
    setCreating(true);
    try {
      const backup = await createBackupChannel({
        main_channel_id: id,
        title: backupTitle.trim(),
        invite_members: inviteMembers,
      });
      setBackups((prev) => [...prev, backup]);
      setMainChannelId("");
      setBackupTitle("");
      setShowForm(false);
    } catch {
      // silent
    }
    setCreating(false);
  };

  const handleSync = async (id: number) => {
    setSyncingId(id);
    try {
      const result = await syncBackupChannel(id);
      setBackups((prev) =>
        prev.map((b) =>
          b.id === id
            ? {
                ...b,
                synced_count: result.total,
                last_sync_at: new Date().toISOString(),
              }
            : b,
        ),
      );
    } catch {
      // silent
    }
    setSyncingId(null);
  };

  const handleToggle = async (id: number) => {
    setTogglingId(id);
    try {
      const updated = await toggleBackupChannel(id);
      setBackups((prev) => prev.map((b) => (b.id === id ? updated : b)));
    } catch {
      // silent
    }
    setTogglingId(null);
  };

  const handleDelete = async (id: number) => {
    if (!confirm(t("deleteConfirm"))) return;
    const deleteTelegram = confirm(t("deleteTelegramConfirm"));
    setDeletingId(id);
    try {
      await deleteBackupChannel(id, deleteTelegram);
      setBackups((prev) => prev.filter((b) => b.id !== id));
    } catch {
      // silent
    }
    setDeletingId(null);
  };

  const handlePromote = async (id: number) => {
    if (!confirm(t("promoteConfirm"))) return;
    setPromotingId(id);
    try {
      const newBackup = await promoteBackupChannel(id);
      setBackups((prev) =>
        prev
          .map((b) =>
            b.id === id ? { ...b, is_active: false, is_promoted: true } : b,
          )
          .concat(newBackup),
      );
    } catch {
      // silent
    }
    setPromotingId(null);
  };

  const handleIntervalChange = async (value: string) => {
    const hours = parseInt(value);
    setIntervalHours(hours);
    try {
      await setBackupSyncInterval(hours);
    } catch {
      // silent
    }
  };

  return (
    <DSCard
      icon={<DatabaseBackup className="w-5 h-5 text-[#e5a00d]" />}
      title={t("title")}
      description={t("description")}
    >
      <div className="flex flex-col gap-4">
        {/* Auto-sync interval */}
        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm font-medium text-[#fafafa]">
              {t("interval")}
            </span>
          </div>
          <Select
            value={String(intervalHours)}
            onValueChange={handleIntervalChange}
          >
            <SelectTrigger className="w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="0">{t("intervalDisabled")}</SelectItem>
              <SelectItem value="1">{t("interval1h")}</SelectItem>
              <SelectItem value="3">{t("interval3h")}</SelectItem>
              <SelectItem value="6">{t("interval6h")}</SelectItem>
              <SelectItem value="12">{t("interval12h")}</SelectItem>
              <SelectItem value="24">{t("interval24h")}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="h-px bg-[#27272a]" />

        {/* Backup list */}
        {loading ? (
          <div className="flex justify-center py-4">
            <Loader2 className="w-5 h-5 text-[#71717a] animate-spin" />
          </div>
        ) : backups.length === 0 && !showForm ? (
          <p className="text-sm text-[#71717a] text-center py-2">
            {t("noBackups")}
          </p>
        ) : (
          <div className="flex flex-col gap-2">
            {backups.map((b) => (
              <BackupRow
                key={b.id}
                backup={b}
                syncingId={syncingId}
                togglingId={togglingId}
                deletingId={deletingId}
                promotingId={promotingId}
                onSync={handleSync}
                onToggle={handleToggle}
                onDelete={handleDelete}
                onPromote={handlePromote}
              />
            ))}
          </div>
        )}

        {/* Create form */}
        {showForm && (
          <BackupForm
            channelIds={channelIds}
            mainChannelId={mainChannelId}
            onMainChannelIdChange={setMainChannelId}
            backupTitle={backupTitle}
            onBackupTitleChange={setBackupTitle}
            inviteMembers={inviteMembers}
            onInviteMembersChange={setInviteMembers}
            creating={creating}
            onCreate={handleCreate}
            onCancel={() => setShowForm(false)}
          />
        )}

        {/* Add button */}
        {!showForm && (
          <DSButton
            variant="secondary"
            onClick={() => setShowForm(true)}
            icon={<Plus className="w-4 h-4" />}
          >
            {t("createNew")}
          </DSButton>
        )}
      </div>
    </DSCard>
  );
}
