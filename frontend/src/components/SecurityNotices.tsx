import { useEffect, useState } from "react";
import { BellIcon, HandsPrayIcon, MailIcon, MoonIcon } from "./ui/Icons";
import { useI18n } from "../i18n";

interface BlockedInfo {
  reason?: string;
  until?: number; // epoch seconds, 0 = permanent
  ttl?: number;
  contact?: string;
}

/**
 * Global listener for admin security actions against the current client:
 *  - "voya:blocked"     → full-screen block notice (reason + expiry)
 *  - "voya:forcelogout" → session-ended notice with a re-login button
 *  - "voya:idle-logout" → friendly "signed out for inactivity" notice
 * Events are dispatched by the axios interceptor on 403(blocked)/401(force)
 * and by the inactivity timer (useIdleLogout).
 */
/**
 * Send the browser to the app's OWN root under its base path (e.g. "/voya/"),
 * never the domain root. A hard `location.href = "/login"` is origin-relative
 * and drops the "/voya" prefix — it would land on https://host/login, outside
 * the app. Reading VITE_BASE_PATH (injected into window.__ENV__ by the nginx
 * entrypoint) keeps the redirect inside the deployment and shows the logged-out
 * landing page, which is exactly where an ended session should return.
 */
function goToAppHome() {
  const base =
    (window as { __ENV__?: { VITE_BASE_PATH?: string } }).__ENV__?.VITE_BASE_PATH || "/";
  window.location.href = base.endsWith("/") ? base : `${base}/`;
}

export default function SecurityNotices() {
  const { t } = useI18n();
  const [blocked, setBlocked] = useState<BlockedInfo | null>(null);
  const [logout, setLogout] = useState<string | null>(null);
  const [idle, setIdle] = useState(false);

  useEffect(() => {
    const onBlocked = (e: Event) => setBlocked((e as CustomEvent).detail || {});
    const onLogout = (e: Event) =>
      setLogout((e as CustomEvent).detail?.message || t("Phiên đã bị đăng xuất bởi quản trị viên"));
    const onIdle = () => setIdle(true);
    window.addEventListener("voya:blocked", onBlocked as EventListener);
    window.addEventListener("voya:forcelogout", onLogout as EventListener);
    window.addEventListener("voya:idle-logout", onIdle as EventListener);
    return () => {
      window.removeEventListener("voya:blocked", onBlocked as EventListener);
      window.removeEventListener("voya:forcelogout", onLogout as EventListener);
      window.removeEventListener("voya:idle-logout", onIdle as EventListener);
    };
  }, []);

  if (blocked) {
    const until = blocked.until && blocked.until > 0 ? new Date(blocked.until * 1000) : null;
    return (
      <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-slate-900/70 backdrop-blur-sm p-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-2xl border border-slate-200 p-8 text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-amber-100 flex items-center justify-center text-amber-700">
            <HandsPrayIcon className="h-8 w-8"  aria-hidden="true" />
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">{t("Truy cập tạm thời bị hạn chế")}</h2>
          <p className="text-slate-600 mb-4">
            {t("Rất tiếc, kết nối của bạn hiện đang bị tạm ngưng bởi quản trị viên. Chúng tôi mong bạn thông cảm.")}
          </p>
          <div className="rounded-lg bg-slate-50 border border-slate-200 text-slate-700 text-sm px-4 py-3 mb-4 text-left">
            <div><span className="font-semibold">{t("Lý do:")}</span> {blocked.reason || t("Không rõ")}</div>
            <div className="mt-1">
              <span className="font-semibold">{t("Thời hạn:")}</span>{" "}
              {until
                ? t("đến {khi}", { khi: until.toLocaleString("vi-VN") })
                : t("cho đến khi được gỡ")}
            </div>
          </div>
          <p className="text-sm text-slate-500 mb-2">{t("Nếu bạn cho rằng đây là nhầm lẫn, vui lòng liên hệ để được hỗ trợ:")}</p>
          {blocked.contact ? (
            <a
              href={`mailto:${blocked.contact}?subject=${encodeURIComponent(t("Khiếu nại hạn chế truy cập"))}&body=${encodeURIComponent(t("Xin chào, truy cập của tôi bị hạn chế với lý do: {ly_do}. Tôi mong được xem xét lại. Cảm ơn.", { ly_do: blocked.reason || "" }))}`}
              className="inline-flex items-center gap-1.5 mb-5 text-ctu-blue font-medium hover:underline"
            >
              <MailIcon className="inline h-4 w-4 mr-1 -mt-0.5"  aria-hidden="true" /> {blocked.contact}
            </a>
          ) : (
            <p className="text-sm text-slate-400 mb-5">{t("quản trị viên hệ thống")}</p>
          )}
          <div>
            <button
              onClick={() => window.location.reload()}
              className="px-5 py-2.5 rounded-lg bg-slate-100 text-slate-700 font-medium hover:bg-slate-200 transition-colors"
            >
              {t("Thử lại")}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (logout) {
    return (
      <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-slate-900/70 backdrop-blur-sm p-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-2xl border border-slate-200 p-8 text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-amber-100 flex items-center justify-center text-amber-700">
            <BellIcon className="h-8 w-8"  aria-hidden="true" />
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">{t("Phiên đã kết thúc")}</h2>
          <p className="text-slate-600 mb-6">{logout}</p>
          <button
            onClick={goToAppHome}
            className="px-5 py-2.5 rounded-lg bg-ctu-blue text-white font-medium hover:bg-ctu-navy transition-colors"
          >
            {t("Đăng nhập lại")}
          </button>
        </div>
      </div>
    );
  }

  if (idle) {
    return (
      <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-slate-900/70 backdrop-blur-sm p-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-2xl border border-slate-200 p-8 text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-slate-100 flex items-center justify-center text-slate-500">
            <MoonIcon className="h-8 w-8"  aria-hidden="true" />
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">{t("Phiên đăng nhập đã tạm nghỉ")}</h2>
          <p className="text-slate-600 mb-2">
            {t("Bạn đã không hoạt động trong một khoảng thời gian, nên chúng tôi tự động đăng xuất để bảo vệ tài khoản của bạn.")}
          </p>
          <p className="text-sm text-slate-500 mb-6">
            {t("Đây là thao tác bảo mật thông thường — dữ liệu của bạn vẫn an toàn. Vui lòng đăng nhập lại để tiếp tục.")}
          </p>
          <button
            onClick={goToAppHome}
            className="px-5 py-2.5 rounded-lg bg-ctu-blue text-white font-medium hover:bg-ctu-navy transition-colors"
          >
            {t("Đăng nhập lại")}
          </button>
        </div>
      </div>
    );
  }

  return null;
}
