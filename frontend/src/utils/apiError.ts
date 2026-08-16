/**
 * Rút thông báo lỗi hiển thị được từ một lỗi axios.
 *
 * Khuôn mẫu `catch (e: any) { ... e?.response?.data?.detail || "..." }` trước
 * đây lặp lại ở 13 chỗ và là toàn bộ số lỗi `no-explicit-any` của dự án. Gom về
 * một chỗ cũng vá được một lỗ hổng: `userMessage` do interceptor của
 * axiosClient gắn (đã dịch sang tiếng Việt: hết phiên, quá tải, mất mạng...)
 * trước đây bị bỏ qua, nên lỗi mạng chỉ hiện chuỗi mặc định chung chung.
 *
 * Thứ tự ưu tiên: `detail` của backend → `userMessage` đã dịch → chuỗi dự phòng.
 * (`error.message` của axios cố ý không dùng: nó là tiếng Anh kiểu
 * "Request failed with status code 500", vô nghĩa với người dùng cuối.)
 */
export function apiErrorMessage(err: unknown, fallback: string): string {
  if (err && typeof err === 'object') {
    const e = err as {
      userMessage?: unknown;
      response?: { data?: { detail?: unknown } };
    };

    const detail = e.response?.data?.detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
    // FastAPI trả lỗi validation dạng mảng — lấy message đầu tiên đọc được.
    if (Array.isArray(detail)) {
      const first = detail.find(
        (d): d is { msg: string } =>
          !!d && typeof d === 'object' && typeof (d as { msg?: unknown }).msg === 'string',
      );
      if (first) return first.msg;
    }

    if (typeof e.userMessage === 'string' && e.userMessage.trim()) return e.userMessage;
  }

  return fallback;
}
