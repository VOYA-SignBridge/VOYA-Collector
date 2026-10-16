/**
 * Hàng đợi kiểm duyệt và hai cái nút.
 *
 * Đơn vị là PHIÊN THU, không phải mẫu: một lần quay sinh ra ~11,5 mẫu dùng
 * chung `capture_session_id`, nên hàng đợi gộp chúng thành một dòng. Người
 * duyệt xem một cử chỉ, không xem mười một bản tăng cường của nó.
 */

import axiosClient from "./axiosClient";

const API_PREFIX = "/api/v1/moderation";

export interface PendingSession {
  capture_session_id: string;
  label_original: string | null;
  dialect: string | null;
  language: string | null;
  sample_count: number;
  captured_at: string | null;
  contributor_id: string | null;
  contributor_name: string | null;
  contributor_email: string | null;
  completeness: number | null;
  /** `sample_uid` của mẫu GỐC (`augment_id = 0`) — thứ để xem lại. */
  original_uid: string | null;
}

export interface ModerationQueue {
  /** Tổng số phiên đang chờ. Có thể LỚN HƠN `items.length` vì `limit`. */
  count: number;
  items: PendingSession[];
}

export async function fetchQueue(limit = 100): Promise<ModerationQueue> {
  const res = await axiosClient.get<ModerationQueue>(`${API_PREFIX}/queue`, {
    params: { limit },
  });
  return res.data;
}

export interface DecisionResult {
  capture_session_id: string;
  review_status: string;
  sample_count: number;
  tenant_id: string;
}

export async function approveSession(sessionId: string): Promise<DecisionResult> {
  const res = await axiosClient.post(`${API_PREFIX}/sessions/${sessionId}/approve`, {
    note: "",
  });
  return res.data;
}

/**
 * Từ chối. `note` là BẮT BUỘC — máy chủ từ chối một lượt gọi không kèm lý do.
 *
 * Không phải nghi thức: tới lúc người duyệt nhìn tới thì người đóng góp đã bỏ
 * công quay rồi, và một lời từ chối không nói vì sao thì họ không có gì để sửa.
 * Dữ liệu KHÔNG bị xoá — họ vẫn dùng được cho riêng mình.
 */
export async function rejectSession(
  sessionId: string,
  note: string,
): Promise<DecisionResult> {
  const res = await axiosClient.post(`${API_PREFIX}/sessions/${sessionId}/reject`, {
    note,
  });
  return res.data;
}
