/**
 * Điểm đến sau khi đăng nhập/đăng ký.
 *
 * ProtectedRoute đính `?next=<đường dẫn>` khi đá khách sang /login. Chỉ chấp
 * nhận đường dẫn nội bộ: một giá trị như `//evil.com` hay `https://evil.com`
 * lọt qua sẽ thành lỗ hổng open-redirect, nên phải bắt đầu bằng đúng một dấu
 * "/" và không được là đường dẫn tới chính các trang xác thực (đăng nhập xong
 * lại quay về trang đăng nhập thì thành vòng lặp).
 */

const DEFAULT_DESTINATION = '/upload';
const AUTH_PATHS = ['/login', '/register', '/forgot-password', '/reset-password'];

export function safeRedirectTarget(next: string | null | undefined): string {
  if (!next) return DEFAULT_DESTINATION;

  let decoded: string;
  try {
    decoded = decodeURIComponent(next);
  } catch {
    return DEFAULT_DESTINATION;
  }

  if (!decoded.startsWith('/') || decoded.startsWith('//')) return DEFAULT_DESTINATION;
  // Chặn cả dạng "/\evil.com" — một số trình duyệt coi "\" tương đương "/".
  if (decoded.startsWith('/\\')) return DEFAULT_DESTINATION;

  const path = decoded.split(/[?#]/)[0];
  if (AUTH_PATHS.includes(path)) return DEFAULT_DESTINATION;

  return decoded;
}
