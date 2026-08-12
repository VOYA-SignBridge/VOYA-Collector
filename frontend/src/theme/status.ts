/**
 * Bốn sắc thái trạng thái, một nguồn sự thật.
 *
 * Vì sao là tệp này chứ không phải lớp Tailwind rải khắp nơi
 * -----------------------------------------------------------
 * Trước tệp này, "thành công" được viết tay ở 31 tệp bằng bốn cách khác nhau
 * (`bg-green-100`, `bg-emerald-50`, `text-emerald-700`, `bg-emerald-600`). Đổi
 * quy ước màu một lần là sửa 31 chỗ và bỏ sót vài chỗ — và chỗ bỏ sót thì
 * không ai thấy cho tới khi nó nằm cạnh chỗ đã sửa.
 *
 * Vì sao "thành công" là XANH DƯƠNG
 * ----------------------------------
 * Quyết định của chủ dự án, và nó khớp thương hiệu: bảng màu con dấu CTU là
 * navy / xanh dương / vàng / đỏ. Xanh lá là màu DUY NHẤT trong giao diện không
 * có trong con dấu.
 *
 * Hệ quả phải xử lý: thương hiệu đã là xanh dương, nên một chip xanh dương tự
 * nó không nói "thành công" — nó chỉ nói "thuộc về ứng dụng này". Vì vậy:
 *
 *   * **Sắc thái không bao giờ đi một mình.** Mọi thành phần dùng bảng này đều
 *     kèm một biểu tượng (`theme/statusIcon`). Đây cũng là yêu cầu tiếp cận:
 *     WCAG 1.4.1 cấm dùng riêng màu để truyền đạt thông tin, và khoảng 8% nam
 *     giới không phân biệt được đỏ–lục.
 *   * **`neutral` là xám đá, không phải xanh nhạt.** Nếu "thông tin" cũng xanh
 *     thì xanh mất hết sức nặng.
 *
 * Vì sao chuỗi lớp viết đủ, không ghép động
 * ------------------------------------------
 * `bg-${tone}-100` **không chạy được**: Tailwind quét mã nguồn ở dạng văn bản,
 * một tên lớp chỉ tồn tại lúc chạy sẽ không được sinh ra và phần tử hiện ra
 * không màu. Bảng tra viết đủ chữ là bắt buộc, không phải dài dòng.
 */

export type StatusTone = "success" | "warning" | "danger" | "neutral";

/** `soft` cho nhãn/chip/hộp thông báo; `solid` cho nút chính; `outline` cho nút phụ. */
export type StatusVariant = "soft" | "solid" | "outline";

interface ToneClasses {
  soft: string;
  solid: string;
  outline: string;
  /** Chỉ phần chữ — cho những chỗ đã có nền riêng. */
  text: string;
  /** Chỉ phần nền đặc — thanh tiến trình, chấm trạng thái. */
  fill: string;
  ring: string;
}

const TONES: Record<StatusTone, ToneClasses> = {
  // Xanh dương CTU. `sky` là họ Tailwind gần #0e7bc2 nhất (sky-600 = #0284c7).
  success: {
    soft: "bg-sky-50 text-sky-800 border-sky-200",
    solid: "bg-sky-600 text-white border-sky-600 hover:bg-sky-700",
    outline: "bg-white text-sky-700 border-sky-300 hover:bg-sky-50",
    text: "text-sky-700",
    fill: "bg-sky-600",
    ring: "focus-visible:ring-sky-500",
  },
  warning: {
    soft: "bg-amber-50 text-amber-800 border-amber-200",
    solid: "bg-amber-500 text-white border-amber-500 hover:bg-amber-600",
    outline: "bg-white text-amber-700 border-amber-300 hover:bg-amber-50",
    text: "text-amber-700",
    fill: "bg-amber-500",
    ring: "focus-visible:ring-amber-500",
  },
  danger: {
    soft: "bg-red-50 text-red-800 border-red-200",
    solid: "bg-red-600 text-white border-red-600 hover:bg-red-700",
    outline: "bg-white text-red-700 border-red-300 hover:bg-red-50",
    text: "text-red-700",
    fill: "bg-red-600",
    ring: "focus-visible:ring-red-500",
  },
  neutral: {
    soft: "bg-slate-50 text-slate-700 border-slate-200",
    solid: "bg-slate-800 text-white border-slate-800 hover:bg-slate-900",
    outline: "bg-white text-slate-700 border-slate-300 hover:bg-slate-50",
    text: "text-slate-600",
    fill: "bg-slate-400",
    ring: "focus-visible:ring-slate-400",
  },
};

export function toneClasses(tone: StatusTone, variant: StatusVariant = "soft"): string {
  return TONES[tone][variant];
}

export function toneText(tone: StatusTone): string {
  return TONES[tone].text;
}

export function toneFill(tone: StatusTone): string {
  return TONES[tone].fill;
}

export function toneRing(tone: StatusTone): string {
  return TONES[tone].ring;
}

/**
 * Vòng nét khi điều hướng bằng bàn phím.
 *
 * `focus-visible` chứ không `focus`: dùng `focus` thì vòng nét cũng hiện sau
 * mỗi cú bấm chuột, và lập trình viên phản xạ đầu tiên là gỡ nó đi — lúc đó
 * người dùng bàn phím mất hẳn dấu hiệu vị trí con trỏ.
 */
export const FOCUS_RING =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2";

/**
 * Ánh xạ mã trạng thái nghiệp vụ → sắc thái.
 *
 * Đặt ở đây để cùng một chữ "ready" không hiện xanh ở trang này và xám ở trang
 * kia. Không khớp thì trả `neutral`: một trạng thái lạ **không được** mặc định
 * thành "thành công", vì lỗi im lặng ở hướng đó là hứa với người dùng một điều
 * chưa chắc đúng.
 */
const STATUS_TONE: Record<string, StatusTone> = {
  // vòng đời chung
  ready: "success", completed: "success", success: "success", active: "success",
  ok: "success", healthy: "success", published: "success", accepted: "success",
  verified: "success", synced: "success",
  // đang diễn ra / cần chú ý
  pending: "warning", running: "warning", queued: "warning", processing: "warning",
  in_review: "warning", draft: "warning", degraded: "warning", expiring: "warning",
  // hỏng / nguy hiểm
  failed: "danger", error: "danger", revoked: "danger", expired: "danger",
  locked: "danger", blocked: "danger", deleted: "danger", unhealthy: "danger",
};

export function toneForStatus(status: string | null | undefined): StatusTone {
  return STATUS_TONE[(status || "").toLowerCase()] ?? "neutral";
}
