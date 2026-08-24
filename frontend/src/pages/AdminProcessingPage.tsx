/**
 * Hàng đợi xử lý (UC16 — Monitor Processing).
 *
 * `/admin/resources` đo MÁY. Trang này đo VIỆC. Hai câu hỏi khác nhau, và gộp
 * chúng vào một màn hình là cách chắc chắn để không trả lời được câu nào: một
 * host rảnh 5% CPU vẫn có thể đang ôm một hàng đợi 300 việc chưa ai nhấc.
 *
 * Luật hiển thị: **"không đo được" phải trông khác "bằng 0"**. Khi không worker
 * nào trả lời, trang nói thẳng là không hỏi được — chứ không vẽ một hàng đợi
 * trống, vốn là kết luận ngược hẳn với sự thật.
 */
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useToast } from "../hooks/useToast";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";
import {
  getProcessingSnapshot,
  revokeTask,
  type ProcessingSnapshot,
  type TaskRow,
} from "../api/processing";
import { friendlyError } from "../lib/errors";
import { useI18n } from "../i18n";
import { ServerIcon, BoltIcon, ClockIcon, AlertTriangleIcon } from "../components/ui/Icons";

function Card({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-2.5">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-ctu-blue/10 text-ctu-blue">
          {icon}
        </span>
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</span>
      </div>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function fmtStart(v: number | null): string {
  if (!v) return "—";
  const d = new Date(v * 1000);
  return isNaN(d.getTime()) ? "—" : d.toLocaleTimeString();
}

export default function AdminProcessingPage() {
  const { t } = useI18n();
  const { toast } = useToast();
  const [snap, setSnap] = useState<ProcessingSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [auto, setAuto] = useState(true);

  const load = useCallback(async () => {
    try {
      setSnap(await getProcessingSnapshot());
    } catch (e) {
      toast.error(friendlyError(e, t("Không đọc được trạng thái xử lý")));
    } finally {
      setLoading(false);
    }
  }, [t, toast]);

  useEffect(() => {
    load();
    if (!auto) return;
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [auto, load]);

  const doRevoke = async (task: TaskRow) => {
    const terminate = task.state === "running";
    const msg = terminate
      ? t("Dừng hẳn việc đang chạy \"{ten}\"? Công việc có thể dở dang.", { ten: task.name })
      : t("Gỡ việc \"{ten}\" khỏi hàng đợi?", { ten: task.name });
    if (!window.confirm(msg)) return;
    try {
      await revokeTask(task.task_id, terminate);
      toast.success(t("Đã gửi lệnh huỷ"));
      await load();
    } catch (e) {
      toast.error(friendlyError(e, t("Huỷ thất bại")));
    }
  };

  const TaskTable = ({ rows, title }: { rows: TaskRow[]; title: string }) => (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <h3 className="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-800">
        {title} <span className="ml-1 tabular-nums text-slate-400">({rows.length})</span>
      </h3>
      {rows.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-slate-400">{t("Không có việc nào.")}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-3 py-2 text-left font-medium">{t("Tên việc")}</th>
                <th className="px-3 py-2 text-left font-medium">{t("Worker")}</th>
                <th className="px-3 py-2 text-left font-medium">{t("Bắt đầu")}</th>
                <th className="px-3 py-2 text-left font-medium">{t("Tham số")}</th>
                <th className="px-3 py-2 text-right font-medium">{t("Thao tác")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.task_id} className="border-t border-slate-100">
                  <td className="px-3 py-2 font-medium text-slate-800">{r.name}</td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-500">{r.worker}</td>
                  <td className="px-3 py-2 tabular-nums text-slate-600">{fmtStart(r.time_start)}</td>
                  <td className="max-w-xs truncate px-3 py-2 font-mono text-xs text-slate-400">
                    {r.args_preview || "—"}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      onClick={() => doRevoke(r)}
                      className="rounded-md border border-slate-300 px-2.5 py-1 text-xs text-slate-700 transition-colors hover:bg-slate-100"
                    >
                      {r.state === "running" ? t("Dừng") : t("Gỡ khỏi hàng đợi")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );

  if (loading && !snap) {
    return (
      <div className="flex justify-center py-20">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="animate-fade-in mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
      <PageHeader
        title={t("Hàng đợi xử lý")}
        subtitle={t("Việc đang chạy, việc đang chờ và worker đang phục vụ chúng.")}
        actions={
          <>
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={auto}
                onChange={(e) => setAuto(e.target.checked)}
                className="rounded border-slate-300"
              />
              {t("Tự làm mới")}
            </label>
            <button
              onClick={load}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
            >
              {t("Làm mới")}
            </button>
          </>
        }
      />

      {snap && !snap.reachable && (
        <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>
            {t("Không hỏi được worker nào — số liệu bên dưới KHÔNG có nghĩa là hàng đợi trống.")}{" "}
            {snap.unreachable_reason}
          </span>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card title={t("Worker đang phục vụ")} icon={<ServerIcon className="h-5 w-5" />}>
          <div className="text-2xl font-bold tabular-nums text-slate-900">
            {snap?.reachable ? snap.workers.length : "—"}
          </div>
          <p className="mt-1 truncate font-mono text-[11px] text-slate-400">
            {snap?.workers.join(", ") || (snap?.reachable ? t("không có") : t("không hỏi được"))}
          </p>
        </Card>
        <Card title={t("Đang chạy")} icon={<BoltIcon className="h-5 w-5" />}>
          <div className="text-2xl font-bold tabular-nums text-slate-900">
            {snap?.reachable ? snap.running.length : "—"}
          </div>
        </Card>
        <Card title={t("Đang chờ worker")} icon={<ClockIcon className="h-5 w-5" />}>
          <div className="text-2xl font-bold tabular-nums text-slate-900">
            {snap?.reachable ? snap.reserved.length : "—"}
          </div>
        </Card>
        <Card title={t("Việc hỏng gần đây")} icon={<AlertTriangleIcon className="h-5 w-5" />}>
          <div className="text-2xl font-bold tabular-nums text-slate-900">
            {snap?.recent_failures.length ?? 0}
          </div>
        </Card>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold text-slate-800">
          {t("Chiều dài hàng đợi (việc chưa worker nào nhấc)")}
        </h3>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {(snap?.queues ?? []).map((q) => (
            <div key={q.name} className="rounded-lg border border-slate-200 px-4 py-3">
              <div className="font-mono text-xs text-slate-500">{q.name}</div>
              {q.depth === null ? (
                <div className="mt-1 text-sm italic text-slate-400">{t("không đo được")}</div>
              ) : (
                <div className="mt-1 text-2xl font-bold tabular-nums text-slate-900">{q.depth}</div>
              )}
              {q.error && <div className="mt-1 text-[11px] text-red-600">{q.error}</div>}
            </div>
          ))}
        </div>
      </div>

      <TaskTable rows={snap?.running ?? []} title={t("Việc đang chạy")} />
      <TaskTable rows={snap?.reserved ?? []} title={t("Việc đang chờ")} />

      {(snap?.recent_failures.length ?? 0) > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
          <h3 className="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-800">
            {t("Việc hỏng gần đây")}
          </h3>
          <ul className="divide-y divide-slate-100">
            {(snap?.recent_failures ?? []).map((f, i) => (
              <li key={i} className="px-4 py-2.5 text-sm">
                <span className="font-medium text-slate-800">{f.action}</span>
                <span className="ml-2 font-mono text-xs text-slate-400">{f.target}</span>
                {f.reason && <p className="mt-0.5 text-xs text-slate-500">{f.reason}</p>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
