import { useEffect, useRef, useState } from "react";
import apiClient from "../api/axiosClient";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import { friendlyError } from "../lib/errors";
import { tr, useI18n } from "../i18n";
import {
  BellOffIcon,
  BoltIcon,
  ChartBarIcon,
  ChipIcon,
  GearIcon,
  HardDriveIcon,
  ServerIcon,
} from "../components/ui/Icons";

// ---------------------------------------------------------------------------
// Types — mirror backend app/monitoring.py :: collect_resources()
// ---------------------------------------------------------------------------
interface HostInfo {
  cpu_pct?: number;
  cpu_count?: number;
  cpu_per_core?: number[];
  ram_used_mb?: number;
  ram_total_mb?: number;
  ram_pct?: number;
  error?: string;
}
interface GpuProcess { pid: number; vram_mb: number }
interface GpuInfo {
  available: boolean;
  reason?: string;
  name?: string;
  util_pct?: number;
  vram_used_mb?: number;
  vram_total_mb?: number;
  vram_pct?: number;
  temp_c?: number;
  power_w?: number;
  processes?: GpuProcess[];
  age_s?: number;
}
interface TrainingInfo {
  active: boolean;
  job_id?: string;
  model_type?: string;
  current_epoch?: number;
  total_epochs?: number;
  started_at?: string;
}
interface RedisInfo {
  available: boolean;
  used_mb?: number;
  maxmemory_mb?: number;
  used_pct?: number;
}
interface DiskInfo {
  available: boolean;
  total_gb?: number;
  used_gb?: number;
  free_gb?: number;
  used_pct?: number;
  mount?: string;
  reason?: string;
}
interface ServiceAlloc {
  name: string;
  role: string;
  mem_limit_mb: number; // 0 => unlimited
  gpu: boolean;
  cpus?: number | null;      // hard CPU cap (usually null = shared)
  concurrency?: number | null;
}
interface ConfigInfo {
  available: boolean;
  source_file?: string;
  services?: ServiceAlloc[];
  total_alloc_mb?: number;
}
interface Alert {
  level: "critical" | "warning";
  message: string;
  /** Việc cần làm, tách khỏi `message` (chuyện đang xảy ra). */
  hint?: string;
  resource?: string;
}
interface ResourceReport {
  timestamp: string;
  host: HostInfo;
  gpu: GpuInfo;
  training: TrainingInfo;
  redis: RedisInfo;
  disk: DiskInfo;
  config: ConfigInfo;
  alerts: Alert[];
}

const REFRESH_MS = 5000;

// ---------------------------------------------------------------------------
// formatting + status color (4-step; always paired with a numeric label so
// identity is never color-alone)
// ---------------------------------------------------------------------------
const fmtMem = (mb?: number): string => {
  const v = mb || 0;
  return v >= 1000 ? `${(v / 1000).toFixed(1)} GB` : `${v.toFixed(0)} MB`;
};

/**
 * Phần ghi chú đứng sau một ô không có số liệu: vì sao không có.
 *
 * Ba khả năng, và chúng khác nhau về ý nghĩa: người ta đã TẮT cảnh báo (chủ ý,
 * không phải hỏng), máy chủ có nói lý do, hoặc không biết gì. Gộp chung thành
 * một dấu gạch ngang là bắt quản trị viên tự đoán xem đó là cấu hình hay sự cố.
 */
function noteFor(src: { ignored?: boolean; reason?: string } | null | undefined): string {
  if (src?.ignored) return ` (${tr("Đã tắt cảnh báo")})`;
  return src?.reason ? ` (${src.reason})` : "";
}

function statusBar(pct: number): string {
  if (pct >= 95) return "bg-red-500";
  if (pct >= 90) return "bg-orange-500";
  if (pct >= 75) return "bg-amber-400";
  return "bg-ctu-blue";
}

function Meter({ pct }: { pct: number }) {
  const clamped = Math.max(0, Math.min(100, pct || 0));
  return (
    <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
      <div
        className={`h-full rounded-full transition-all duration-700 ${statusBar(clamped)}`}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

// A big KPI tile: label · pct, then "used / total", then meter, then meta line.
function StatTile({
  label, pct, value, meta, muted,
}: {
  label: string; pct?: number; value: string; meta?: string; muted?: boolean;
}) {
  const showPct = typeof pct === "number";
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</span>
        {showPct && (
          <span className="text-xs font-bold tabular-nums text-slate-500">{(pct as number).toFixed(0)}%</span>
        )}
      </div>
      <div className={`text-3xl font-bold tabular-nums ${muted ? "text-slate-400" : "text-slate-900"}`}>
        {value}
      </div>
      {showPct ? <Meter pct={pct as number} /> : <div className="h-2" />}
      <div className="text-xs text-slate-500 min-h-[1rem]">{meta}</div>
    </div>
  );
}

export default function AdminResourcesPage() {
  const { t } = useI18n();
  const [data, setData] = useState<ResourceReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState(true);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      if (document.hidden) return; // pause polling when tab not visible
      try {
        const res = await apiClient.get<ResourceReport>("/api/v1/admin/resources");
        if (!cancelled) { setData(res.data); setError(null); }
      } catch (e: any) {
        if (!cancelled) setError(friendlyError(e, tr("Không tải được số liệu tài nguyên")));
      }
    };
    tick();
    if (live) timer.current = window.setInterval(tick, REFRESH_MS);
    const onVis = () => { if (!document.hidden && live) tick(); };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      cancelled = true;
      if (timer.current) window.clearInterval(timer.current);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [live]);

  const handleMuteAlert = async (resource: string) => {
    if (!window.confirm(t("Bạn có chắc muốn tắt báo động cho phần cứng này không? Hành động này sẽ đánh dấu lỗi thành bỏ qua."))) return;
    try {
      await apiClient.post("/api/v1/admin/config/ignore-hardware", { resource, ignore: true });
      // Fast refresh
      apiClient.get<ResourceReport>("/api/v1/admin/resources").then((res) => setData(res.data)).catch(console.error);
    } catch (err: any) {
      // `err.message` của axios là chuỗi kỹ thuật ("Request failed with status
      // code 500") — nó nói với người vận hành đúng bằng không, và nó là đường
      // rò cuối cùng còn lại trong tệp này.
      setError(friendlyError(err, tr("Không tắt được cảnh báo phần cứng")));
    }
  };

  const host = data?.host;
  const gpu = data?.gpu;
  const training = data?.training;
  const redis = data?.redis;
  const disk = data?.disk;
  const config = data?.config;
  const alerts = data?.alerts ?? [];

  const services = config?.services ?? [];
  const maxAlloc = services.reduce((m, s) => Math.max(m, s.mem_limit_mb), 0) || 1;
  const budgetMb = host?.ram_total_mb || 0;
  const allocMb = config?.total_alloc_mb || 0;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 mb-2 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-ctu-blue/10 flex items-center justify-center text-ctu-blue">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            {t("Giám sát tài nguyên")}
          </h2>
          <p className="text-slate-600">{t("Tình trạng CPU · RAM · GPU · Ổ cứng và cấu hình phân phối tài nguyên hệ thống")}</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-400 tabular-nums">
            {data ? new Date(data.timestamp).toLocaleTimeString() : "—"}
          </span>
          <button
            onClick={() => setLive((v) => !v)}
            className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium border transition-colors ${
              live ? "bg-ctu-blue/10 text-ctu-blue border-ctu-blue/20"
                   : "bg-slate-50 text-slate-600 border-slate-200"
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${live ? "bg-ctu-blue animate-pulse" : "bg-slate-400"}`} />
            {live ? t("Trực tiếp") : t("Tạm dừng")}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">{error}</div>
      )}

      {!data && !error ? (
        <div className="py-20">
          <LoadingSpinner size="lg" label={t("Đang tải số liệu tài nguyên...")} />
        </div>
      ) : (
        <>
          {/* Alerts */}
      {alerts.length > 0 ? (
        <div className="space-y-2">
          {alerts.map((a, i) => (
            <div key={i}
              className={`rounded-lg px-4 py-3 text-sm font-medium border flex items-center justify-between gap-4 ${
                a.level === "critical" ? "bg-red-50 border-red-200 text-red-700"
                                       : "bg-amber-50 border-amber-200 text-amber-700"}`}>
              {/* Câu cảnh báo tới từ máy chủ và mang chính câu tiếng Việt làm
                  khoá — đúng quy ước từ điển của dự án (docs/05-frontend/I18N.md §2), nên
                  `t()` dịch được nó y như chữ viết thẳng trong giao diện. */}
              <div className="flex items-start gap-2">
                <span
                  className={`mt-1.5 inline-block h-2.5 w-2.5 shrink-0 rounded-full ${
                    a.level === "critical" ? "bg-red-500" : "bg-amber-500"
                  }`}
                  aria-hidden="true"
                />
                <div>
                  <div>{t(a.message)}</div>
                  {/* Việc-cần-làm tách khỏi chuyện-đang-xảy-ra: dòng đầu nói hệ
                      thống đang thế nào, dòng sau mới nói phải làm gì. Gộp lại
                      thì phần cần đọc gấp bị chôn giữa câu hướng dẫn. */}
                  {a.hint ? (
                    <div className="mt-1 text-xs font-normal opacity-80">{t(a.hint)}</div>
                  ) : null}
                </div>
              </div>
              {a.resource && (
                <button
                  onClick={() => handleMuteAlert(a.resource as string)}
                  className="shrink-0 px-2.5 py-1.5 text-xs bg-white/60 hover:bg-white rounded-md border border-current/20 shadow-sm transition-colors opacity-90 hover:opacity-100 flex items-center gap-1.5"
                >
                  <BellOffIcon className="h-3.5 w-3.5"  aria-hidden="true" /> {t("Bỏ qua")}
                </button>
              )}
            </div>
          ))}
        </div>
      ) : data ? (
        <div className="rounded-lg px-4 py-3 text-sm font-medium border bg-ctu-blue/10 border-ctu-blue/20 text-ctu-blue flex items-center gap-2">
          <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full bg-emerald-500" aria-hidden="true" /> {t("Tài nguyên bình thường — không có cảnh báo")}
        </div>
      ) : null}

      {/* KPI row — current usage as used / total */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
        <StatTile
          label="CPU"
          pct={host?.cpu_pct}
          value={host?.error ? "—" : `${(host?.cpu_pct ?? 0).toFixed(0)}%`}
          meta={host?.error ? host.error : t("{n} nhân logic", { n: host?.cpu_count ?? "?" })}
        />
        <StatTile
          label={t("RAM hệ thống")}
          pct={host?.ram_pct}
          value={host?.error ? "—" : `${fmtMem(host?.ram_used_mb)} / ${fmtMem(host?.ram_total_mb)}`}
          meta={t("Bộ nhớ khả dụng cho Docker")}
        />
        <StatTile
          label={t("VRAM GPU (toàn máy)")}
          pct={gpu?.available ? gpu?.vram_pct : undefined}
          value={gpu?.available ? `${fmtMem(gpu?.vram_used_mb)} / ${fmtMem(gpu?.vram_total_mb)}` : "—"}
          meta={gpu?.available
            ? t("Gồm cả Windows · VOYA: {length} tiến trình", { length: gpu?.processes?.length ?? 0 })
            : t("Không có số liệu") + noteFor(gpu)}
          muted={!gpu?.available}
        />
        <StatTile
          label={t("Tải GPU")}
          pct={gpu?.available ? gpu?.util_pct : undefined}
          value={gpu?.available ? `${(gpu?.util_pct ?? 0).toFixed(0)}%` : "—"}
          meta={gpu?.available
            ? t("Nhiệt độ {nhiet}°C · Công suất {cong_suat} W · {n} tiến trình", {
                nhiet: gpu?.temp_c ?? "—",
                cong_suat: gpu?.power_w ?? "—",
                n: gpu?.processes?.length ?? 0,
              })
            : undefined}
          muted={!gpu?.available}
        />
        <StatTile
          label={t("Ổ cứng (Dataset)")}
          pct={disk?.available ? disk?.used_pct : undefined}
          value={disk?.available ? `${(disk?.used_gb ?? 0).toFixed(1)} / ${(disk?.total_gb ?? 0).toFixed(1)} GB` : "—"}
          meta={disk?.available
            ? t("Còn trống {p1} GB", { p1: (disk?.free_gb ?? 0).toFixed(1) })
            : t("Không đọc được") + noteFor(disk)}
          muted={!disk?.available}
        />
      </div>

      {/* Per-core CPU */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <ChipIcon className="h-5 w-5"  aria-hidden="true" />
            <h3 className="font-semibold text-slate-700">{t("CPU theo nhân")}</h3>
          </div>
          <span className="text-xs text-slate-400">
            {host?.cpu_count ?? "?"} nhân · dùng chung, không ghim cứng
          </span>
        </div>
        {host?.cpu_per_core && host.cpu_per_core.length > 0 ? (
          <div className="flex items-end gap-1.5 h-24">
            {host.cpu_per_core.map((c, i) => (
              <div key={i} className="flex-1 flex flex-col items-center gap-1" title={t("Nhân {i}: {p1}%", { i, p1: c.toFixed(0) })}>
                <div className="w-full h-full rounded-md bg-slate-100 overflow-hidden flex flex-col justify-end">
                  <div
                    className={`w-full rounded-md transition-all duration-500 ${statusBar(c)}`}
                    style={{ height: `${Math.max(3, c)}%` }}
                  />
                </div>
                <span className="text-[9px] text-slate-400 tabular-nums">{i}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500">{t("Chưa có dữ liệu CPU theo nhân")}</p>
        )}
      </div>

      {/* Training + Redis */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="font-semibold text-slate-700">{t("Huấn luyện")}</h3>
          </div>
          {training?.active ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-ctu-blue/10 text-ctu-blue">
                  <span className="w-1.5 h-1.5 rounded-full bg-ctu-blue animate-pulse" />{t("Đang chạy")}
                </span>
                <span className="text-xs font-mono text-slate-500">{training.model_type}</span>
                <span className="text-xs font-mono text-slate-400 truncate">{training.job_id}</span>
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-bold tabular-nums text-slate-900">
                  epoch {training.current_epoch ?? 0}<span className="text-slate-400">/{training.total_epochs ?? 0}</span>
                </span>
                <span className="text-xs text-slate-500 tabular-nums">
                  {training.total_epochs ? Math.round((100 * (training.current_epoch ?? 0)) / training.total_epochs) : 0}%
                </span>
              </div>
              <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                <div
                  className="h-full rounded-full bg-ctu-blue transition-all duration-700"
                  style={{ width: `${Math.max(0, Math.min(100, training.total_epochs ? (100 * (training.current_epoch ?? 0)) / training.total_epochs : 0))}%` }}
                />
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-sm text-slate-500 py-4">
              <span className="w-2 h-2 rounded-full bg-slate-300" />
              {t("Không có job đang chạy — GPU rảnh, tài nguyên đã trả về hệ thống")}
            </div>
          )}
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <div className="flex items-center gap-2 mb-4">
            <ServerIcon className="h-5 w-5"  aria-hidden="true" />
            <h3 className="font-semibold text-slate-700">Redis</h3>
          </div>
          {redis?.available ? (
            <div className="space-y-3">
              <div className="text-2xl font-bold tabular-nums text-slate-900">
                {fmtMem(redis.used_mb)}{redis.maxmemory_mb ? <span className="text-slate-400"> / {fmtMem(redis.maxmemory_mb)}</span> : null}
              </div>
              {redis.maxmemory_mb ? (
                <Meter pct={redis.used_pct ?? 0} />
              ) : (
                <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                  <div className="h-full rounded-full bg-ctu-blue/40" style={{ width: '100%' }} />
                </div>
              )}
              <div className="text-xs text-slate-500">{redis.maxmemory_mb ? `Cache / broker · ${(redis.used_pct ?? 0).toFixed(0)}%` : t("Không giới hạn — chỉ hiển thị dung lượng tuyệt đối")}</div>
            </div>
          ) : <p className="text-sm text-slate-500">—</p>}
        </div>
      </div>

      {/* Grafana Observability Card */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 rounded-xl shadow-lg border border-slate-700 p-6 text-white relative overflow-hidden group">
        <div className="absolute top-0 right-0 p-8 opacity-10">
          <svg className="w-32 h-32 transform group-hover:scale-110 transition-transform duration-700" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
        </div>
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <ChartBarIcon className="h-6 w-6"  aria-hidden="true" />
              <h3 className="text-xl font-bold">{t("Hệ thống giám sát chuyên sâu (Grafana)")}</h3>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-ctu-blue text-white tracking-wide uppercase">{t("Mới")}</span>
            </div>
            <p className="text-slate-300 text-sm max-w-2xl">
              {t("Nhật ký lỗi theo thời gian thực, dấu vết kiểm toán từng tác vụ, và biểu đồ lịch sử phần cứng (Prometheus).")}
            </p>
          </div>
          <div className="flex shrink-0 gap-3">
            <a 
              href="http://localhost:3000" 
              target="_blank" 
              rel="noreferrer"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-white text-slate-900 text-sm font-semibold hover:bg-slate-50 transition-colors shadow-sm"
            >
              {t("Mở Grafana Dashboard")} <span className="text-lg">↗</span>
            </a>
          </div>
        </div>
      </div>

      {/* Resource configuration & distribution */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-5">
          <div className="flex items-center gap-2">
            <GearIcon className="h-5 w-5"  aria-hidden="true" />
            <h3 className="font-semibold text-slate-700">{t("Cấu hình &amp; phân phối tài nguyên")}</h3>
          </div>
          {config?.available && (
            <span className="text-xs font-mono text-slate-400">{config.source_file}</span>
          )}
        </div>

        {/* Capacity chips */}
        <div className="flex flex-wrap gap-2 mb-5">
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-50 border border-slate-200 text-slate-600">
            <ChipIcon className="inline h-3.5 w-3.5 mr-1 -mt-0.5"  aria-hidden="true" /> {host?.cpu_count ?? "?"} nhân CPU
          </span>
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-50 border border-slate-200 text-slate-600">
            <HardDriveIcon className="inline h-3.5 w-3.5 mr-1 -mt-0.5"  aria-hidden="true" /> {fmtMem(budgetMb)} RAM
          </span>
          {gpu?.available && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-ctu-blue/5 border border-ctu-blue/20 text-ctu-blue">
              <BoltIcon className="inline h-3.5 w-3.5 mr-1 -mt-0.5"  aria-hidden="true" /> {gpu.name} · {fmtMem(gpu.vram_total_mb)} → trainer
            </span>
          )}
        </div>

        {config?.available && services.length > 0 ? (
          <>
            <div className="space-y-2.5">
              {services.map((s) => (
                <div key={s.name} className="flex items-center gap-3">
                  <div className="w-28 sm:w-40 shrink-0">
                    <div className="text-sm font-medium text-slate-800 truncate">{s.name}</div>
                    <div className="text-[11px] text-slate-400 truncate">
                      {t(s.role)}
                      {s.concurrency ? t(" · {concurrency} luồng", { concurrency: s.concurrency }) : ""}
                      {s.cpus ? ` · ${s.cpus} core` : ""}
                    </div>
                  </div>
                  <div className="flex-1 h-6 rounded-md bg-slate-100 overflow-hidden relative">
                    <div
                      className="h-full rounded-md bg-ctu-blue/80"
                      style={{ width: `${s.mem_limit_mb ? Math.max(4, (s.mem_limit_mb / maxAlloc) * 100) : 0}%` }}
                    />
                  </div>
                  {s.gpu && (
                    <span className="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-bold bg-ctu-blue/10 text-ctu-blue">GPU</span>
                  )}
                  <div className="w-16 shrink-0 text-right text-sm font-semibold tabular-nums text-slate-700">
                    {s.mem_limit_mb ? fmtMem(s.mem_limit_mb) : "∞"}
                  </div>
                </div>
              ))}
            </div>

            {/* Budget summary */}
            <div className="mt-5 pt-4 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2 text-sm">
              <span className="text-slate-500">
                Tổng phân bổ container:{" "}
                <span className="font-bold text-slate-800 tabular-nums">{fmtMem(allocMb)}</span>
                {budgetMb ? (
                  <span className="text-slate-400">
                    {" "}
                    {t("/ ngân sách {muc}", { muc: fmtMem(budgetMb) })}
                  </span>
                ) : null}
              </span>
              {budgetMb > 0 && (
                <span className={`font-bold tabular-nums ${allocMb > budgetMb ? "text-orange-600" : "text-slate-600"}`}>
                  {Math.round((100 * allocMb) / budgetMb)}% ngân sách
                </span>
              )}
            </div>
          </>
        ) : (
          <p className="text-sm text-slate-500">{t("Không đọc được cấu hình tài nguyên từ compose.")}</p>
        )}
      </div>
      </>
      )}
    </div>
  );
}
