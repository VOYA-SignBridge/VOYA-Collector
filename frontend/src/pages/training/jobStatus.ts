/**
 * Nhãn trạng thái job huấn luyện — nguồn duy nhất.
 *
 * Trước đây mỗi màn hình tự xử lý: Lịch sử có bảng dịch riêng, còn Tiến độ và
 * Kết quả in thẳng `job.status` ra tiếng Anh ("running", "completed") — và Kết
 * quả còn luôn tô xanh emerald kể cả khi job thất bại. Dùng chung ở đây để ba
 * chỗ không bao giờ mâu thuẫn nhau nữa.
 */

export type JobStatusBadge = { text: string; cls: string };

const STATUS_BADGES: Record<string, JobStatusBadge> = {
  pending: { text: 'Đang chờ', cls: 'bg-slate-100 text-slate-700' },
  queued: { text: 'Đang chờ', cls: 'bg-slate-100 text-slate-700' },
  running: { text: 'Đang chạy', cls: 'bg-ctu-blue/10 text-ctu-blue' },
  completed: { text: 'Hoàn thành', cls: 'bg-emerald-50 text-emerald-700' },
  failed: { text: 'Thất bại', cls: 'bg-red-50 text-red-700' },
  cancelled: { text: 'Đã hủy', cls: 'bg-amber-50 text-amber-700' },
};

/** Trạng thái lạ vẫn hiện được (dùng chính chuỗi gốc) thay vì rơi về ô trống. */
export function jobStatusBadge(status?: string | null): JobStatusBadge {
  if (!status) return { text: '—', cls: 'bg-slate-100 text-slate-700' };
  return STATUS_BADGES[status] ?? { text: status, cls: 'bg-slate-100 text-slate-700' };
}

export function jobStatusText(status?: string | null): string {
  return jobStatusBadge(status).text;
}
