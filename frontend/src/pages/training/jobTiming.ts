import type { TrainingJob } from '../../hooks/useTrainingAPI';

/**
 * Thời lượng một phiên huấn luyện.
 *
 * Trước đây bước Tiến Độ tự có hàm định dạng riêng còn bước Kết Quả không hiển
 * thị thời gian gì cả — xem xong kết quả vẫn không biết lần chạy đó mất bao lâu.
 * Gom về một chỗ để hai bước đọc ra cùng một con số.
 */
export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds));
  const hours = Math.floor(s / 3600);
  const minutes = Math.floor((s % 3600) / 60);
  const seconds = s % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

/** Số giây job đã chạy, hoặc null nếu thiếu mốc thời gian để tính. */
export function jobDurationSeconds(job?: TrainingJob | null): number | null {
  if (!job?.started_at) return null;
  const start = new Date(job.started_at).getTime();
  // Job chưa kết thúc thì đo tới hiện tại; đã kết thúc thì chốt ở completed_at.
  const endSource = job.completed_at ?? (isFinished(job.status) ? job.started_at : null);
  const end = endSource ? new Date(endSource).getTime() : Date.now();
  if (!Number.isFinite(start) || !Number.isFinite(end)) return null;
  return Math.max(0, (end - start) / 1000);
}

function isFinished(status: string): boolean {
  return status === 'completed' || status === 'failed' || status === 'cancelled';
}
