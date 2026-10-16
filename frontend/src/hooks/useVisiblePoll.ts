import { useEffect, useRef } from "react";

/**
 * Gọi lại một hàm theo chu kỳ, và **dừng khi tab bị ẩn**.
 *
 * Phần "dừng khi ẩn" không phải tối ưu vặt. Một tab hỗ trợ để quên qua đêm với
 * chu kỳ 8 giây là hơn 10.000 lượt gọi vô ích tới máy chủ, mỗi lượt đánh thức
 * Postgres để trả về đúng dữ liệu vừa trả lượt trước. Nhân với số người trực
 * đang mở bàn làm việc thì đó là tải thật.
 *
 * Khi tab sáng trở lại thì gọi NGAY một lần chứ không chờ hết chu kỳ: người vừa
 * quay lại màn hình là người muốn biết ngay nhất, và bắt họ nhìn dữ liệu cũ
 * thêm 8 giây là đúng lúc họ mất niềm tin vào con số trên màn hình.
 *
 * `fn` được giữ trong ref: truyền một hàm mới mỗi lần dựng lại là chuyện bình
 * thường ở React, và nếu nó nằm trong mảng phụ thuộc thì bộ đếm bị dựng lại
 * liên tục và chu kỳ không bao giờ tới hạn.
 */
export function useVisiblePoll(fn: () => void, intervalMs: number, active = true) {
  const saved = useRef(fn);
  saved.current = fn;

  useEffect(() => {
    if (!active || intervalMs <= 0) return;

    let timer: ReturnType<typeof setInterval> | undefined;

    const start = () => {
      if (timer !== undefined) return;
      timer = setInterval(() => saved.current(), intervalMs);
    };
    const stop = () => {
      if (timer === undefined) return;
      clearInterval(timer);
      timer = undefined;
    };

    const onVisibility = () => {
      if (document.hidden) {
        stop();
      } else {
        saved.current();
        start();
      }
    };

    if (!document.hidden) start();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [intervalMs, active]);
}

export default useVisiblePoll;
