import { useCallback, useEffect, useRef, useState } from "react";
import apiClient from "../api/axiosClient";
import { useToast } from "../hooks/useToast";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import BlockIpModal, { type BlockPayload } from "../components/BlockIpModal";

interface SecurityEvent {
  ts: number;
  action: string;
  actor: string;
  target: string;
  reason?: string;
  duration_seconds?: number;
}

// ---------------------------------------------------------------------------
// Types — mirror backend app/activity.py :: activity_report()
// ---------------------------------------------------------------------------
interface GeoData {
  local?: boolean;
  country?: string;
  country_code?: string;
  city?: string;
  lat?: number;
  lon?: number;
}
interface Session {
  ip: string;
  user_id?: string | null;
  username?: string | null;
  is_admin?: boolean;
  browser: string;
  user_agent: string;
  last_path: string;
  seconds_ago: number;
  online: boolean;
  req_window: number;
  location: string;
  isp?: string | null;
  precise?: { lat: number; lon: number; accuracy: number; age_s: number } | null;
  geo: GeoData;
  blocked: boolean;
}
interface Anomaly {
  level: "warning" | "critical";
  ip: string;
  location: string;
  message: string;
}
interface Blocked {
  ip: string;
  by: string;
  at?: number;
  reason?: string;
  until?: number; // epoch seconds, 0 = permanent
  ttl?: number;   // remaining seconds
}
interface ActivityReport {
  sessions: Session[];
  online_count: number;
  anomalies: Anomaly[];
  blocked: Blocked[];
  security_log?: SecurityEvent[];
  geoip_enabled: boolean;
}

const REFRESH_MS = 3000;

const ago = (s: number): string => {
  if (s < 60) return `${Math.round(s)}s trước`;
  if (s < 3600) return `${Math.round(s / 60)} phút trước`;
  return `${Math.round(s / 3600)} giờ trước`;
};

export default function AdminActivityPage() {
  const [data, setData] = useState<ActivityReport | null>(null);
  const [secLog, setSecLog] = useState<SecurityEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [blockTarget, setBlockTarget] = useState<string | null>(null);
  const timer = useRef<number | null>(null);
  const { toast } = useToast();

  const fetchReport = useCallback(async () => {
    try {
      const rep = await apiClient.get<ActivityReport>("/api/v1/admin/activity");
      setData(rep.data);
      setSecLog(rep.data.security_log || []);
      setError(null);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Không tải được dữ liệu phiên hoạt động");
    }
  }, []);

  useEffect(() => {
    // Only poll while the tab is visible → zero background requests when the
    // admin switches away, and an instant refresh when they come back.
    const tick = () => { if (!document.hidden) fetchReport(); };
    tick();
    if (live) timer.current = window.setInterval(tick, REFRESH_MS);
    const onVis = () => { if (!document.hidden && live) fetchReport(); };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      if (timer.current) window.clearInterval(timer.current);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [live, fetchReport]);

  const doBlock = async (ip: string, payload: BlockPayload) => {
    setBusy(ip);
    try {
      await apiClient.post("/api/v1/admin/block-ip", {
        ip, reason: payload.reason, duration_seconds: payload.duration_seconds,
      });
      toast.success(`Đã chặn ${ip}`);
      await fetchReport();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Chặn IP thất bại");
    } finally { setBusy(null); }
  };

  const unblockIp = async (ip: string) => {
    setBusy(ip);
    try {
      await apiClient.post("/api/v1/admin/unblock-ip", { ip });
      toast.success(`Đã bỏ chặn ${ip}`);
      await fetchReport();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Bỏ chặn thất bại");
    } finally { setBusy(null); }
  };

  const forceLogout = async (userId: string, name: string) => {
    const reason = window.prompt(`Lý do ngắt phiên "${name}" (sẽ hiển thị cho người dùng):`, "Vi phạm quy định sử dụng");
    if (reason === null) return; // cancelled
    setBusy(userId);
    try {
      await apiClient.post("/api/v1/admin/force-logout", { user_id: userId, reason });
      toast.success(`Đã đăng xuất ${name}`);
      await fetchReport();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Đăng xuất thất bại");
    } finally { setBusy(null); }
  };

  const sessions = data?.sessions ?? [];
  const anomalies = data?.anomalies ?? [];
  const blocked = data?.blocked ?? [];

  const Chip = ({ label, value, tone }: { label: string; value: string | number; tone?: string }) => (
    <div className={`px-3 py-1.5 rounded-lg text-xs font-medium border ${tone || "bg-slate-50 border-slate-200 text-slate-600"}`}>
      {label}: <span className="font-bold">{value}</span>
    </div>
  );

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 mb-2 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-ctu-blue/10 flex items-center justify-center text-ctu-blue">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m6-3.13a4 4 0 10-4-4 4 4 0 004 4zm6 0a3 3 0 10-3-3" />
              </svg>
            </div>
            Phiên hoạt động
          </h2>
          <p className="text-slate-600">Người dùng đang kết nối, vị trí, mức sử dụng và công cụ xử lý bất thường</p>
        </div>
        <button
          onClick={() => setLive((v) => !v)}
          className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium border transition-colors ${
            live ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-600 border-slate-200"
          }`}
        >
          <span className={`w-2 h-2 rounded-full ${live ? "bg-emerald-500 animate-pulse" : "bg-slate-400"}`} />
          {live ? "Trực tiếp" : "Tạm dừng"}
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">{error}</div>
      )}

      {!data && !error ? (
        <div className="py-20">
          <LoadingSpinner size="lg" label="Đang tải phiên hoạt động..." />
        </div>
      ) : (
        <>
          {/* Summary */}
      <div className="flex flex-wrap gap-2">
        <Chip label="Đang online" value={data?.online_count ?? 0} tone="bg-emerald-50 border-emerald-200 text-emerald-700" />
        <Chip label="Tổng phiên" value={sessions.length} />
        <Chip label="IP bị chặn" value={blocked.length} tone={blocked.length ? "bg-red-50 border-red-200 text-red-700" : undefined} />
        <Chip label="Định vị GeoIP" value={data?.geoip_enabled ? "Bật" : "Chưa có DB"} tone={data?.geoip_enabled ? "bg-ctu-blue/5 border-ctu-blue/20 text-ctu-blue" : "bg-amber-50 border-amber-200 text-amber-700"} />
      </div>

      {/* Anomaly alerts */}
      {anomalies.length > 0 && (
        <div className="space-y-2">
          {anomalies.map((a, i) => (
            <div key={i}
              className={`rounded-lg px-4 py-3 text-sm font-medium border flex items-center justify-between gap-3 ${
                a.level === "critical" ? "bg-red-50 border-red-200 text-red-700" : "bg-amber-50 border-amber-200 text-amber-700"}`}>
              <span className="flex items-center gap-2">
                <span>{a.level === "critical" ? "🔴" : "🟠"}</span>{a.message}
              </span>
              <button onClick={() => setBlockTarget(a.ip)} disabled={busy === a.ip}
                className="shrink-0 px-2.5 py-1 rounded-md text-xs font-semibold bg-white/70 border border-current hover:bg-white transition-colors disabled:opacity-50">
                Chặn IP
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Sessions table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-600">
                <th className="py-3 px-4 font-semibold">Người dùng</th>
                <th className="py-3 px-4 font-semibold">IP</th>
                <th className="py-3 px-4 font-semibold">Vị trí</th>
                <th className="py-3 px-4 font-semibold">Trình duyệt</th>
                <th className="py-3 px-4 font-semibold">Hoạt động</th>
                <th className="py-3 px-4 font-semibold text-right">req/5p</th>
                <th className="py-3 px-4 font-semibold text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {!data ? (
                <tr><td colSpan={7} className="py-8 text-center text-slate-400">Đang tải…</td></tr>
              ) : sessions.length === 0 ? (
                <tr><td colSpan={7} className="py-8 text-center text-slate-400">Chưa có phiên nào đang hoạt động.</td></tr>
              ) : (
                sessions.map((s) => (
                  <tr key={s.ip} className={`border-b border-slate-100 hover:bg-slate-50 transition-colors ${s.blocked ? "bg-red-50/40" : ""}`}>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${s.online ? "bg-emerald-500" : "bg-slate-300"}`} title={s.online ? "Online" : "Offline"} />
                        {s.username ? (
                          <span className="font-medium text-slate-800">
                            {s.username}
                            {s.is_admin && <span className="ml-1.5 px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-700">ADMIN</span>}
                          </span>
                        ) : (
                          <span className="text-slate-400 italic">Khách</span>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4 font-mono text-xs text-slate-600">{s.ip}</td>
                    <td className="py-3 px-4">
                      <div className="text-slate-600">{s.location}</div>
                      {s.isp && <div className="text-[11px] text-slate-400 truncate max-w-[150px]" title={s.isp}>{s.isp}</div>}
                      {s.precise && (
                        <a
                          href={`https://www.openstreetmap.org/?mlat=${s.precise.lat}&mlon=${s.precise.lon}#map=17/${s.precise.lat}/${s.precise.lon}`}
                          target="_blank" rel="noreferrer"
                          className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600 hover:underline"
                          title={`GPS ${s.precise.lat.toFixed(5)}, ${s.precise.lon.toFixed(5)} (±${Math.round(s.precise.accuracy)}m)`}
                        >
                          📍 GPS ±{Math.round(s.precise.accuracy)}m · bản đồ
                        </a>
                      )}
                    </td>
                    <td className="py-3 px-4 text-slate-600" title={s.user_agent}>{s.browser}</td>
                    <td className="py-3 px-4 text-slate-500">
                      <div className="font-mono text-xs truncate max-w-[160px]" title={s.last_path}>{s.last_path}</div>
                      <div className="text-[11px] text-slate-400">{ago(s.seconds_ago)}</div>
                    </td>
                    <td className="py-3 px-4 text-right tabular-nums font-semibold">
                      <span className={s.req_window >= 400 ? "text-orange-600" : "text-slate-600"}>{s.req_window}</span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-end gap-1.5">
                        {s.user_id && !s.is_admin && (
                          <button onClick={() => forceLogout(s.user_id!, s.username || s.ip)} disabled={busy === s.user_id}
                            className="px-2 py-1 rounded-md text-xs font-medium bg-slate-100 text-slate-600 hover:bg-slate-200 transition-colors disabled:opacity-50">
                            Ngắt phiên
                          </button>
                        )}
                        {s.blocked ? (
                          <button onClick={() => unblockIp(s.ip)} disabled={busy === s.ip}
                            className="px-2 py-1 rounded-md text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 transition-colors disabled:opacity-50">
                            Bỏ chặn
                          </button>
                        ) : (
                          <button onClick={() => setBlockTarget(s.ip)} disabled={busy === s.ip || s.geo?.local}
                            title={s.geo?.local ? "Không thể chặn IP nội bộ" : "Chặn IP này"}
                            className="px-2 py-1 rounded-md text-xs font-medium bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
                            Chặn IP
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Blocked IPs */}
      {blocked.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <h3 className="font-semibold text-slate-700 mb-3 flex items-center gap-2">🚫 IP đang bị chặn ({blocked.length})</h3>
          <div className="space-y-2">
            {blocked.map((b) => (
              <div key={b.ip} className="flex items-center justify-between gap-3 px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-sm">
                <div className="min-w-0">
                  <span className="font-mono font-medium text-red-700">{b.ip}</span>
                  {b.reason && <span className="text-red-600"> — {b.reason}</span>}
                  <span className="text-red-400 text-xs ml-1">
                    ({b.by ? `bởi ${b.by}` : "admin"}
                    {b.until ? ` · đến ${new Date(b.until * 1000).toLocaleString("vi-VN")}` : " · vĩnh viễn"})
                  </span>
                </div>
                <button onClick={() => unblockIp(b.ip)} disabled={busy === b.ip}
                  className="shrink-0 px-2 py-1 rounded-md text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 disabled:opacity-50">
                  Bỏ chặn
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Security audit log */}
      {secLog.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <h3 className="font-semibold text-slate-700 mb-3 flex items-center gap-2">🛡️ Nhật ký bảo mật</h3>
          <div className="space-y-1.5 max-h-72 overflow-y-auto">
            {secLog.map((ev, i) => (
              <div key={i} className="flex items-center gap-2 text-xs text-slate-600 border-b border-slate-50 pb-1.5">
                <span className="text-slate-400 tabular-nums shrink-0">{new Date(ev.ts * 1000).toLocaleString("vi-VN")}</span>
                <span className={`px-1.5 py-0.5 rounded font-semibold shrink-0 ${
                  ev.action === "block_ip" ? "bg-red-100 text-red-700"
                    : ev.action === "unblock_ip" ? "bg-emerald-100 text-emerald-700"
                      : "bg-amber-100 text-amber-700"}`}>
                  {ev.action === "block_ip" ? "Chặn IP" : ev.action === "unblock_ip" ? "Bỏ chặn" : "Ngắt phiên"}
                </span>
                <span className="font-mono text-slate-500 shrink-0 truncate max-w-[160px]">{ev.target}</span>
                {ev.reason && <span className="truncate">— {ev.reason}</span>}
                <span className="text-slate-400 ml-auto shrink-0">bởi {ev.actor || "?"}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      </>
      )}

      <BlockIpModal ip={blockTarget} open={!!blockTarget} onClose={() => setBlockTarget(null)} onConfirm={doBlock} />
    </div>
  );
}
