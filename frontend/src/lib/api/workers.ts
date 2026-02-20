import { api } from "./client";

export interface WorkerInfo {
  id: number;
  phone: string;
  is_premium: boolean;
  status: "ACTIVE" | "FLOOD_WAIT" | "OFFLINE";
  current_load: number;
  is_connected: boolean;
  clients_total: number;
  clients_in_use: number;
  flood_wait_remaining_seconds?: number;
  flood_wait_until?: string;
}

export interface WorkersSummary {
  total: number;
  active: number;
  flood_wait: number;
  offline: number;
  connected_clients: number;
  total_clients: number;
  clients_in_use: number;
  clients_available: number;
}

export interface WorkersStatusResponse {
  workers: WorkerInfo[];
  summary: WorkersSummary;
}

export async function getWorkersStatus(): Promise<WorkersStatusResponse> {
  const response = await api.get<WorkersStatusResponse>(
    "/api/v1/workers/status",
  );
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
  const response = await api.get<SystemStats>("/api/v1/stats");
  return response.data;
}

export async function sendWorkerCode(
  phoneNumber: string,
): Promise<{ status: string; phone_code_hash: string }> {
  const response = await api.post<{ status: string; phone_code_hash: string }>(
    "/api/v1/workers/send-code",
    { phone_number: phoneNumber },
  );
  return response.data;
}

export async function verifyWorkerCode(
  phoneNumber: string,
  code: string,
  password?: string,
): Promise<{ status: string; worker_id?: number; is_premium?: boolean }> {
  const response = await api.post<{
    status: string;
    worker_id?: number;
    is_premium?: boolean;
  }>("/api/v1/workers/verify-code", {
    phone_number: phoneNumber,
    code,
    password,
  });
  return response.data;
}

export async function deleteWorker(workerId: number): Promise<void> {
  await api.delete(`/api/v1/workers/${workerId}`);
}

export interface BenchmarkResult {
  clients: number;
  speed_mbps: number;
  elapsed_seconds: number;
  bytes_downloaded: number;
  improvement_pct?: number;
}

export interface BenchmarkResponse {
  test_file_mb: number;
  total_clients_in_pool: number;
  clients_tested: number;
  results: BenchmarkResult[];
  optimal_clients_per_stream: number;
}

export async function runBenchmark(): Promise<BenchmarkResponse> {
  const response = await api.post<BenchmarkResponse>(
    "/api/v1/workers/benchmark",
  );
  return response.data;
}
