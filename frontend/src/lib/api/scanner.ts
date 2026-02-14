import { api } from "./client";

export interface AutoScanStatus {
  enabled: boolean;
  running: boolean;
  interval_hours: number;
  last_scan: string | null;
  next_scan: string | null;
}

export interface ScanStatus {
  is_scanning: boolean;
}

export async function getAutoScanStatus(): Promise<AutoScanStatus> {
  const { data } = await api.get<AutoScanStatus>(
    "/api/v1/scanner/auto-scan/status",
  );
  return data;
}

export async function getScanStatus(): Promise<ScanStatus> {
  const { data } = await api.get<ScanStatus>("/api/v1/scanner/status");
  return data;
}

export async function triggerScan(
  limit?: number,
  topicId?: number,
): Promise<{ new_items: number; updated_items: number }> {
  const { data } = await api.post("/api/v1/scanner/scan", {
    limit,
    topic_id: topicId,
  });
  return data;
}

export async function setAutoScanInterval(
  hours: number,
): Promise<AutoScanStatus> {
  const { data } = await api.post<AutoScanStatus>(
    `/api/v1/scanner/auto-scan/interval?hours=${hours}`,
    {},
  );
  return data;
}
