/**
 * Chuông thông báo trên thanh điều hướng.
 *
 * **Chỉ hỏi số, không hỏi danh sách.** `GET /notifications/unread-count` trả về
 * một số nguyên; gọi `GET /notifications` theo chu kỳ để hiển thị một chữ số là
 * tải về vài chục kilobyte mỗi lượt cho không.
 *
 * **Chu kỳ 60 giây, và dừng khi tab bị ẩn.** Một tab để quên qua đêm sẽ gọi 480
 * lượt vô ích; `document.hidden` cắt đúng phần đó. Khi tab sáng trở lại thì hỏi
 * ngay một lần chứ không chờ hết chu kỳ — người vừa quay lại là người muốn biết
 * ngay nhất.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { fetchUnreadCount } from "../api/account";
import { BellIcon } from "./ui/Icons";
import { useI18n } from "../i18n";

const POLL_MS = 60_000;

export default function NotificationBell() {
  const { t } = useI18n();
  const [unread, setUnread] = useState(0);
  const timer = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      setUnread(await fetchUnreadCount());
    } catch {
      // Im lặng có chủ ý: cái chuông là thông tin phụ. Một biểu ngữ lỗi đỏ vì
      // không đếm được thông báo sẽ che mất lỗi thật của việc người dùng đang làm.
    }
  }, []);

  useEffect(() => {
    void refresh();

    const tick = () => {
      if (!document.hidden) void refresh();
    };
    timer.current = window.setInterval(tick, POLL_MS);

    const onVisible = () => {
      if (!document.hidden) void refresh();
    };
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      if (timer.current !== null) window.clearInterval(timer.current);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [refresh]);

  // Nhãn mang cả con số: trình đọc màn hình đọc `aria-label`, không đọc chấm
  // tròn đỏ. Nếu chỉ để t("Thông báo") thì người khiếm thị không biết có gì mới.
  const label =
    unread > 0 ? t("Thông báo, {n} chưa đọc", { n: unread }) : t("Thông báo");

  return (
    <Link
      to="/notifications"
      aria-label={label}
      title={label}
      className="relative inline-flex h-9 w-9 items-center justify-center rounded-lg text-slate-600 transition hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
    >
      <BellIcon className="h-5 w-5" />
      {unread > 0 && (
        <span
          aria-hidden="true"
          className="absolute -right-0.5 -top-0.5 inline-flex min-w-[1.15rem] items-center justify-center rounded-full bg-red-600 px-1 text-[0.7rem] font-semibold leading-4 text-white"
        >
          {unread > 99 ? "99+" : unread}
        </span>
      )}
    </Link>
  );
}
