import axiosClient from "./axiosClient";

/**
 * Phiếu dùng thử ẩn danh.
 *
 * Vì sao phần này phải có mặt giao diện
 * --------------------------------------
 * Cổng gác (`app/access_gate.py`) cho phép `/realtime/*` chạy với **một trong
 * hai**: phiên đăng nhập, HOẶC một phiếu dùng thử. Nhưng phiếu chỉ lấy được
 * bằng `POST /trial/start`, và trước tệp này **không có chỗ nào trong giao diện
 * gọi nó**. Hệ quả: tuyến `/realtime` mở cho khách vãng lai, khách bấm vào, và
 * mọi lời gọi API trả 401 — tính năng dùng thử tồn tại đầy đủ ở máy chủ mà
 * không ai chạm tới được.
 *
 * `start` là POST chứ không phải GET vì nó ĐẶT cookie. Một GET đặt cookie sẽ bị
 * trình duyệt nạp trước và bởi mọi bộ quét liên kết, nên hạn ngạch bắt đầu tiêu
 * trước khi người dùng bấm gì.
 */

const API_PREFIX = "/api/v1/trial";

/** Sự kiện phát ra mỗi khi máy chủ báo lại số phút còn lại. Xem `axiosClient`. */
export const TRIAL_EVENT = "voya:trial-minutes";

export interface TrialState {
  /** Đã có phiếu chưa. `false` nghĩa là chưa bấm "dùng thử" lần nào. */
  has_grant: boolean;
  minutes_limit: number;
  minutes_used: number;
  minutes_remaining: number;
  /** Mốc hạn ngạch làm mới, dạng ISO. */
  resets_at: string | null;
  /** Có phiếu nhưng đã tiêu hết phút hôm nay. */
  exhausted: boolean;
}

/**
 * Xin phiếu, hoặc lấy lại tình trạng phiếu đang có.
 *
 * Idempotent theo cookie: bấm hai lần không cấp phiếu thứ hai và **không làm
 * mới hạn ngạch**. Nếu nó cấp mới mỗi lượt gọi thì hạn ngạch hằng ngày thành vô
 * hạn — chỉ cần gọi lại đúng endpoint này.
 */
export async function startTrial(): Promise<TrialState> {
  const res = await axiosClient.post<TrialState>(`${API_PREFIX}/start`);
  return res.data;
}

/** Số phút còn lại. Không tiêu tốn gì — dùng để vẽ đồng hồ. */
export async function fetchTrialStatus(): Promise<TrialState> {
  const res = await axiosClient.get<TrialState>(`${API_PREFIX}/status`);
  return res.data;
}

/**
 * Đọc số phút còn lại từ header của MỘT phản hồi bất kỳ.
 *
 * Cổng gác gắn `X-Trial-Minutes-Remaining` vào **mọi** phản hồi đi qua phiếu,
 * không chỉ lúc hết. Nhờ vậy đồng hồ trên màn hình cập nhật theo từng lượt
 * nhận dạng mà không phải gọi thêm một vòng `/trial/status` cho mỗi khung hình
 * — và với một trang bắn request liên tục thì "một vòng nữa mỗi khung hình" là
 * gấp đôi lưu lượng để hiển thị một con số.
 */
export function minutesFromHeaders(
  headers: unknown,
): { remaining: number; limit: number } | null {
  const h = headers as Record<string, string> | undefined;
  if (!h) return null;
  const remaining = Number(h["x-trial-minutes-remaining"]);
  const limit = Number(h["x-trial-minutes-limit"]);
  if (!Number.isFinite(remaining) || !Number.isFinite(limit)) return null;
  return { remaining, limit };
}
