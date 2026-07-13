import { useEffect, useState } from "react";
import apiClient from "../api/axiosClient";

/**
 * Shows a pending admin warning to the logged-in user (one-off, must acknowledge).
 * Rendered only for authenticated users (Layout gates it). Friendly + professional.
 */
export default function WarningBanner() {
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    apiClient
      .get("/api/v1/auth/my-notice")
      .then((res) => {
        const w = res.data?.warning;
        if (!cancelled && w?.message) setMsg(String(w.message));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  if (!msg) return null;

  const dismiss = async () => {
    setBusy(true);
    try {
      await apiClient.post("/api/v1/auth/my-notice/ack");
    } catch {
      /* best-effort */
    } finally {
      setMsg(null);
    }
  };

  return (
    <div className="fixed inset-0 z-[9997] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-2xl border border-amber-200 p-8 text-center">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-amber-100 flex items-center justify-center text-3xl">⚠️</div>
        <h2 className="text-xl font-bold text-slate-900 mb-2">Thông báo từ quản trị viên</h2>
        <div className="rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-sm px-4 py-3 mb-5 text-left whitespace-pre-wrap">
          {msg}
        </div>
        <p className="text-xs text-slate-400 mb-5">
          Vui lòng lưu ý nội dung trên để tiếp tục sử dụng dịch vụ một cách tốt nhất. Xin cảm ơn.
        </p>
        <button
          onClick={dismiss}
          disabled={busy}
          className="px-6 py-2.5 rounded-lg bg-ctu-blue text-white font-medium hover:bg-ctu-navy transition-colors disabled:opacity-50"
        >
          Tôi đã hiểu
        </button>
      </div>
    </div>
  );
}
