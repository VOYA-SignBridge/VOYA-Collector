import { useCallback, useEffect, useMemo, useState } from "react";
import { useToast } from "../hooks/useToast";
import {
  getClassTrash,
  getSampleTrash,
  restoreClass,
  purgeClass,
  restoreSample,
  purgeSample,
  bulkRestoreClasses,
  bulkPurgeClasses,
  emptyClassTrash,
  bulkRestoreSamples,
  bulkPurgeSamples,
  emptySampleTrash,
  type TrashClass,
  type TrashSample,
} from "../api/dataset";

type Tab = "classes" | "samples";

export default function TrashPage() {
  const { toast } = useToast();
  const [tab, setTab] = useState<Tab>("classes");
  const [classes, setClasses] = useState<TrashClass[]>([]);
  const [samples, setSamples] = useState<TrashSample[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [selClasses, setSelClasses] = useState<Set<string>>(new Set());
  const [selSamples, setSelSamples] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    const [c, s] = await Promise.all([getClassTrash(), getSampleTrash()]);
    if (c.ok) setClasses(c.data);
    else toast.error(c.error || "Không đọc được thùng rác nhãn");
    if (s.ok) setSamples(s.data);
    else toast.error(s.error || "Không đọc được thùng rác mẫu");
    setSelClasses(new Set());
    setSelSamples(new Set());
    setLoading(false);
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  const sel = tab === "classes" ? selClasses : selSamples;
  const setSel = tab === "classes" ? setSelClasses : setSelSamples;
  const allIds = useMemo(
    () => (tab === "classes" ? classes.map((c) => c.class_uid) : samples.map((s) => s.sample_uid)),
    [tab, classes, samples],
  );
  const allSelected = allIds.length > 0 && allIds.every((id) => sel.has(id));

  const toggle = (id: string) => {
    setSel((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };
  const toggleAll = () => setSel(allSelected ? new Set() : new Set(allIds));

  const afterBulk = async (label: string, res: { ok: boolean; data?: { ok_count: number; failed_count: number }; error?: string }) => {
    if (res.ok && res.data) {
      const { ok_count, failed_count } = res.data;
      if (failed_count) toast.error(`${label}: ${ok_count} thành công, ${failed_count} lỗi`);
      else toast.success(`${label}: ${ok_count} mục`);
    } else {
      toast.error(res.error || `${label} thất bại`);
    }
    await load();
  };

  // --- single-row actions ---
  const doRestoreClass = async (c: TrashClass) => {
    setBusy(true);
    const res = await restoreClass(c.class_uid);
    setBusy(false);
    if (res.ok) { toast.success(`Đã khôi phục "${c.label_original || c.slug}"`); setClasses((p) => p.filter((x) => x.class_uid !== c.class_uid)); }
    else toast.error(res.error || "Lỗi khôi phục");
  };
  const doPurgeClass = async (c: TrashClass) => {
    if (!window.confirm(`Xóa VĨNH VIỄN nhãn "${c.label_original || c.slug}" và ${c.sample_count ?? 0} mẫu? Không thể hoàn tác.`)) return;
    setBusy(true);
    const res = await purgeClass(c.class_uid);
    setBusy(false);
    if (res.ok) { toast.success("Đã xóa vĩnh viễn nhãn"); setClasses((p) => p.filter((x) => x.class_uid !== c.class_uid)); }
    else toast.error(res.error || "Lỗi xóa vĩnh viễn");
  };
  const doRestoreSample = async (s: TrashSample) => {
    setBusy(true);
    const res = await restoreSample(s.sample_uid);
    setBusy(false);
    if (res.ok) { toast.success("Đã khôi phục mẫu"); setSamples((p) => p.filter((x) => x.sample_uid !== s.sample_uid)); }
    else toast.error(res.error || "Lỗi khôi phục mẫu");
  };
  const doPurgeSample = async (s: TrashSample) => {
    if (!window.confirm(`Xóa VĨNH VIỄN mẫu ${s.sample_uid}? Không thể hoàn tác.`)) return;
    setBusy(true);
    const res = await purgeSample(s.sample_uid);
    setBusy(false);
    if (res.ok) { toast.success("Đã xóa vĩnh viễn mẫu"); setSamples((p) => p.filter((x) => x.sample_uid !== s.sample_uid)); }
    else toast.error(res.error || "Lỗi xóa vĩnh viễn mẫu");
  };

  // --- bulk actions ---
  const bulkRestore = async () => {
    const ids = [...sel];
    if (!ids.length) return;
    setBusy(true);
    const res = tab === "classes" ? await bulkRestoreClasses(ids) : await bulkRestoreSamples(ids);
    await afterBulk("Đã khôi phục", res);
    setBusy(false);
  };
  const bulkPurge = async () => {
    const ids = [...sel];
    if (!ids.length) return;
    if (!window.confirm(`Xóa VĨNH VIỄN ${ids.length} mục đã chọn? Không thể hoàn tác.`)) return;
    setBusy(true);
    const res = tab === "classes" ? await bulkPurgeClasses(ids) : await bulkPurgeSamples(ids);
    await afterBulk("Đã xóa vĩnh viễn", res);
    setBusy(false);
  };
  const emptyTrash = async () => {
    const n = tab === "classes" ? classes.length : samples.length;
    if (!n) return;
    if (!window.confirm(`Làm trống thùng rác ${tab === "classes" ? "nhãn" : "mẫu"}? Xóa VĨNH VIỄN toàn bộ ${n} mục. Không thể hoàn tác.`)) return;
    setBusy(true);
    const res = tab === "classes" ? await emptyClassTrash() : await emptySampleTrash();
    await afterBulk("Đã làm trống", res);
    setBusy(false);
  };

  const tabBtn = (t: Tab, label: string, n: number) => (
    <button
      onClick={() => setTab(t)}
      className={`px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors ${
        tab === t ? "border-red-500 text-red-600 dark:text-red-400" : "border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
      }`}
    >
      {label} <span className="ml-1 text-xs opacity-70">({n})</span>
    </button>
  );

  const count = tab === "classes" ? classes.length : samples.length;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-3 mb-1">
        <svg className="h-6 w-6 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
        </svg>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Thùng rác</h1>
      </div>
      <p className="text-sm text-gray-500 mb-4">
        Nhãn và mẫu đã xóa mềm. Khôi phục để đưa lại, hoặc xóa vĩnh viễn (không thể hoàn tác).
        Xóa vĩnh viễn một nhãn sẽ xóa luôn các mẫu bên trong.
      </p>

      <div className="flex gap-2 border-b border-gray-200 dark:border-gray-700 mb-3">
        {tabBtn("classes", "Nhãn đã xóa", classes.length)}
        {tabBtn("samples", "Mẫu đã xóa", samples.length)}
      </div>

      {/* Bulk toolbar */}
      <div className="flex flex-wrap items-center gap-2 mb-3 min-h-[36px]">
        <span className="text-sm text-gray-500">{sel.size > 0 ? `Đã chọn ${sel.size}` : "Chọn mục để thao tác hàng loạt"}</span>
        <div className="flex-1" />
        <button
          disabled={busy || sel.size === 0}
          onClick={bulkRestore}
          className="px-3 py-1.5 text-xs rounded bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-40"
        >
          Khôi phục đã chọn{sel.size ? ` (${sel.size})` : ""}
        </button>
        <button
          disabled={busy || sel.size === 0}
          onClick={bulkPurge}
          className="px-3 py-1.5 text-xs rounded bg-red-600 hover:bg-red-700 text-white disabled:opacity-40"
        >
          Xóa vĩnh viễn đã chọn{sel.size ? ` (${sel.size})` : ""}
        </button>
        <button
          disabled={busy || count === 0}
          onClick={emptyTrash}
          className="px-3 py-1.5 text-xs rounded border border-red-600 text-red-600 hover:bg-red-50 dark:hover:bg-red-950 disabled:opacity-40"
        >
          Làm trống thùng rác
        </button>
      </div>

      {loading ? (
        <div className="py-12 text-center text-gray-400">Đang tải…</div>
      ) : count === 0 ? (
        <div className="py-12 text-center text-gray-400">
          {tab === "classes" ? "Không có nhãn nào trong thùng rác." : "Không có mẫu nào trong thùng rác."}
        </div>
      ) : tab === "classes" ? (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b border-gray-200 dark:border-gray-700">
                <th className="py-2 pr-3 w-8"><input type="checkbox" checked={allSelected} onChange={toggleAll} /></th>
                <th className="py-2 pr-4">Nhãn</th>
                <th className="py-2 pr-4">Ngôn ngữ / Giọng</th>
                <th className="py-2 pr-4">Số mẫu</th>
                <th className="py-2 pr-4">Đã xóa lúc</th>
                <th className="py-2 pr-4 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {classes.map((c) => (
                <tr key={c.class_uid} className="border-b border-gray-100 dark:border-gray-800">
                  <td className="py-2 pr-3"><input type="checkbox" checked={selClasses.has(c.class_uid)} onChange={() => toggle(c.class_uid)} /></td>
                  <td className="py-2 pr-4 font-medium text-gray-900 dark:text-gray-100">
                    {c.label_original || c.slug}<span className="ml-2 text-xs text-gray-400">#{c.class_idx}</span>
                  </td>
                  <td className="py-2 pr-4 text-gray-500">{c.language} / {c.dialect || "—"}</td>
                  <td className="py-2 pr-4">{c.sample_count ?? 0}</td>
                  <td className="py-2 pr-4 text-gray-400">{c.deleted_at ? new Date(c.deleted_at).toLocaleString() : "—"}</td>
                  <td className="py-2 pr-4">
                    <div className="flex gap-2 justify-end">
                      <button disabled={busy} onClick={() => doRestoreClass(c)} className="px-3 py-1 text-xs rounded bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-50">Khôi phục</button>
                      <button disabled={busy} onClick={() => doPurgeClass(c)} className="px-3 py-1 text-xs rounded bg-red-600 hover:bg-red-700 text-white disabled:opacity-50">Xóa vĩnh viễn</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b border-gray-200 dark:border-gray-700">
                <th className="py-2 pr-3 w-8"><input type="checkbox" checked={allSelected} onChange={toggleAll} /></th>
                <th className="py-2 pr-4">Mã mẫu</th>
                <th className="py-2 pr-4">Nhãn</th>
                <th className="py-2 pr-4">Người đóng góp</th>
                <th className="py-2 pr-4">Đã xóa lúc</th>
                <th className="py-2 pr-4 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {samples.map((s) => (
                <tr key={s.sample_uid} className="border-b border-gray-100 dark:border-gray-800">
                  <td className="py-2 pr-3"><input type="checkbox" checked={selSamples.has(s.sample_uid)} onChange={() => toggle(s.sample_uid)} /></td>
                  <td className="py-2 pr-4 font-mono text-xs text-gray-700 dark:text-gray-300">{s.sample_uid}</td>
                  <td className="py-2 pr-4 text-gray-900 dark:text-gray-100">{s.label_original || s.slug}</td>
                  <td className="py-2 pr-4 text-gray-500">{s.username || s.user_id || "—"}</td>
                  <td className="py-2 pr-4 text-gray-400">{s.deleted_at ? new Date(s.deleted_at).toLocaleString() : "—"}</td>
                  <td className="py-2 pr-4">
                    <div className="flex gap-2 justify-end">
                      <button disabled={busy} onClick={() => doRestoreSample(s)} className="px-3 py-1 text-xs rounded bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-50">Khôi phục</button>
                      <button disabled={busy} onClick={() => doPurgeSample(s)} className="px-3 py-1 text-xs rounded bg-red-600 hover:bg-red-700 text-white disabled:opacity-50">Xóa vĩnh viễn</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
