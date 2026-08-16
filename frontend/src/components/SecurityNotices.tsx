import { useEffect, useState } from "react";

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
export default function SecurityNotices() {
  const [blocked, setBlocked] = useState<BlockedInfo | null>(null);
  const [logout, setLogout] = useState<string | null>(null);
  const [idle, setIdle] = useState(false);

  useEffect(() => {
    const onBlocked = (e: Event) => setBlocked((e as CustomEvent).detail || {});
    const onLogout = (e: Event) =>
      setLogout((e as CustomEvent).detail?.message || "Phiên đã bị đăng xuất bởi quản trị viên");
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
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-amber-100 flex items-center justify-center text-3xl">🙏</div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">Truy cập tạm thời bị hạn chế</h2>
          <p className="text-slate-600 mb-4">
            Rất tiếc, kết nối của bạn hiện đang bị tạm ngưng bởi quản trị viên. Chúng tôi mong bạn thông cảm.
          </p>
          <div className="rounded-lg bg-slate-50 border border-slate-200 text-slate-700 text-sm px-4 py-3 mb-4 text-left">
            <div><span className="font-semibold">Lý do:</span> {blocked.reason || "Không rõ"}</div>
            <div className="mt-1">
              <span className="font-semibold">Thời hạn:</span>{" "}
              {until ? `đến ${until.toLocaleString("vi-VN")}` : "cho đến khi được gỡ"}
            </div>
          </div>
          <p className="text-sm text-slate-500 mb-2">Nếu bạn cho rằng đây là nhầm lẫn, vui lòng liên hệ để được hỗ trợ:</p>
          {blocked.contact ? (
            <a
              href={`mailto:${blocked.contact}?subject=${encodeURIComponent("Khiếu nại hạn chế truy cập")}&body=${encodeURIComponent("Xin chào, truy cập của tôi bị hạn chế với lý do: " + (blocked.reason || "") + ". Tôi mong được xem xét lại. Cảm ơn.")}`}
              className="inline-flex items-center gap-1.5 mb-5 text-ctu-blue font-medium hover:underline"
            >
              {blocked.contact}
            </a>
          ) : (
            <p className="text-sm text-slate-400 mb-5">quản trị viên hệ thống</p>
          )}
          <div>
            <button
              onClick={() => window.location.reload()}
              className="px-5 py-2.5 rounded-lg bg-slate-100 text-slate-700 font-medium hover:bg-slate-200 transition-colors"
            >
              Thử lại
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
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-amber-100 flex items-center justify-center text-3xl">🔔</div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">Phiên đã kết thúc</h2>
          <p className="text-slate-600 mb-6">{logout}</p>
          <button
            onClick={() => { window.location.href = "/login"; }}
            className="px-5 py-2.5 rounded-lg bg-ctu-blue text-white font-medium hover:bg-ctu-navy transition-colors"
          >
            Đăng nhập lại
          </button>
        </div>
      </div>
    );
  }

  if (idle) {
    return (
      <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-slate-900/70 backdrop-blur-sm p-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-2xl border border-slate-200 p-8 text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-slate-100 flex items-center justify-center text-3xl">😴</div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">Phiên đăng nhập đã tạm nghỉ</h2>
          <p className="text-slate-600 mb-2">
            Bạn đã không hoạt động trong một khoảng thời gian, nên chúng tôi tự động đăng xuất để bảo vệ tài khoản của bạn.
          </p>
          <p className="text-sm text-slate-500 mb-6">
            Đây là thao tác bảo mật thông thường — dữ liệu của bạn vẫn an toàn. Vui lòng đăng nhập lại để tiếp tục.
          </p>
          <button
            onClick={() => { window.location.href = "/login"; }}
            className="px-5 py-2.5 rounded-lg bg-ctu-blue text-white font-medium hover:bg-ctu-navy transition-colors"
          >
            Đăng nhập lại
          </button>
        </div>
      </div>
    );
  }

  return null;
}
