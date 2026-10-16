/**
 * Ngày giờ hiệu lực của văn bản pháp lý: từ ô `datetime-local` tới máy chủ.
 *
 * Vấn đề (LEG-04, 13/09/2026)
 * ---------------------------
 * `<input type="datetime-local">` trả về `"2026-08-20T09:00"` — KHÔNG có múi
 * giờ. Bản trước gửi nguyên chuỗi ấy; máy chủ đọc bằng `fromisoformat` và hiểu
 * theo múi giờ của container, là **UTC**. Người ở Việt Nam gõ 09:00 thì văn bản
 * có hiệu lực lúc 16:00 giờ Việt Nam — lệch 7 giờ trên một mốc pháp lý.
 *
 * Cách làm
 * --------
 * Giữ đúng giờ-trên-tường người dùng gõ và gắn offset của trình duyệt vào:
 * `"2026-08-20T09:00:00+07:00"`. Máy chủ (Python 3.11 `fromisoformat`,
 * Pydantic `datetime`) đọc offset đó và lưu đúng thời điểm tuyệt đối.
 *
 * Và hiện lại cho người dùng thấy CHÍNH XÁC thời điểm ấy kèm tên múi giờ —
 * cách Google Calendar, Stripe hay bất kỳ hệ thống lên lịch nghiêm túc nào làm.
 * Một mốc hiệu lực pháp lý không được phép mập mờ về múi giờ.
 */

/** `"2026-08-20T09:00"` (giờ địa phương trình duyệt) -> ISO 8601 có offset. */
export function localInputToOffsetIso(local: string): string | null {
  const v = (local || "").trim();
  if (!v) return null;
  // `new Date("YYYY-MM-DDTHH:mm")` (không Z, không offset) được mọi trình duyệt
  // hiện đại diễn giải theo giờ ĐỊA PHƯƠNG — đúng ý người gõ.
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return null;

  const pad = (n: number) => String(n).padStart(2, "0");
  // `getTimezoneOffset()` là phút PHẢI CỘNG để ra UTC, nên dấu ngược với ISO.
  const offMin = -d.getTimezoneOffset();
  const sign = offMin >= 0 ? "+" : "-";
  const abs = Math.abs(offMin);
  const seconds = pad(d.getSeconds());
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}:${seconds}` +
    `${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`
  );
}

/** Nhãn múi giờ của trình duyệt, ví dụ `"Asia/Ho_Chi_Minh (UTC+07:00)"`. */
export function browserTimeZoneLabel(now: Date = new Date()): string {
  let name = "";
  try {
    name = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  } catch {
    name = "";
  }
  const offMin = -now.getTimezoneOffset();
  const sign = offMin >= 0 ? "+" : "-";
  const abs = Math.abs(offMin);
  const pad = (n: number) => String(n).padStart(2, "0");
  const utc = `UTC${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`;
  return name ? `${name} (${utc})` : utc;
}

/**
 * Câu xem trước để người công bố đọc lại trước khi bấm: giờ, ngày, múi giờ.
 * Trả `null` khi ô trống (= hiệu lực ngay) hoặc không đọc được.
 */
export function describeEffectiveFrom(local: string, locale = "vi-VN"): string | null {
  const v = (local || "").trim();
  if (!v) return null;
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return null;
  const time = new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
  const date = new Intl.DateTimeFormat(locale, { day: "2-digit", month: "2-digit", year: "numeric" }).format(d);
  return `${time} ${date} — ${browserTimeZoneLabel(d)}`;
}
