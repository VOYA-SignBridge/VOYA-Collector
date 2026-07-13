import { useEffect, useRef, useState } from "react";
import apiClient from "../api/axiosClient";

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
interface Alert { level: "critical" | "warning"; message: string }
interface ResourceReport {
  timestamp: string;
  host: HostInfo;
  gpu: GpuInfo;
  training: TrainingInfo;
  redis: RedisInfo;
  config: ConfigInfo;
  alerts: Alert[];
}

const REFRESH_MS = 3000;

// ---------------------------------------------------------------------------
// formatting + status color (4-step; always paired with a numeric label so
// identity is never color-alone)
// ---------------------------------------------------------------------------
const fmtMem = (mb?: number): string => {
  const v = mb || 0;
  return v >= 1000 ? `${(v / 1000).toFixed(1)} GB` : `${v.toFixed(0)} MB`;
};

function statusBar(pct: number): string {
  if (pct >= 95) return "bg-red-500";
  if (pct >= 90) return "bg-orange-500";
  if (pct >= 75) return "bg-amber-400";
  return "bg-emerald-500";
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
        if (!cancelled) setError(e?.response?.data?.detail || "Không tải được số liệu tài nguyên");
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

  const host = data?.host;
  const gpu = data?.gpu;
  const training = data?.training;
  const redis = data?.redis;
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
            Giám sát tài nguyên
          </h2>
          <p className="text-slate-600">Tình trạng CPU · RAM · GPU và cấu hình phân phối tài nguyên hệ thống</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-400 tabular-nums">
            {data ? new Date(data.timestamp).toLocaleTimeString() : "—"}
          </span>
          <button
            onClick={() => setLive((v) => !v)}
            className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium border transition-colors ${
              live ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                   : "bg-slate-50 text-slate-600 border-slate-200"
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${live ? "bg-emerald-500 animate-pulse" : "bg-slate-400"}`} />
            {live ? "Trực tiếp" : "Tạm dừng"}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">{error}</div>
      )}

      {/* Alerts */}
      {alerts.length > 0 ? (
        <div className="space-y-2">
          {alerts.map((a, i) => (
            <div key={i}
              className={`rounded-lg px-4 py-3 text-sm font-medium border flex items-center gap-2 ${
                a.level === "critical" ? "bg-red-50 border-red-200 text-red-700"
                                       : "bg-amber-50 border-amber-200 text-amber-700"}`}>
              <span>{a.level === "critical" ? "🔴" : "🟠"}</span>{a.message}
            </div>
          ))}
        </div>
      ) : data ? (
        <div className="rounded-lg px-4 py-3 text-sm font-medium border bg-emerald-50 border-emerald-200 text-emerald-700 flex items-center gap-2">
          <span>🟢</span> Tài nguyên bình thường — không có cảnh báo
        </div>
      ) : null}

      {/* KPI row — current usage as used / total */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatTile
          label="CPU"
          pct={host?.cpu_pct}
          value={host?.error ? "—" : `${(host?.cpu_pct ?? 0).toFixed(0)}%`}
          meta={host?.error ? host.error : `${host?.cpu_count ?? "?"} nhân logic`}
        />
        <StatTile
          label="RAM hệ thống"
          pct={host?.ram_pct}
          value={host?.error ? "—" : `${fmtMem(host?.ram_used_mb)} / ${fmtMem(host?.ram_total_mb)}`}
          meta="Bộ nhớ khả dụng cho Docker"
        />
        <StatTile
          label="VRAM GPU (toàn máy)"
          pct={gpu?.available ? gpu?.vram_pct : undefined}
          value={gpu?.available ? `${fmtMem(gpu?.vram_used_mb)} / ${fmtMem(gpu?.vram_total_mb)}` : "—"}
          meta={gpu?.available
            ? `Gồm cả Windows · VOYA: ${gpu?.processes?.length ?? 0} tiến trình`
            : `Không có số liệu${gpu?.reason ? ` (${gpu.reason})` : ""}`}
          muted={!gpu?.available}
        />
        <StatTile
          label="Tải GPU"
          pct={gpu?.available ? gpu?.util_pct : undefined}
          value={gpu?.available ? `${(gpu?.util_pct ?? 0).toFixed(0)}%` : "—"}
          meta={gpu?.available ? `🌡️ ${gpu?.temp_c ?? "—"}°C · ⚡ ${gpu?.power_w ?? "—"} W · ${gpu?.processes?.length ?? 0} tiến trình` : undefined}
          muted={!gpu?.available}
        />
      </div>

      {/* Per-core CPU */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <span className="text-lg">🧮</span>
            <h3 className="font-semibold text-slate-700">CPU theo nhân</h3>
          </div>
          <span className="text-xs text-slate-400">
            {host?.cpu_count ?? "?"} nhân · dùng chung, không ghim cứng
          </span>
        </div>
        {host?.cpu_per_core && host.cpu_per_core.length > 0 ? (
          <div className="flex items-end gap-1.5 h-24">
            {host.cpu_per_core.map((c, i) => (
              <div key={i} className="flex-1 flex flex-col items-center gap-1" title={`Nhân ${i}: ${c.toFixed(0)}%`}>
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
          <p className="text-sm text-slate-500">Đang tải…</p>
        )}
      </div>

      {/* Training + Redis */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-lg">🏋️</span>
            <h3 className="font-semibold text-slate-700">Huấn luyện</h3>
          </div>
          {training?.active ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-ctu-blue/10 text-ctu-blue">
                  <span className="w-1.5 h-1.5 rounded-full bg-ctu-blue animate-pulse" />Đang chạy
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
              <Meter pct={training.total_epochs ? (100 * (training.current_epoch ?? 0)) / training.total_epochs : 0} />
            </div>
          ) : (
            <div className="flex items-center gap-2 text-sm text-slate-500 py-4">
              <span className="w-2 h-2 rounded-full bg-slate-300" />
              Không có job đang chạy — GPU rảnh, tài nguyên đã trả về hệ thống
            </div>
          )}
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-lg">🗄️</span>
            <h3 className="font-semibold text-slate-700">Redis</h3>
          </div>
          {redis?.available ? (
            <div className="space-y-3">
              <div className="text-2xl font-bold tabular-nums text-slate-900">
                {fmtMem(redis.used_mb)}{redis.maxmemory_mb ? <span className="text-slate-400"> / {fmtMem(redis.maxmemory_mb)}</span> : null}
              </div>
              <Meter pct={redis.used_pct ?? 0} />
              <div className="text-xs text-slate-500">{redis.maxmemory_mb ? "Cache / broker" : "Không giới hạn"}</div>
            </div>
          ) : <p className="text-sm text-slate-500">—</p>}
        </div>
      </div>

      {/* Resource configuration & distribution */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-5">
          <div className="flex items-center gap-2">
            <span className="text-lg">⚙️</span>
            <h3 className="font-semibold text-slate-700">Cấu hình &amp; phân phối tài nguyên</h3>
          </div>
          {config?.available && (
            <span className="text-xs font-mono text-slate-400">{config.source_file}</span>
          )}
        </div>

        {/* Capacity chips */}
        <div className="flex flex-wrap gap-2 mb-5">
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-50 border border-slate-200 text-slate-600">
            🧮 {host?.cpu_count ?? "?"} nhân CPU
          </span>
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-50 border border-slate-200 text-slate-600">
            💾 {fmtMem(budgetMb)} RAM
          </span>
          {gpu?.available && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-ctu-blue/5 border border-ctu-blue/20 text-ctu-blue">
              🎮 {gpu.name} · {fmtMem(gpu.vram_total_mb)} → trainer
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
                      {s.role}
                      {s.concurrency ? ` · ${s.concurrency} luồng` : ""}
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
                    <span className="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-700">GPU</span>
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
                {budgetMb ? <span className="text-slate-400"> / ngân sách {fmtMem(budgetMb)}</span> : null}
              </span>
              {budgetMb > 0 && (
                <span className={`font-bold tabular-nums ${allocMb > budgetMb ? "text-orange-600" : "text-slate-600"}`}>
                  {Math.round((100 * allocMb) / budgetMb)}% ngân sách
                </span>
              )}
            </div>
          </>
        ) : (
          <p className="text-sm text-slate-500">Không đọc được cấu hình tài nguyên từ compose.</p>
        )}
      </div>
    </div>
  );
}
