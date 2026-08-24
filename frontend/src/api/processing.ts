import apiClient from "./axiosClient";

export interface TaskRow {
  task_id: string;
  name: string;
  worker: string;
  state: "running" | "reserved" | "scheduled";
  args_preview: string;
  time_start: number | null;
}

export interface QueueDepth {
  name: string;
  /** `null` = không đo được. KHÁC với 0 ("hàng đợi trống"). */
  depth: number | null;
  error: string | null;
}

export interface ProcessingSnapshot {
  workers: string[];
  reachable: boolean;
  unreachable_reason: string | null;
  running: TaskRow[];
  reserved: TaskRow[];
  queues: QueueDepth[];
  recent_failures: { action: string; target: string; reason: string; created_at: string }[];
}

export const getProcessingSnapshot = () =>
  apiClient.get<ProcessingSnapshot>("/api/v1/admin/processing").then((r) => r.data);

export const revokeTask = (taskId: string, terminate: boolean) =>
  apiClient
    .post("/api/v1/admin/processing/revoke", { task_id: taskId, terminate })
    .then((r) => r.data);
