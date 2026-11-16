/**
 * Cấu hình công khai nạp LÚC CHẠY (xem `docker-entrypoint.sh` và `index.html`), để
 * đổi được mà không phải dựng lại ảnh giao diện.
 */

/** Email liên hệ công khai, hoặc chuỗi rỗng nếu người vận hành chưa đặt. */
export function contactEmail(): string {
  const value = (window as unknown as { __ENV__?: { VITE_CONTACT_EMAIL?: string } }).__ENV__?.VITE_CONTACT_EMAIL ?? "";
  // Chỉ nhận thứ trông như một địa chỉ email: giá trị này đi thẳng vào `mailto:`.
  return /^[^\s@<>"']+@[^\s@<>"']+\.[^\s@<>"']+$/.test(value) ? value : "";
}
