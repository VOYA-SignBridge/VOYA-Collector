/**
 * @i18n-key-table — `STATUS_LABEL` là bảng KHOÁ, dịch tại chỗ đọc bằng
 * `t(STATUS_LABEL[s])`, cùng khuôn với `ROLE_LABEL` ở `api/tenants.ts`.
 */
import apiClient from "./axiosClient";

/** Bản xuất dữ liệu CỦA CHÍNH người gọi — khác bản xuất tổ chức ở `api/tenants.ts`,
 *  vốn chỉ quản trị viên gọi được và chứa dữ liệu của cả tổ chức. */
export interface PersonalExport {
  export_id: string;
  status: "pending" | "running" | "ready" | "failed" | "expired";
  size_bytes: number | null;
  sample_count: number | null;
  error: string | null;
  created_at: string;
  completed_at: string | null;
  expires_at: string;
}

const PREFIX = "/api/v1/me/exports";

export const requestPersonalExport = () =>
  apiClient.post<{ export_id: string; status: string }>(PREFIX).then((r) => r.data);

export const fetchPersonalExports = () =>
  apiClient.get<PersonalExport[]>(PREFIX).then((r) => r.data);

export const personalExportDownloadUrl = (exportId: string) =>
  `${PREFIX}/${encodeURIComponent(exportId)}/download`;

/** Nhãn trạng thái bằng tiếng Việt — dịch ở nơi gọi bằng `t(STATUS_LABEL[s])`,
 *  cùng khuôn với `ROLE_LABEL`/`roleLabel()` ở `api/tenants.ts`. */
export const STATUS_LABEL: Record<PersonalExport["status"], string> = {
  pending: "Đang chờ",
  running: "Đang dựng gói",
  ready: "Sẵn sàng",
  failed: "Hỏng",
  expired: "Đã hết hạn",
};
