/**
 * Nhớ trang người dùng đang xem TRƯỚC khi rẽ vào Cài đặt, để trang Cài đặt có
 * nút "← Quay lại" trỏ đúng về đó.
 *
 * Vì sao không dùng `navigate(-1)`: lịch sử trình duyệt không biết ranh giới
 * của khu Cài đặt. Người dùng vào Tài khoản → Bảo mật → Đồng thuận rồi bấm
 * quay lại sẽ chỉ lùi về Bảo mật; và ai mở thẳng `/settings/security` từ một
 * liên kết trong thư thì không có gì để lùi. Ghi lại đường dẫn cuối cùng
 * NGOÀI khu Cài đặt thì cả hai trường hợp đều về đúng chỗ.
 *
 * `sessionStorage` chứ không phải biến trong bộ nhớ: F5 ở trang Cài đặt vẫn
 * còn nút quay lại. Mọi lần đọc/ghi đều bọc try/catch vì cửa sổ riêng tư hoặc
 * chính sách trình duyệt có thể ném lỗi — nút chỉ lùi về Trang chủ, không đổ.
 */
const KEY = "voya.settings.returnTo";
const SETTINGS_PREFIX = "/settings";
const FALLBACK = "/";

/** Những đường không bao giờ là "trang vừa xem" có nghĩa để quay về. */
const IGNORED_PREFIXES = ["/login", "/register", "/forgot-password", "/reset-password", "/recover", "/invitation", "/logout"];

export function rememberReturnPath(pathnameWithSearch: string): void {
  const path = pathnameWithSearch || "";
  if (!path.startsWith("/")) return;
  if (path.startsWith(SETTINGS_PREFIX)) return;
  if (IGNORED_PREFIXES.some((p) => path === p || path.startsWith(p + "/") || path.startsWith(p + "?"))) return;
  try {
    window.sessionStorage.setItem(KEY, path);
  } catch {
    /* không lưu được thì nút quay lại dùng đường mặc định */
  }
}

export function getReturnPath(): string {
  try {
    const v = window.sessionStorage.getItem(KEY);
    if (v && v.startsWith("/") && !v.startsWith("//") && !v.startsWith(SETTINGS_PREFIX)) return v;
  } catch {
    /* xem trên */
  }
  return FALLBACK;
}
