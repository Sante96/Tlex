import { api } from "./client";

export interface WorkerInfo {
  id: number;
  phone: string;
  is_premium: boolean;
  status: "active" | "flood_wait" | "offline";
  current_load: number;
  is_connected: boolean;
  flood_wait_remaining_seconds?: number;
  flood_wait_until?: string;
}

export interface WorkersSummary {
  total: number;
  active: number;
  flood_wait: number;
  offline: number;
  connected_clients: number;
}

export interface WorkersStatusResponse {
  workers: WorkerInfo[];
  summary: WorkersSummary;
}

export async function getWorkersStatus(): Promise<WorkersStatusResponse> {
  const response = await api.get<WorkersStatusResponse>("/workers/status");
  return response.data;
}

export interface SystemStats {
  media: {
    movies: number;
    episodes: number;
    total: number;
  };
  users: {
    total: number;
    profiles: number;
  };
  workers: WorkersSummary;
}

export async function getSystemStats(): Promise<SystemStats> {
  const response = await api.get<SystemStats>("/stats");
  return response.data;
}
