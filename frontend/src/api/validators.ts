import type { Session, Label, UploadResult, JobStatus, ClassRow } from "../types";
import { tr } from "../i18n";

/**
 * Kiểm hình dạng dữ liệu máy chủ trả về, trước khi giao diện tin vào nó.
 *
 * Vì sao thông báo ở đây bằng tiếng Việt, và mơ hồ có chủ ý
 * ----------------------------------------------------------
 * Chuỗi `error` của các hàm này **đi thẳng lên màn hình**: `useFetch` đặt nó
 * vào state lỗi, `LabelsPage` và `AdminVocabularyPage` hiện nó nguyên văn.
 * Trước đây chúng là "Invalid labels response" — vừa là tiếng Anh giữa một
 * giao diện tiếng Việt, vừa nói về hình dạng JSON, thứ người dùng không sửa
 * được và cũng không nên biết.
 *
 * Chi tiết kỹ thuật không mất đi: nó vào `console.warn`, nơi lập trình viên
 * đọc được còn người dùng thì không phải đọc.
 *
 * Đây cũng là lý do `lib/errors.friendlyError` tồn tại cho nhánh HTTP. Hai chỗ
 * vì hai loại lỗi khác nhau: ở đó là máy chủ **từ chối**, ở đây là máy chủ
 * **trả lời sai hình dạng** — không có mã HTTP nào để tra.
 */

export type Result<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; errorCode?: string };

export function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

/** Câu hiện cho người dùng. `detail` chỉ để lại trong console. */
function malformed(what: string, detail: string): { ok: false; error: string } {
  // Chữ cho LẬP TRÌNH VIÊN, chỉ in ở DEV, không bao giờ lên màn hình người
  // dùng — cố ý không dịch. Dịch nó chỉ làm khó việc tìm kiếm trong log.
  // i18n-ignore-next-line
  if (import.meta.env.DEV) console.warn(`[du lieu sai hinh dang] ${what}: ${detail}`);
  return {
    ok: false,
    error: tr("Dữ liệu {gi} máy chủ trả về không đúng định dạng. Hãy tải lại trang; nếu vẫn vậy, báo cho quản trị viên.", { gi: what }),
  };
}

export function validateLabels(data: unknown): Result<Label[]> {
  if (!Array.isArray(data)) return malformed("danh sách nhãn", "không phải mảng");
  for (const item of data) {
    if (!isObject(item)) return malformed("danh sách nhãn", "một phần tử không phải đối tượng");
  }
  return { ok: true, data: data as unknown as Label[] };
}

export function validateLabel(data: unknown): Result<Label> {
  if (!isObject(data)) return malformed("nhãn", "không phải đối tượng");
  return { ok: true, data: data as unknown as Label };
}

export function validateSessions(data: unknown): Result<Session[]> {
  if (!Array.isArray(data)) return malformed("danh sách phiên thu", "không phải mảng");
  const out: Session[] = [];
  for (const item of data) {
    if (!isObject(item)) {
      return malformed("danh sách phiên thu", "một phần tử không phải đối tượng");
    }
    const s = item as Partial<Session>;
    if (typeof s.session_id !== "string") {
      return malformed("danh sách phiên thu", "thiếu session_id");
    }
    out.push({
      session_id: s.session_id,
      user: String(s.user ?? ""),
      labels: Array.isArray(s.labels) ? (s.labels as string[]) : [],
      samples_count: Number(s.samples_count ?? 0),
      created_at: String(s.created_at ?? ""),
    } as Session);
  }
  return { ok: true, data: out };
}

export function validateJobStatus(data: unknown): Result<JobStatus> {
  if (!isObject(data)) return malformed("trạng thái tác vụ", "không phải đối tượng");
  return { ok: true, data: data as JobStatus };
}

export function validateUploadResult(data: unknown): Result<UploadResult> {
  if (!isObject(data)) return malformed("kết quả tải lên", "không phải đối tượng");
  return { ok: true, data: data as UploadResult };
}

export function validateClass(data: unknown): Result<ClassRow> {
  if (!isObject(data)) return malformed("lớp ký hiệu", "không phải đối tượng");
  if (typeof data.class_uid !== "string") {
    return malformed("lớp ký hiệu", "thiếu class_uid");
  }
  return { ok: true, data: data as unknown as ClassRow };
}
