import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Đếm ngược tới lúc được xin mã mới.
 *
 * Vì sao tính bằng MỐC THỜI GIAN chứ không phải bằng bộ đếm giảm dần
 * -------------------------------------------------------------------
 * Cách hay gặp là `setInterval(() => setLeft(n => n - 1), 1000)`. Nó sai trong
 * đúng những tình huống người dùng hay rơi vào:
 *
 * * Chuyển sang tab khác → trình duyệt giới hạn timer của tab nền xuống còn
 *   một nhịp mỗi phút. Quay lại thấy còn 58 giây trong khi thực tế đã hết.
 * * Khoá màn hình điện thoại → timer dừng hẳn. Đồng hồ treo ở 43 mãi mãi.
 *
 * Nên ở đây `setInterval` chỉ dùng để **vẽ lại**; con số luôn được tính lại từ
 * `Date.now()`, thứ không nói dối.
 *
 * Đây là lớp lịch sự, không phải lớp cưỡng chế: máy chủ mới là nơi từ chối một
 * lượt xin mã quá sớm (`resend_too_soon`). Nếu hai bên lệch nhau thì máy chủ
 * đúng — nên khi nhận được từ chối, hãy gọi `startFrom(giây máy chủ nói)`.
 */
export function useResendCountdown(): {
  secondsLeft: number;
  startFrom: (seconds: number) => void;
  clear: () => void;
} {
  const [until, setUntil] = useState<number | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (until === null) {
      setSecondsLeft(0);
      return;
    }
    const tick = () => {
      const left = Math.max(0, Math.ceil((until - Date.now()) / 1000));
      setSecondsLeft(left);
      if (left === 0) setUntil(null);
    };
    tick();
    timer.current = setInterval(tick, 500);
    return () => {
      if (timer.current) clearInterval(timer.current);
      timer.current = null;
    };
  }, [until]);

  const startFrom = useCallback((seconds: number) => {
    if (!Number.isFinite(seconds) || seconds <= 0) {
      setUntil(null);
      return;
    }
    setUntil(Date.now() + seconds * 1000);
  }, []);

  const clear = useCallback(() => setUntil(null), []);

  return { secondsLeft, startFrom, clear };
}

/**
 * Rút số giây máy chủ yêu cầu đợi ra khỏi một lỗi 429.
 *
 * Thông báo là "vui lòng đợi 40 giây trước khi yêu cầu mã mới" — con số nằm
 * trong câu chữ chứ không có ở header nào, nên phải bóc bằng biểu thức. Không
 * bóc được thì trả về `null` và người gọi tự dùng thời gian chờ mặc định; đoán
 * bừa một con số sẽ tệ hơn.
 */
export function secondsFromRetryError(err: unknown): number | null {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail !== "string") return null;
  const m = detail.match(/(\d+)\s*giây/);
  if (!m) return null;
  const n = Number(m[1]);
  return Number.isFinite(n) && n > 0 ? n : null;
}
