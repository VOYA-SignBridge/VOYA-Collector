import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useI18n } from "../i18n";

/**
 * Friendly, professional 403 shown when a signed-in but non-admin user reaches
 * an admin-only route (instead of leaking the admin shell). Offers a "go home"
 * button and auto-returns to the dashboard after 5 seconds.
 */
export default function NotAuthorizedPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [count, setCount] = useState(5);

  useEffect(() => {
    const tick = setInterval(() => setCount((c) => Math.max(0, c - 1)), 1000);
    const go = setTimeout(() => navigate("/", { replace: true }), 5000);
    return () => {
      clearInterval(tick);
      clearTimeout(go);
    };
  }, [navigate]);

  return (
    <div className="min-h-[70vh] flex items-center justify-center p-4 animate-fade-in">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl border border-slate-200 p-8 text-center">
        <div className="w-16 h-16 mx-auto mb-5 rounded-full bg-amber-50 flex items-center justify-center text-amber-500">
          <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 3 4.5 6v5.5c0 4.3 3.2 7.6 7.5 9 4.3-1.4 7.5-4.7 7.5-9V6L12 3Z" />
            <path d="M12 9v4" />
            <circle cx="12" cy="16.3" r="0.6" fill="currentColor" stroke="none" />
          </svg>
        </div>

        <h1 className="text-2xl font-bold text-slate-900 mb-2">{t("Khu vực dành cho quản trị viên")}</h1>
        <p className="text-slate-600 mb-1">
          {t("Tài khoản của bạn hiện không có quyền truy cập trang này.")}
        </p>
        <p className="text-sm text-slate-400 mb-6">
          {t("Nếu bạn cho rằng đây là nhầm lẫn, vui lòng liên hệ quản trị viên để được hỗ trợ.")}
        </p>

        <button
          onClick={() => navigate("/", { replace: true })}
          className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-ctu-blue text-white font-medium hover:bg-ctu-navy transition-colors"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 11.5 12 4l8 7.5" />
            <path d="M6 10v9.5a1 1 0 0 0 1 1h3.5v-6h3v6H17a1 1 0 0 0 1-1V10" />
          </svg>
          {t("Về trang chủ")}
        </button>

        <p className="mt-5 text-xs text-slate-400">
          {t("Tự động chuyển về trang chủ sau")} <span className="font-semibold text-slate-500">{count}</span> {t("giây…")}
        </p>
      </div>
    </div>
  );
}
