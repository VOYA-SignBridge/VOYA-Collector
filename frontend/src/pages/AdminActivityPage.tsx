/**
 * Phiên hoạt động + nhật ký: nhãn trong `secEventBadge`, `AUDIT_FILTERS` và
 * `auditLabel` là KHOÁ từ điển, dịch tại chỗ dựng.
 *
 * @i18n-key-table
 */
import { useCallback, useEffect, useRef, useState } from "react";
import apiClient from "../api/axiosClient";
import { useToast } from "../hooks/useToast";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import BlockIpModal, { type BlockPayload } from "../components/BlockIpModal";
import { AlertTriangleIcon, ScrollTextIcon, ShieldIcon, XCircleIcon } from "../components/ui/Icons";
import { FOCUS_RING, toneClasses } from "../theme/status";
import { friendlyError } from "../lib/errors";
import { tr, useI18n } from "../i18n";

interface SecurityEvent {
  ts: number;
  action: string;
  actor: string;
  target: string;
  reason?: string;
  duration_seconds?: number;
  source?: string; // e.g. TRAINING_SYSTEM_FAILURE: dispatch | trainer_exit | ...
}

// Nhãn + màu cho mỗi loại sự kiện trong nhật ký bảo mật.
function secEventBadge(action: string): { label: string; cls: string } {
  switch (action) {
    case "block_ip":
      return { label: "Chặn IP", cls: "bg-red-100 text-red-700" };
    case "unblock_ip":
      return { label: "Bỏ chặn", cls: "bg-sky-100 text-sky-800" };
    case "TRAINING_SYSTEM_FAILURE":
      return { label: "Training lỗi hệ thống", cls: "bg-red-100 text-red-700" };
    default:
      return { label: "Ngắt phiên", cls: "bg-amber-100 text-amber-700" };
  }
}

// ---------------------------------------------------------------------------
// Nhật ký kiểm toán BỀN — mirror backend app/audit.py :: record()
//
// Khác bảng "Nhật ký bảo mật" ở trên, vốn đọc từ một danh sách Redis cắt còn
// 500 mục trên một instance chạy `volatile-lru`: bảng này nằm trong Postgres,
// không bị đuổi, và giữ `ip_hash` đối chiếu được giữa các hành động.
//
// KHÔNG nằm trong vòng poll 3 giây. Đây là bản ghi lịch sử, không phải bảng
// theo dõi trực tiếp; hỏi lại mỗi ba giây là bắt Postgres quét một bảng chỉ
// tăng, để hiển thị dữ liệu gần như không đổi.
// ---------------------------------------------------------------------------
interface AuditRow {
  audit_id: number;
  created_at: string;
  tenant_id: string | null;
  actor_user_id: string | null;
  actor_label: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  detail: Record<string, unknown> | null;
  ip_hash: string | null;
}

// Mỗi tiền tố mà máy chủ thật sự ghi ra đều phải có một nút ở đây. Thiếu nút
// thì hành động ấy không biến mất — nó vẫn nằm dưới "Tất cả" — nhưng nó không
// LỌC RA được, và ở một bảng chỉ dài thêm theo thời gian thì "không lọc ra
// được" và "không tìm thấy" là cùng một thứ đối với người đang cần nó.
const AUDIT_FILTERS: { label: string; prefix: string }[] = [
  { label: "Tất cả", prefix: "" },
  { label: "An ninh", prefix: "security." },
  { label: "Dữ liệu", prefix: "data." },
  { label: "Tổ chức", prefix: "tenant." },
  { label: "Từ vựng", prefix: "vocabulary." },
  { label: "Pháp lý", prefix: "legal." },
  { label: "Tài khoản", prefix: "account." },
  { label: "Nâng quyền", prefix: "sudo." },
  { label: "Cấu hình", prefix: "settings." },
];

// `data.class.purge` → "Xoá vĩnh viễn nhãn". Chỉ đặt tên cho những hành động
// không hồi được; phần còn lại hiện nguyên mã hành động, vì một nhãn tiếng
// Việt đoán mò còn khó tra hơn chuỗi gốc.
function auditLabel(action: string): { text: string; cls: string } {
  if (action.endsWith(".purge") || action.endsWith(".purge.bulk"))
    return { text: action, cls: "bg-red-100 text-red-700" };
  if (action.startsWith("sudo.") || action.startsWith("settings."))
    return { text: action, cls: "bg-amber-100 text-amber-700" };
  if (action.startsWith("security."))
    return { text: action, cls: "bg-sky-100 text-sky-700" };
  // Gộp phương ngữ đổi nhãn mẫu của người khác; gỡ thành viên cắt quyền xem
  // chính dữ liệu họ đóng góp. Cả hai không có nút hoàn tác, nên chúng đứng
  // cùng bậc với `purge` chứ không phải bậc "ghi chú".
  if (action === "vocabulary.dialect.merged" || action === "tenant.member_removed")
    return { text: action, cls: "bg-red-100 text-red-700" };
  if (action.startsWith("tenant.") || action.startsWith("vocabulary."))
    return { text: action, cls: "bg-violet-100 text-violet-700" };
  return { text: action, cls: "bg-slate-100 text-slate-600" };
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

// Hàm mức module → `tr`. Chuỗi nó trả về KHÔNG tự dựng lại khi đổi ngôn ngữ,
// nhưng bảng này tự làm mới mỗi 3 giây nên chữ theo kịp trong một nhịp.
const ago = (s: number): string => {
  if (s < 60) return tr("{n}s trước", { n: Math.round(s) });
  if (s < 3600) return tr("{n} phút trước", { n: Math.round(s / 60) });
  return tr("{n} giờ trước", { n: Math.round(s / 3600) });
};

export default function AdminActivityPage() {
  const { t } = useI18n();
  const [data, setData] = useState<ActivityReport | null>(null);
  const [secLog, setSecLog] = useState<SecurityEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [blockTarget, setBlockTarget] = useState<string | null>(null);
  const [audit, setAudit] = useState<AuditRow[]>([]);
  const [auditPrefix, setAuditPrefix] = useState("");
  const [auditBusy, setAuditBusy] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);
  const { toast } = useToast();

  // Số thứ tự lượt tải nhật ký gần nhất — xem `fetchAudit`.
  const auditRun = useRef(0);

  const fetchAudit = useCallback(async (prefix: string) => {
    // Bấm nhanh qua các bộ lọc thì nhiều request cùng bay. Chúng không về theo
    // thứ tự gửi, nên nếu không canh, một phản hồi CŨ về sau sẽ ghi đè phản hồi
    // của bộ lọc đang chọn — bảng hiện dữ liệu của bộ lọc khác với nút đang
    // sáng, và người đọc không có cách nào biết.
    const run = ++auditRun.current;
    setAuditBusy(true);
    try {
      const res = await apiClient.get<{ events: AuditRow[] }>(
        "/api/v1/admin/audit-log",
        { params: { limit: 150, action_prefix: prefix } },
      );
      if (run !== auditRun.current) return;
      setAudit(res.data.events || []);
      setAuditError(null);
    } catch (e: any) {
      if (run !== auditRun.current) return;
      setAuditError(friendlyError(e, "Không tải được nhật ký kiểm toán"));
    } finally {
      if (run === auditRun.current) setAuditBusy(false);
    }
  }, []);

  const fetchReport = useCallback(async () => {
    try {
      const rep = await apiClient.get<ActivityReport>("/api/v1/admin/activity");
      setData(rep.data);
      setSecLog(rep.data.security_log || []);
      setError(null);
    } catch (e: any) {
      setError(friendlyError(e, "Không tải được dữ liệu phiên hoạt động"));
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

  // Tách khỏi vòng poll ở trên: chỉ nạp khi vào trang và khi đổi bộ lọc.
  useEffect(() => { fetchAudit(auditPrefix); }, [auditPrefix, fetchAudit]);

  const doBlock = async (ip: string, payload: BlockPayload) => {
    setBusy(ip);
    try {
      await apiClient.post("/api/v1/admin/block-ip", {
        ip, reason: payload.reason, duration_seconds: payload.duration_seconds,
      });
      toast.success(t("Đã chặn {ip}", { ip }));
      await fetchReport();
    } catch (e: any) {
      toast.error(friendlyError(e, "Chặn IP thất bại"));
    } finally { setBusy(null); }
  };

  const unblockIp = async (ip: string) => {
    setBusy(ip);
    try {
      await apiClient.post("/api/v1/admin/unblock-ip", { ip });
      toast.success(t("Đã bỏ chặn {ip}", { ip }));
      await fetchReport();
    } catch (e: any) {
      toast.error(friendlyError(e, "Bỏ chặn thất bại"));
    } finally { setBusy(null); }
  };

  const forceLogout = async (userId: string, name: string) => {
    const reason = window.prompt(t("Lý do ngắt phiên \"{name}\" (sẽ hiển thị cho người dùng):", { name }), "Vi phạm quy định sử dụng");
    if (reason === null) return; // cancelled
    setBusy(userId);
    try {
      await apiClient.post("/api/v1/admin/force-logout", { user_id: userId, reason });
      toast.success(t("Đã đăng xuất {name}", { name }));
      await fetchReport();
    } catch (e: any) {
      toast.error(friendlyError(e, "Đăng xuất thất bại"));
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
            {t("Phiên hoạt động")}
          </h2>
          <p className="text-slate-600">{t("Người dùng đang kết nối, vị trí, mức sử dụng và công cụ xử lý bất thường")}</p>
        </div>
        <button
          onClick={() => setLive((v) => !v)}
          className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium border transition-colors ${
            live ? toneClasses("success", "soft") : toneClasses("neutral", "soft")
          }`}
        >
          <span className={`w-2 h-2 rounded-full ${live ? "bg-sky-600 animate-pulse motion-reduce:animate-none" : "bg-slate-400"}`} />
          {live ? t("Trực tiếp") : t("Tạm dừng")}
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">{error}</div>
      )}

      {!data && !error ? (
        <div className="py-20">
          <LoadingSpinner size="lg" label={t("Đang tải phiên hoạt động...")} />
        </div>
      ) : (
        <>
          {/* Summary */}
      <div className="flex flex-wrap gap-2">
        <Chip label={t("Đang online")} value={data?.online_count ?? 0} tone="bg-sky-50 border-sky-200 text-sky-800" />
        <Chip label={t("Tổng phiên")} value={sessions.length} />
        <Chip label={t("IP bị chặn")} value={blocked.length} tone={blocked.length ? "bg-red-50 border-red-200 text-red-700" : undefined} />
        <Chip label={t("Định vị GeoIP")} value={data?.geoip_enabled ? t("Bật") : t("Chưa có DB")} tone={data?.geoip_enabled ? "bg-ctu-blue/5 border-ctu-blue/20 text-ctu-blue" : "bg-amber-50 border-amber-200 text-amber-700"} />
      </div>

      {/* Anomaly alerts */}
      {anomalies.length > 0 && (
        <div className="space-y-2">
          {anomalies.map((a, i) => (
            <div key={i}
              className={`rounded-lg px-4 py-3 text-sm font-medium border flex items-center justify-between gap-3 ${
                a.level === "critical" ? "bg-red-50 border-red-200 text-red-700" : "bg-amber-50 border-amber-200 text-amber-700"}`}>
              <span className="flex items-center gap-2">
                {a.level === "critical"
                  ? <XCircleIcon className="w-4 h-4 shrink-0 text-red-600" aria-hidden="true" />
                  : <AlertTriangleIcon className="w-4 h-4 shrink-0 text-amber-600" aria-hidden="true" />}
                {a.message}
              </span>
              <button onClick={() => setBlockTarget(a.ip)} disabled={busy === a.ip}
                className="shrink-0 px-2.5 py-1 rounded-md text-xs font-semibold bg-white/70 border border-current hover:bg-white transition-colors disabled:opacity-50">
                {t("Chặn IP")}
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
                <th className="py-3 px-4 font-semibold">{t("Người dùng")}</th>
                <th className="py-3 px-4 font-semibold">IP</th>
                <th className="py-3 px-4 font-semibold">{t("Vị trí")}</th>
                <th className="py-3 px-4 font-semibold">{t("Trình duyệt")}</th>
                <th className="py-3 px-4 font-semibold">{t("Hoạt động")}</th>
                <th className="py-3 px-4 font-semibold text-right">req/5p</th>
                <th className="py-3 px-4 font-semibold text-right">{t("Thao tác")}</th>
              </tr>
            </thead>
            <tbody>
              {!data ? (
                <tr><td colSpan={7} className="py-8 text-center text-slate-400">{t("Đang tải…")}</td></tr>
              ) : sessions.length === 0 ? (
                <tr><td colSpan={7} className="py-8 text-center text-slate-400">{t("Chưa có phiên nào đang hoạt động.")}</td></tr>
              ) : (
                sessions.map((s) => (
                  <tr key={s.ip} className={`border-b border-slate-100 hover:bg-slate-50 transition-colors ${s.blocked ? "bg-red-50/40" : ""}`}>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${s.online ? "bg-sky-600" : "bg-slate-300"}`} title={s.online ? "Online" : "Offline"} />
                        {s.username ? (
                          <span className="font-medium text-slate-800">
                            {s.username}
                            {s.is_admin && <span className="ml-1.5 px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-700">{t("QUẢN TRỊ")}</span>}
                          </span>
                        ) : (
                          <span className="text-slate-400 italic">{t("Khách")}</span>
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
                          className="inline-flex items-center gap-1 text-[11px] font-medium text-sky-700 hover:underline"
                          title={`GPS ${s.precise.lat.toFixed(5)}, ${s.precise.lon.toFixed(5)} (±${Math.round(s.precise.accuracy)}m)`}
                        >
                          GPS ±{Math.round(s.precise.accuracy)}m · bản đồ
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
                            {t("Ngắt phiên")}
                          </button>
                        )}
                        {s.blocked ? (
                          <button onClick={() => unblockIp(s.ip)} disabled={busy === s.ip}
                            className={`px-2 py-1 rounded-md text-xs font-medium border transition-colors disabled:opacity-50 ${toneClasses("success", "outline")} ${FOCUS_RING}`}>
                            {t("Bỏ chặn")}
                          </button>
                        ) : (
                          <button onClick={() => setBlockTarget(s.ip)} disabled={busy === s.ip || s.geo?.local}
                            title={s.geo?.local ? t("Không thể chặn IP nội bộ") : t("Chặn IP này")}
                            className="px-2 py-1 rounded-md text-xs font-medium bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
                            {t("Chặn IP")}
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
          <h3 className="font-semibold text-slate-700 mb-3 flex items-center gap-2"><XCircleIcon className="w-4 h-4 text-red-600" aria-hidden="true" />
            {t("IP đang bị chặn ({n})", { n: blocked.length })}
          </h3>
          <div className="space-y-2">
            {blocked.map((b) => (
              <div key={b.ip} className="flex items-center justify-between gap-3 px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-sm">
                <div className="min-w-0">
                  <span className="font-mono font-medium text-red-700">{b.ip}</span>
                  {b.reason && <span className="text-red-600"> — {b.reason}</span>}
                  <span className="text-red-400 text-xs ml-1">
                    ({b.by ? t("bởi {ai}", { ai: b.by }) : "admin"}
                    {b.until
                      ? ` · ${t("đến {khi}", { khi: new Date(b.until * 1000).toLocaleString("vi-VN") })}`
                      : ` · ${t("vĩnh viễn")}`})
                  </span>
                </div>
                <button onClick={() => unblockIp(b.ip)} disabled={busy === b.ip}
                  className={`shrink-0 px-2 py-1 rounded-md text-xs font-medium border disabled:opacity-50 ${toneClasses("success", "outline")} ${FOCUS_RING}`}>
                  {t("Bỏ chặn")}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Security audit log */}
      {secLog.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <h3 className="font-semibold text-slate-700 mb-3 flex items-center gap-2"><ShieldIcon className="w-4 h-4 text-slate-500" aria-hidden="true" />{t("Nhật ký bảo mật")}</h3>
          <div className="space-y-1.5 max-h-72 overflow-y-auto">
            {secLog.map((ev, i) => {
              const badge = secEventBadge(ev.action);
              return (
                <div key={i} className="flex items-center gap-2 text-xs text-slate-600 border-b border-slate-50 pb-1.5">
                  <span className="text-slate-400 tabular-nums shrink-0">{new Date(ev.ts * 1000).toLocaleString("vi-VN")}</span>
                  <span className={`px-1.5 py-0.5 rounded font-semibold shrink-0 ${badge.cls}`}>{t(badge.label)}</span>
                  {ev.source && <span className="font-mono text-slate-400 shrink-0">[{ev.source}]</span>}
                  <span className="font-mono text-slate-500 shrink-0 truncate max-w-[160px]">{ev.target}</span>
                  {ev.reason && <span className="truncate">— {ev.reason}</span>}
                  <span className="text-slate-400 ml-auto shrink-0">
                    {t("bởi {ai}", { ai: ev.actor || "?" })}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
      {/* Nhật ký kiểm toán bền (Postgres) */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <h3 className="font-semibold text-slate-700 flex items-center gap-2">
            <ScrollTextIcon className="w-4 h-4 text-ctu-blue" aria-hidden="true" />
            {t("Nhật ký kiểm toán")}
          </h3>
          <span className="text-xs text-slate-400">
            {t("lưu bền trong cơ sở dữ liệu — không bị đuổi như bảng phía trên")}
          </span>
          <div className="ml-auto flex items-center gap-1">
            {AUDIT_FILTERS.map((f) => (
              <button
                key={f.prefix}
                onClick={() => setAuditPrefix(f.prefix)}
                className={`px-2 py-1 rounded-md text-xs font-medium border ${
                  auditPrefix === f.prefix
                    ? "bg-slate-800 text-white border-slate-800"
                    : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                }`}
              >
                {t(f.label)}
              </button>
            ))}
            <button
              onClick={() => fetchAudit(auditPrefix)}
              disabled={auditBusy}
              className="px-2 py-1 rounded-md text-xs font-medium bg-slate-50 text-slate-600 border border-slate-200 hover:bg-slate-100 disabled:opacity-50"
            >
              {auditBusy ? t("Đang tải…") : t("Tải lại")}
            </button>
          </div>
        </div>

        {auditError && (
          <p className="text-xs text-red-600 mb-2">{auditError}</p>
        )}

        {audit.length === 0 && !auditBusy && !auditError ? (
          <p className="text-xs text-slate-400">{t("Chưa có dòng nào.")}</p>
        ) : (
          <div className="max-h-96 overflow-y-auto overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-slate-400 text-left">
                <tr className="border-b border-slate-100">
                  <th className="py-1.5 pr-3 font-medium">{t("Thời điểm")}</th>
                  <th className="py-1.5 pr-3 font-medium">{t("Hành động")}</th>
                  <th className="py-1.5 pr-3 font-medium">{t("Người thực hiện")}</th>
                  <th className="py-1.5 pr-3 font-medium">{t("Đối tượng")}</th>
                  <th className="py-1.5 pr-3 font-medium" title={t("Băm HMAC của địa chỉ IP: đối chiếu được giữa các dòng, không đảo ngược ra IP")}>
                    {t("Nguồn")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {audit.map((row) => {
                  const badge = auditLabel(row.action);
                  return (
                    <tr key={row.audit_id} className="border-b border-slate-50 align-top">
                      <td className="py-1.5 pr-3 text-slate-400 tabular-nums whitespace-nowrap">
                        {new Date(row.created_at).toLocaleString("vi-VN")}
                      </td>
                      <td className="py-1.5 pr-3">
                        <span className={`px-1.5 py-0.5 rounded font-mono font-semibold ${badge.cls}`}>
                          {badge.text}
                        </span>
                      </td>
                      <td className="py-1.5 pr-3 text-slate-600 whitespace-nowrap">
                        {row.actor_label || <span className="text-slate-300">{t("hệ thống")}</span>}
                      </td>
                      <td className="py-1.5 pr-3 text-slate-500 font-mono truncate max-w-[220px]"
                          title={row.target_id || ""}>
                        {row.target_id || "—"}
                      </td>
                      <td className="py-1.5 pr-3 text-slate-300 font-mono whitespace-nowrap">
                        {row.ip_hash ? row.ip_hash.slice(0, 8) : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
      </>
      )}

      <BlockIpModal ip={blockTarget} open={!!blockTarget} onClose={() => setBlockTarget(null)} onConfirm={doBlock} />
    </div>
  );
}
