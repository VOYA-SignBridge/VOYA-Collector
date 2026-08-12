/**
 * Ba mặt của "tài khoản của tôi" ở phiên bản v6: thông báo, hỗ trợ, 2FA.
 *
 * Gộp một tệp vì chúng dùng chung một khái niệm — người đang đăng nhập — và
 * không đường nào nhận `user_id` từ phía client. Một API thông báo cho phép chỉ
 * định người khác là một API đọc trộm, nên phía máy chủ lấy danh tính từ phiên
 * và phía này không có gì để truyền.
 *
 * @i18n-key-table — chữ tiếng Việt trong tệp này là KHOÁ từ điển; bảng nhãn
 * xuất khẩu ở đây được dịch tại chỗ dùng bằng `t(BANG[x])`.
 */

import axiosClient from "./axiosClient";

const NOTIFY = "/api/v1/notifications";
const SUPPORT = "/api/v1/support";
const TFA = "/api/v1/2fa";

// ===========================================================================
// Thông báo
// ===========================================================================
export type NotificationKind =
  | "subscription" | "consent" | "security" | "training"
  | "support" | "data" | "system";

export type Severity = "info" | "success" | "warning" | "critical";

export interface AppNotification {
  notification_id: string;
  kind: NotificationKind;
  title: string;
  body: string;
  link: string | null;
  severity: Severity;
  read_at: string | null;
  created_at: string;
}

export const KIND_LABEL: Record<NotificationKind, string> = {
  subscription: "Gói dịch vụ",
  consent: "Pháp lý",
  security: "Bảo mật",
  training: "Huấn luyện",
  support: "Hỗ trợ",
  data: "Dữ liệu",
  system: "Hệ thống",
};

export async function fetchNotifications(
  opts: { limit?: number; unreadOnly?: boolean; before?: string } = {},
): Promise<{ items: AppNotification[]; unread: number }> {
  const { data } = await axiosClient.get(NOTIFY, {
    params: {
      limit: opts.limit ?? 30,
      unread_only: opts.unreadOnly ?? false,
      before: opts.before,
    },
  });
  return data;
}

/** Chỉ con số, cho cái chuông. Tách riêng vì giao diện hỏi nó theo chu kỳ. */
export async function fetchUnreadCount(): Promise<number> {
  const { data } = await axiosClient.get(`${NOTIFY}/unread-count`);
  return data.unread ?? 0;
}

export async function markRead(ids: string[]): Promise<number> {
  const { data } = await axiosClient.post(`${NOTIFY}/read`, { ids });
  return data.updated ?? 0;
}

export async function markAllRead(): Promise<number> {
  const { data } = await axiosClient.post(`${NOTIFY}/read-all`);
  return data.updated ?? 0;
}

// ===========================================================================
// Hỗ trợ
// ===========================================================================
export type TicketStatus = "open" | "pending" | "resolved" | "closed";
export type TicketCategory = "account" | "billing" | "data" | "bug" | "other";

export const STATUS_LABEL: Record<TicketStatus, string> = {
  open: "Đang mở",
  pending: "Chờ bạn phản hồi",
  resolved: "Đã giải quyết",
  closed: "Đã đóng",
};

export const CATEGORY_LABEL: Record<TicketCategory, string> = {
  account: "Tài khoản & đăng nhập",
  billing: "Thanh toán",
  data: "Dữ liệu",
  bug: "Lỗi phần mềm",
  other: "Khác",
};

/**
 * Ai đã nói: người dùng, người trực, hay trợ lý tự động.
 *
 * `is_staff` một mình KHÔNG đủ từ v3.16. Trợ lý là loại thứ ba, và nhét nó vào
 * một trong hai ô sẵn có đều là nói dối trên màn hình: `is_staff` bật thì giao
 * diện gắn nhãn "người trực" cho một câu máy sinh; tắt thì câu máy lẫn vào lời
 * người dùng. Xem `backend/app/support_bot.py`.
 */
export type MessageAuthorKind = "user" | "staff" | "bot";

export interface TicketMessage {
  message_id: string;
  author_label: string;
  is_staff: boolean;
  /** Cũ hơn v3.16 có thể thiếu — chỗ đọc phải suy lại từ `is_staff`. */
  author_kind?: MessageAuthorKind;
  body: string;
  created_at: string;
}

/** Loại người nói, chịu được cả bản ghi cũ chưa có `author_kind`. */
export function authorKindOf(m: TicketMessage): MessageAuthorKind {
  return m.author_kind ?? (m.is_staff ? "staff" : "user");
}

export interface TicketSummary {
  /** Nhãn người mở phiếu, chép lúc gửi. Chỉ có ý nghĩa ở hàng đợi người trực. */
  requester?: string | null;
  ticket_id: string;
  subject: string;
  category: TicketCategory;
  status: TicketStatus;
  priority: string;
  created_at: string;
  updated_at: string;
  /** Đếm lời nhắn của NGƯỜI, không tính trợ lý. */
  message_count: number;
  /** Đoạn xem trước trong hàng đợi, cắt sẵn ở máy chủ. */
  last_snippet?: string | null;
  last_kind?: MessageAuthorKind | null;
}

export interface Ticket extends Omit<TicketSummary, "message_count"> {
  messages: TicketMessage[];
  /**
   * Chip trả lời nhanh hiện dưới ô nhập.
   *
   * Máy chủ suy lại mỗi lần đọc từ lời cuối của người dùng, và trả về mảng rỗng
   * khi người trực đã vào — từ lúc đó cuộc trao đổi là giữa hai người và chip
   * của máy chỉ chen ngang.
   */
  bot_suggestions?: string[];
}

/** Chip câu hỏi nhanh cho hội thoại mới, kèm lối thoát sang người thật. */
export async function fetchSupportStarters(): Promise<{
  starters: string[];
  escape: string;
}> {
  const { data } = await axiosClient.get(`${SUPPORT}/starters`);
  return { starters: data.starters ?? [], escape: data.escape ?? "" };
}

export async function fetchTickets(status?: TicketStatus): Promise<TicketSummary[]> {
  const { data } = await axiosClient.get(`${SUPPORT}/tickets`, {
    params: status ? { status } : undefined,
  });
  return data.items ?? [];
}

export async function fetchTicket(ticketId: string): Promise<Ticket> {
  const { data } = await axiosClient.get(`${SUPPORT}/tickets/${ticketId}`);
  return data;
}

export async function createTicket(payload: {
  subject: string; body: string; category: TicketCategory;
}): Promise<Ticket> {
  const { data } = await axiosClient.post(`${SUPPORT}/tickets`, payload);
  return data;
}

export async function replyToTicket(ticketId: string, body: string): Promise<Ticket> {
  const { data } = await axiosClient.post(`${SUPPORT}/tickets/${ticketId}/reply`, { body });
  return data;
}

export async function setTicketStatus(
  ticketId: string, status: TicketStatus,
): Promise<Ticket> {
  const { data } = await axiosClient.post(
    `${SUPPORT}/tickets/${ticketId}/status`, { status });
  return data;
}

/**
 * Hàng đợi của người trực: MỌI phiếu trong tổ chức, không chỉ phiếu của mình.
 *
 * Endpoint này tồn tại từ đầu và **không màn hình nào gọi nó** — đó chính là
 * nửa sau của lỗi "người dùng nhắn mà admin không nhận được". Nửa đầu là thiếu
 * thông báo; nửa này là thiếu chỗ để đọc.
 *
 * `status` mặc định ở máy chủ là `open`. Truyền `null` để lấy mọi trạng thái —
 * `undefined` sẽ rơi về mặc định của máy chủ, khác hẳn ý định.
 */
export async function fetchSupportQueue(
  status?: TicketStatus | null,
): Promise<TicketSummary[]> {
  const { data } = await axiosClient.get(`${SUPPORT}/queue`, {
    params: status === null ? { status: "" } : status ? { status } : undefined,
  });
  return data.items ?? [];
}

// ===========================================================================
// Xác thực hai bước
// ===========================================================================
export interface TwoFactorStatus {
  enabled: boolean;
  /** Đã cấp bí mật nhưng chưa xác nhận. KHÁC `enabled` — xem AccountPage. */
  pending: boolean;
  confirmed_at: string | null;
  recovery_codes_left: number;
}

export interface TwoFactorEnrollment {
  secret: string;
  /** Bí mật tách nhóm 4 ký tự, cho người gõ tay khi không quét được mã. */
  secret_grouped: string;
  uri: string;
}

export async function fetchTwoFactorStatus(): Promise<TwoFactorStatus> {
  const { data } = await axiosClient.get(`${TFA}/status`);
  return data;
}

export async function beginTwoFactorEnrollment(): Promise<TwoFactorEnrollment> {
  const { data } = await axiosClient.post(`${TFA}/enroll`);
  return data;
}

/** Bật 2FA. Mã khôi phục trả về ở đây là lần DUY NHẤT chúng đọc được. */
export async function confirmTwoFactor(code: string): Promise<string[]> {
  const { data } = await axiosClient.post(`${TFA}/confirm`, { code });
  return data.recovery_codes ?? [];
}

export async function disableTwoFactor(password: string): Promise<void> {
  await axiosClient.post(`${TFA}/disable`, { password });
}

export async function regenerateRecoveryCodes(password: string): Promise<string[]> {
  const { data } = await axiosClient.post(`${TFA}/recovery-codes`, { password });
  return data.recovery_codes ?? [];
}
