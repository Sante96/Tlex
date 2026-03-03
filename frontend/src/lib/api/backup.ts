import { api } from "./client";

export interface BackupTopic {
  main_topic_id: number;
  backup_topic_id: number;
  name: string;
}

export interface BackupChannel {
  id: number;
  main_channel_id: number;
  backup_channel_id: number;
  title: string;
  is_active: boolean;
  is_promoted: boolean;
  synced_count: number;
  last_sync_at: string | null;
  failure_count: number;
  max_failures: number;
  last_failure_at: string | null;
  topics: BackupTopic[];
}

export async function listBackupChannels(): Promise<BackupChannel[]> {
  const { data } = await api.get<BackupChannel[]>("/api/v1/backup/channels");
  return data;
}

export async function createBackupChannel(body: {
  main_channel_id: number;
  title: string;
  invite_members: boolean;
}): Promise<BackupChannel> {
  const { data } = await api.post<BackupChannel>(
    "/api/v1/backup/channels",
    body,
  );
  return data;
}

export async function syncBackupChannel(
  id: number,
): Promise<{ synced: number; total: number }> {
  const { data } = await api.post<{ synced: number; total: number }>(
    `/api/v1/backup/channels/${id}/sync`,
    {},
  );
  return data;
}

export async function toggleBackupChannel(id: number): Promise<BackupChannel> {
  const { data } = await api.patch<BackupChannel>(
    `/api/v1/backup/channels/${id}/toggle`,
  );
  return data;
}

export async function deleteBackupChannel(
  id: number,
  deleteTelegram = false,
): Promise<void> {
  await api.delete(
    `/api/v1/backup/channels/${id}?delete_telegram=${deleteTelegram}`,
  );
}

export async function promoteBackupChannel(id: number): Promise<BackupChannel> {
  const { data } = await api.post<BackupChannel>(
    `/api/v1/backup/channels/${id}/promote`,
    {},
  );
  return data;
}

export async function setMaxFailures(
  id: number,
  maxFailures: number,
): Promise<BackupChannel> {
  const { data } = await api.patch<BackupChannel>(
    `/api/v1/backup/channels/${id}/max-failures?max_failures=${maxFailures}`,
  );
  return data;
}

export async function getBackupSyncInterval(): Promise<{
  interval_hours: number;
}> {
  const { data } = await api.get<{ interval_hours: number }>(
    "/api/v1/backup/sync-interval",
  );
  return data;
}

export async function setBackupSyncInterval(
  hours: number,
): Promise<{ interval_hours: number }> {
  const { data } = await api.post<{ interval_hours: number }>(
    `/api/v1/backup/sync-interval?hours=${hours}`,
    {},
  );
  return data;
}
