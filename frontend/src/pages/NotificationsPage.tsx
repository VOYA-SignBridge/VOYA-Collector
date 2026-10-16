/**
 * Trung tâm thông báo — `/notifications`.
 *
 * Một quyết định đáng nêu: **mở một thông báo có liên kết thì đánh dấu đã đọc
 * NGAY**, không chờ người dùng bấm nút riêng. Nút "đánh dấu đã đọc" tách rời là
 * thứ không ai bấm, và hệ quả là số trên chuông không bao giờ về 0 — rồi người
 * dùng học cách bỏ qua nó hoàn toàn.
 */

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  fetchNotifications,
  KIND_LABEL,
  markAllRead,
  markRead,
  type AppNotification,
  type Severity,
} from "../api/account";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import EmptyState from "../components/ui/EmptyState";
import PageHeader from "../components/ui/PageHeader";
import { CheckIcon } from "../components/ui/Icons";
import { useI18n } from "../i18n";

const TONE: Record<Severity, "success" | "warning" | "danger" | "neutral"> = {
  info: "neutral",
  success: "success",
  warning: "warning",
  critical: "danger",
};

function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("vi-VN", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function NotificationsPage() {
  const { t } = useI18n();
  const [items, setItems] = useState<AppNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchNotifications({ unreadOnly, limit: 50 });
      setItems(data.items);
      setUnread(data.unread);
      setError("");
    } catch {
      setError(t("Không tải được thông báo. Vui lòng thử lại."));
    } finally {
      setLoading(false);
    }
  }, [unreadOnly]);

  useEffect(() => {
    void load();
  }, [load]);

  const openOne = async (n: AppNotification) => {
    if (n.read_at) return;
    // Cập nhật tại chỗ trước khi gọi mạng: người dùng vừa bấm thì màn hình phải
    // phản hồi ngay. Nếu lệnh hỏng, lượt tải sau sẽ dựng lại trạng thái đúng.
    setItems((prev) =>
      prev.map((x) =>
        x.notification_id === n.notification_id
          ? { ...x, read_at: new Date().toISOString() }
          : x,
      ),
    );
    setUnread((u) => Math.max(0, u - 1));
    try {
      await markRead([n.notification_id]);
    } catch {
      void load();
    }
  };

  const readAll = async () => {
    try {
      await markAllRead();
      await load();
    } catch {
      setError(t("Không đánh dấu được. Vui lòng thử lại."));
    }
  };

  return (
    <div className="mx-auto w-full max-w-3xl space-y-4 p-4 sm:p-6">
      <PageHeader
        title={t("Thông báo")}
        subtitle={unread > 0 ? t("{unread} thông báo chưa đọc", { unread }) : t("Bạn đã đọc hết")}
      />

      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant={unreadOnly ? "primary" : "secondary"}
          size="sm"
          onClick={() => setUnreadOnly((v) => !v)}
          aria-pressed={unreadOnly}
        >
          {t("Chỉ chưa đọc")}
        </Button>
        {unread > 0 && (
          <Button variant="secondary" size="sm" onClick={readAll}>
            <CheckIcon className="h-4 w-4" />
            {t("Đánh dấu tất cả đã đọc")}
          </Button>
        )}
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {error}
        </div>
      )}

      {loading && <p className="text-sm text-slate-500">{t("Đang tải…")}</p>}

      {!loading && items.length === 0 && (
        <EmptyState
          title={unreadOnly ? t("Không có thông báo chưa đọc") : t("Chưa có thông báo nào")}
          description={t("Khi có việc cần bạn biết — gói dịch vụ, bảo mật, huấn luyện — nó sẽ xuất hiện ở đây.")}
        />
      )}

      <ul className="space-y-2">
        {items.map((n) => {
          const body = (
            <article
              className={`rounded-xl border p-4 transition ${
                n.read_at
                  ? "border-slate-200 bg-white"
                  : "border-ctu-blue/30 bg-ctu-blue/5"
              }`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={TONE[n.severity]} size="sm">
                  {t(KIND_LABEL[n.kind]) ?? n.kind}
                </Badge>
                {!n.read_at && (
                  <span className="text-xs font-medium text-ctu-blue">{t("Mới")}</span>
                )}
                <time
                  dateTime={n.created_at}
                  className="ml-auto text-xs text-slate-500"
                >
                  {formatWhen(n.created_at)}
                </time>
              </div>
              <h3 className="mt-2 font-semibold text-slate-900">{n.title}</h3>
              {n.body && (
                <p className="mt-1 text-sm text-slate-600">{n.body}</p>
              )}
            </article>
          );

          return (
            <li key={n.notification_id}>
              {n.link ? (
                <Link
                  to={n.link}
                  onClick={() => void openOne(n)}
                  className="block rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
                >
                  {body}
                </Link>
              ) : (
                <button
                  type="button"
                  onClick={() => void openOne(n)}
                  className="block w-full rounded-xl text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
                >
                  {body}
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
