import { useEffect, useState } from "react";
import { fetchLoginHistory, type LoginEvent } from "../../api/auth";
import { useI18n } from "../../i18n";
import LoadingSpinner from "../ui/LoadingSpinner";
import { formatWhen } from "./DevicesSection";

/**
 * Đăng nhập gần đây: để người dùng tự nhận ra một lần vào mà họ không làm.
 * Chỉ hiện thiết bị, thời điểm và (nếu máy chủ định vị được) nơi đăng nhập;
 * địa chỉ IP không được lưu.
 */
export default function LoginHistorySection() {
  const { t, lang } = useI18n();
  const [events, setEvents] = useState<LoginEvent[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchLoginHistory()
      .then((e) => !cancelled && setEvents(e))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <h3 className="text-lg font-semibold text-slate-900">{t("Đăng nhập gần đây")}</h3>
      <p className="mt-1 text-sm text-slate-600">
        {t("Mười lần đăng nhập gần nhất vào tài khoản của bạn.")}
      </p>

      {events === null && !failed && <div className="mt-4"><LoadingSpinner size="sm" label={t("Đang tải…")} /></div>}
      {failed && <p role="alert" className="mt-4 text-sm text-red-700">{t("Không tải được lịch sử đăng nhập.")}</p>}
      {events && events.length === 0 && (
        <p className="mt-4 text-sm text-slate-500">{t("Chưa có lần đăng nhập nào được ghi lại.")}</p>
      )}
      {events && events.length > 0 && (
        <ul className="mt-4 divide-y divide-slate-100">
          {events.map((e, i) => (
            <li key={`${e.at}-${i}`} className="py-2.5 text-sm">
              <span className="font-medium text-slate-900">{e.device}</span>
              {e.place && <span className="text-slate-600"> · {e.place}</span>}
              <span className="block text-xs text-slate-500">{formatWhen(e.at, lang)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
