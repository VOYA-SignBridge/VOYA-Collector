/**
 * Chuông thông báo trên thanh điều hướng — nút, và một BẢNG XỔ XUỐNG.
 *
 * Vì sao không còn là một `<Link>`
 * ---------------------------------
 * Bản trước bấm vào là rời trang, sang `/notifications`. Nghe thì gọn, nhưng nó
 * bắt người dùng trả giá trước khi biết có đáng hay không: đang dở một biểu mẫu
 * huấn luyện, tò mò xem cái chấm đỏ là gì, và mất chỗ đang đứng để đọc một dòng
 * "phiên đăng nhập mới". Cái chuông trả lời một câu hỏi liếc-qua ("có gì mới
 * không?"), nên nó phải trả lời tại chỗ.
 *
 * Nên: bảng xổ xuống với vài mục gần nhất, và MỘT nút "Xem tất cả" cho ai muốn
 * đi tiếp. Trang `/notifications` vẫn còn nguyên — nó là nơi lọc, phân trang,
 * đánh dấu hàng loạt; bảng này cố tình không làm mấy việc đó.
 *
 * Vẫn chỉ hỏi SỐ theo chu kỳ
 * ---------------------------
 * `GET /notifications/unread-count` chạy nền mỗi 60 giây; danh sách chỉ được
 * tải khi bảng thật sự mở ra. Đảo lại — hỏi cả danh sách theo chu kỳ để bảng
 * lúc nào cũng sẵn — là tải vài chục kilobyte mỗi phút cho một bảng mà đa số
 * lượt tải không ai mở.
 *
 * **Chu kỳ dừng khi tab bị ẩn.** Một tab để quên qua đêm sẽ gọi 480 lượt vô
 * ích; `document.hidden` cắt đúng phần đó. Khi tab sáng trở lại thì hỏi ngay
 * một lần chứ không chờ hết chu kỳ — người vừa quay lại là người muốn biết ngay
 * nhất.
 *
 * @i18n-key-table — bốn chuỗi trong `relativeWhen` là KHOÁ từ điển, dịch bằng
 * `t(when.key, when.vars)` ở chỗ dựng. Chúng phải là khoá chứ không phải câu đã
 * ghép: ghép ở đây là ghép theo ngữ pháp tiếng Việt, và bản tiếng Anh sẽ nhận
 * một chuỗi đóng cứng không sửa được.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  fetchNotifications,
  fetchUnreadCount,
  markRead,
  KIND_LABEL,
  type AppNotification,
} from "../api/account";
import { BellIcon } from "./ui/Icons";
import { useI18n } from "../i18n";

const POLL_MS = 60_000;

/** Số mục trong bảng xổ. Đủ để liếc, không đủ để thành một trang thứ hai. */
const PEEK = 6;

/** Viền trái theo mức độ. Màu KHÔNG phải tín hiệu duy nhất — mỗi mục còn có
 *  nhãn loại bằng chữ, vì người mù màu đọc bảng này bằng chữ. */
const TONE: Record<string, string> = {
  info: "border-l-slate-300",
  success: "border-l-emerald-400",
  warning: "border-l-amber-400",
  critical: "border-l-red-500",
};

/**
 * Khoảng cách thời gian, trả về KHOÁ + biến chứ không trả về câu đã ghép.
 *
 * Ghép câu ở đây là ghép bằng tiếng Việt, và bản tiếng Anh sẽ nhận một chuỗi đã
 * đóng cứng. Trả về cặp (khoá, biến) để chỗ dựng gọi `t()` — cùng lý do vì sao
 * `<Trans>` tồn tại.
 */
function relativeWhen(iso: string): { key: string; vars?: Record<string, number> } {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return { key: "" };
  const mins = Math.round((Date.now() - d.getTime()) / 60_000);
  if (mins < 1) return { key: "vừa xong" };
  if (mins < 60) return { key: "{n} phút trước", vars: { n: mins } };
  const hours = Math.round(mins / 60);
  if (hours < 24) return { key: "{n} giờ trước", vars: { n: hours } };
  return { key: "{n} ngày trước", vars: { n: Math.round(hours / 24) } };
}

export default function NotificationBell() {
  const { t } = useI18n();
  const navigate = useNavigate();

  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<AppNotification[] | null>(null);
  const [loading, setLoading] = useState(false);

  const timer = useRef<number | null>(null);
  const boxRef = useRef<HTMLDivElement | null>(null);

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

  // Đóng khi bấm ra ngoài hoặc bấm Esc. Cả hai đều cần: chuột đóng bằng cách
  // bấm ra ngoài, bàn phím thì không có "ngoài" nào để bấm.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (!next) return;

    setLoading(true);
    try {
      const data = await fetchNotifications({ limit: PEEK });
      setItems(data.items);
      setUnread(data.unread);
    } catch {
      // `items = []` chứ không để `null`: `null` nghĩa là "chưa tải", và bảng
      // sẽ đứng mãi ở "Đang tải…" sau một lượt hỏng.
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  /** Mở một mục: đánh dấu đã đọc, rồi đi tới đích của nó nếu có. */
  const openItem = async (n: AppNotification) => {
    setOpen(false);
    if (!n.read_at) {
      // Không `await` trước khi điều hướng: người dùng đã bấm, họ muốn tới nơi.
      // Một lượt POST chậm không được phép giữ họ lại trên trang cũ.
      void markRead([n.notification_id]).then(refresh);
      setUnread((u) => Math.max(0, u - 1));
    }
    navigate(n.link || "/notifications");
  };

  const label =
    unread > 0 ? t("Thông báo, {n} chưa đọc", { n: unread }) : t("Thông báo");

  return (
    <div ref={boxRef} className="relative">
      <button
        type="button"
        onClick={() => void toggle()}
        aria-label={label}
        title={label}
        aria-expanded={open}
        aria-haspopup="dialog"
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
      </button>

      {open ? (
        <div
          role="dialog"
          aria-label={t("Thông báo")}
          /* Neo bên PHẢI: cái chuông nằm gần mép phải của header, nên một bảng
             neo trái sẽ tràn khỏi màn hình trên máy hẹp. `max-w-[calc(100vw-1rem)]`
             giữ nó trong khung ngay cả trên điện thoại. */
          className="absolute right-0 z-50 mt-2 w-80 max-w-[calc(100vw-1rem)] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl"
        >
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
            <span className="text-sm font-semibold text-slate-900">
              {t("Thông báo")}
            </span>
            {unread > 0 ? (
              <span className="rounded-full bg-red-50 px-2 py-0.5 text-[11px] font-semibold text-red-600">
                {t("{n} chưa đọc", { n: unread })}
              </span>
            ) : null}
          </div>

          <div className="max-h-80 overflow-y-auto">
            {loading && items === null ? (
              <p className="px-4 py-6 text-center text-sm text-slate-500">
                {t("Đang tải…")}
              </p>
            ) : !items || items.length === 0 ? (
              <p className="px-4 py-6 text-center text-sm text-slate-500">
                {t("Bạn đã đọc hết")}
              </p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {items.map((n) => {
                  const when = relativeWhen(n.created_at);
                  return (
                  <li key={n.notification_id}>
                    <button
                      type="button"
                      onClick={() => void openItem(n)}
                      className={`w-full border-l-4 px-4 py-3 text-left transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ctu-blue ${
                        TONE[n.severity] ?? TONE.info
                      } ${n.read_at ? "" : "bg-sky-50/40"}`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
                          {t(KIND_LABEL[n.kind] ?? n.kind)}
                        </span>
                        <span className="ml-auto shrink-0 text-[11px] text-slate-400">
                          {t(when.key, when.vars)}
                        </span>
                      </div>
                      <p
                        className={`mt-1 truncate text-sm ${
                          n.read_at ? "text-slate-700" : "font-semibold text-slate-900"
                        }`}
                      >
                        {n.title}
                      </p>
                      {n.body ? (
                        <p className="mt-0.5 truncate text-xs text-slate-500">{n.body}</p>
                      ) : null}
                    </button>
                  </li>
                  );
                })}
              </ul>
            )}
          </div>

          {/* Lối đi tiếp, luôn hiện — kể cả khi bảng rỗng. Người vào đây tìm
              "lịch sử thông báo" cần thấy đường tới nó ngay cả lúc không có gì
              mới, và đó chính là lúc họ hay tìm nhất. */}
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              navigate("/notifications");
            }}
            className="block w-full border-t border-slate-100 bg-slate-50 px-4 py-2.5 text-center text-sm font-semibold text-ctu-blue transition hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ctu-blue"
          >
            {t("Xem chi tiết")}
          </button>
        </div>
      ) : null}
    </div>
  );
}
