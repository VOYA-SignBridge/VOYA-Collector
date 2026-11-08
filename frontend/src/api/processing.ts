import apiClient from "./axiosClient";

export interface TaskRow {
  task_id: string;
  name: string;
  worker: string;
  state: "running" | "reserved" | "scheduled";
  args_preview: string;
  time_start: number | null;
  /** Tổ chức đã gửi việc; `null` = việc nền tảng hoặc không tra được chủ. */
  tenant_id: string | null;
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
  recent_failures: {
    action: string;
    target: string;
    reason: string;
    created_at: string;
    tenant_id: string | null;
  }[];
  /** Khác `null` khi không đọc được nhật ký việc hỏng — danh sách rỗng khi đó là "không biết". */
  recent_failures_error: string | null;
  /**
   * "tenant": danh sách việc đã lọc theo tổ chức đang làm việc.
   * "platform": quản trị nền tảng, thấy mọi việc.
   */
  task_scope: "tenant" | "platform";
  /** Chiều dài hàng đợi luôn là số của cả nền tảng. */
  queues_scope: "platform";
}

export const getProcessingSnapshot = () =>
  apiClient.get<ProcessingSnapshot>("/api/v1/admin/processing").then((r) => r.data);

export const revokeTask = (taskId: string, terminate: boolean) =>
  apiClient
    .post("/api/v1/admin/processing/revoke", { task_id: taskId, terminate })
    .then((r) => r.data);
