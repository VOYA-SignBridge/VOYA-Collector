import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import apiClient from "../api/axiosClient";
import SyncGDriveModal from "../components/SyncGDriveModal";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import {
  TagIcon, CameraIcon, UsersIcon, GlobeIcon, DatabaseIcon, ClockIcon, CloudDownloadIcon,
} from "../components/ui/Icons";

interface Contributor { user_id: string; username: string; count: number }
interface RecentSample { label: string; dialect: string; source: string; created_at: string }
interface DataReport {
  labels_count: number;
  total_samples: number;
  contributors_count: number;
  regions_count: number;
  top_labels: { label: string; count: number }[];
  by_region: { region: string; count: number }[];
  by_source: { source: string; count: number }[];
  top_contributors: Contributor[];
  recent: RecentSample[];
}

function StatCard({ label, value, icon }: { label: string; value: number; icon: ReactNode }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
      <div className="flex items-center gap-2.5 mb-2">
        <span className="w-9 h-9 rounded-lg bg-ctu-blue/10 text-ctu-blue flex items-center justify-center shrink-0">{icon}</span>
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</span>
      </div>
      <div className="text-3xl font-bold tabular-nums text-slate-900">{value.toLocaleString("vi-VN")}</div>
    </div>
  );
}

function BarList({ title, icon, rows }: { title: string; icon: ReactNode; rows: { name: string; count: number }[] }) {
  const max = rows.reduce((m, r) => Math.max(m, r.count), 0) || 1;
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
      <h3 className="font-semibold text-slate-700 mb-4 flex items-center gap-2"><span className="text-ctu-blue">{icon}</span>{title}</h3>
      {rows.length === 0 ? (
        <p className="text-sm text-slate-400">Chưa có dữ liệu.</p>
      ) : (
        <div className="space-y-2">
          {rows.map((r) => (
            <div key={r.name} className="flex items-center gap-3">
              <div className="w-28 sm:w-36 shrink-0 text-sm text-slate-700 truncate" title={r.name}>{r.name}</div>
              <div className="flex-1 h-5 rounded-md bg-slate-100 overflow-hidden">
                <div className="h-full rounded-md bg-ctu-blue/80" style={{ width: `${Math.max(4, (r.count / max) * 100)}%` }} />
              </div>
              <div className="w-12 shrink-0 text-right text-sm font-semibold tabular-nums text-slate-600">{r.count}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AdminDataPage() {
  const [data, setData] = useState<DataReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncOpen, setSyncOpen] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await apiClient.get<DataReport>("/api/v1/admin/data-report");
      setData(res.data);
      setError(null);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Không tải được báo cáo dữ liệu");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 mb-2 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-ctu-blue/10 flex items-center justify-center text-ctu-blue">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M4 7v10c0 2 1.5 3 5 3s5-1 5-3V7M4 7c0 2 1.5 3 5 3s5-1 5-3M4 7c0-2 1.5-3 5-3s5 1 5 3m0 5c0 2 1.5 3 5 3s5-1 5-3V7c0-2-1.5-3-5-3s-5 1-5 3" />
              </svg>
            </div>
            Quản lý dữ liệu
          </h2>
          <p className="text-slate-600">Báo cáo & thống kê dữ liệu đóng góp, quản lý đồng bộ lưu trữ</p>
        </div>
        <button onClick={() => setSyncOpen(true)}
          title="Kiểm tra & tải các file còn thiếu từ Google Drive về server (không thay đổi cơ sở dữ liệu)"
          className="inline-flex items-center gap-2 px-4 py-2 bg-ctu-blue text-white font-medium rounded-lg hover:bg-ctu-navy transition-colors">
          <CloudDownloadIcon className="w-5 h-5" /> Đồng bộ dữ liệu (Drive → server)
        </button>
      </div>

      {error && <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">{error}</div>}

      {loading ? (
        <div className="py-20">
          <LoadingSpinner size="lg" label="Đang tải báo cáo dữ liệu..." />
        </div>
      ) : (
        <>
          {/* Totals */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Nhãn" value={data?.labels_count ?? 0} icon={<TagIcon className="w-5 h-5" />} />
            <StatCard label="Mẫu dữ liệu" value={data?.total_samples ?? 0} icon={<CameraIcon className="w-5 h-5" />} />
            <StatCard label="Người đóng góp" value={data?.contributors_count ?? 0} icon={<UsersIcon className="w-5 h-5" />} />
            <StatCard label="Vùng miền" value={data?.regions_count ?? 0} icon={<GlobeIcon className="w-5 h-5" />} />
          </div>

          {/* Breakdowns */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <BarList title="Top nhãn theo số mẫu" icon={<TagIcon className="w-5 h-5" />} rows={(data?.top_labels ?? []).map((r) => ({ name: r.label, count: r.count }))} />
            <BarList title="Phân bố theo vùng" icon={<GlobeIcon className="w-5 h-5" />} rows={(data?.by_region ?? []).map((r) => ({ name: r.region, count: r.count }))} />
            <BarList title="Người đóng góp nhiều nhất" icon={<UsersIcon className="w-5 h-5" />} rows={(data?.top_contributors ?? []).map((r) => ({ name: r.username, count: r.count }))} />
            <BarList title="Theo nguồn" icon={<DatabaseIcon className="w-5 h-5" />} rows={(data?.by_source ?? []).map((r) => ({ name: r.source, count: r.count }))} />
          </div>

          {/* Recent */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h3 className="font-semibold text-slate-700 mb-4 flex items-center gap-2"><span className="text-ctu-blue"><ClockIcon className="w-5 h-5" /></span>Mẫu mới nhất</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="text-slate-500 border-b border-slate-200">
                    <th className="py-2 px-3 font-semibold">Nhãn</th>
                    <th className="py-2 px-3 font-semibold">Vùng</th>
                    <th className="py-2 px-3 font-semibold">Nguồn</th>
                    <th className="py-2 px-3 font-semibold">Thời gian</th>
                  </tr>
                </thead>
                <tbody>
                  {(data?.recent ?? []).length === 0 ? (
                    <tr><td colSpan={4} className="py-6 text-center text-slate-400">Chưa có mẫu nào.</td></tr>
                  ) : (
                    data!.recent.map((r, i) => (
                      <tr key={i} className="border-b border-slate-50">
                        <td className="py-2 px-3 font-medium text-slate-800">{r.label || "—"}</td>
                        <td className="py-2 px-3 text-slate-600">{r.dialect || "—"}</td>
                        <td className="py-2 px-3 text-slate-600">{r.source || "—"}</td>
                        <td className="py-2 px-3 text-slate-400 tabular-nums">{r.created_at ? r.created_at.slice(0, 19).replace("T", " ") : "—"}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      <SyncGDriveModal isOpen={syncOpen} onClose={() => setSyncOpen(false)} />
    </div>
  );
}
