import { useCallback, useEffect, useMemo, useState } from "react";
import { useToast } from "../hooks/useToast";
import { useAuth } from "../hooks/useAuth";
import Modal from "../components/ui/Modal";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import { Trans, useI18n } from "../i18n";
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

interface Confirm {
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void | Promise<void>;
}

/* ---- small inline icons (stroke = currentColor) ---- */
const TrashIcon = ({ className = "h-5 w-5" }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
  </svg>
);
const RestoreIcon = ({ className = "h-4 w-4" }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
  </svg>
);
const WarnIcon = ({ className = "h-6 w-6" }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
  </svg>
);

function fmtDate(v?: string) {
  if (!v) return "—";
  const d = new Date(v);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function TrashPage() {
  const { t } = useI18n();
  const { toast } = useToast();
  const { isAdmin } = useAuth();
  // Contributors only have a sample trash (they don't own labels), so default
  // them straight to it; admins land on the labels tab.
  const [tab, setTab] = useState<Tab>(isAdmin ? "classes" : "samples");
  const [classes, setClasses] = useState<TrashClass[]>([]);
  const [samples, setSamples] = useState<TrashSample[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [selClasses, setSelClasses] = useState<Set<string>>(new Set());
  const [selSamples, setSelSamples] = useState<Set<string>>(new Set());
  const [confirm, setConfirm] = useState<Confirm | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    // Everyone has a sample trash. The label (class) trash is admin-only — a
    // contributor never owns a class, so skip that call (it would 403).
    const s = await getSampleTrash();
    if (s.ok) setSamples(s.data);
    else toast.error(s.error || t("Không đọc được thùng rác mẫu"));
    if (isAdmin) {
      const c = await getClassTrash();
      if (c.ok) setClasses(c.data);
      else toast.error(c.error || t("Không đọc được thùng rác nhãn"));
    } else {
      setClasses([]);
    }
    setSelClasses(new Set());
    setSelSamples(new Set());
    setLoading(false);
  }, [toast, isAdmin]);

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
  const someSelected = sel.size > 0 && !allSelected;
  const count = tab === "classes" ? classes.length : samples.length;

  const toggle = (id: string) =>
    setSel((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  const toggleAll = () => setSel(allSelected ? new Set() : new Set(allIds));

  const runBulk = async (
    label: string,
    fn: () => Promise<{ ok: boolean; data?: { ok_count: number; failed_count: number }; error?: string }>,
  ) => {
    setBusy(true);
    const res = await fn();
    if (res.ok && res.data) {
      const { ok_count, failed_count } = res.data;
      if (failed_count) toast.error(t("{label}: {ok_count} thành công, {failed_count} lỗi", { label, ok_count, failed_count }));
      else toast.success(t("{label} {ok_count} mục", { label, ok_count }));
    } else {
      toast.error(res.error || t("{label} thất bại", { label }));
    }
    await load();
    setBusy(false);
  };

  const runSingle = async (label: string, fn: () => Promise<{ ok: boolean; error?: string }>) => {
    setBusy(true);
    const res = await fn();
    if (res.ok) toast.success(label);
    else toast.error(res.error || t("{label} thất bại", { label }));
    await load();
    setBusy(false);
  };

  const ids = () => [...sel];

  /* ---- action launchers (destructive ones go through the confirm modal) ---- */
  const askBulkPurge = () =>
    setConfirm({
      title: t("Xóa vĩnh viễn mục đã chọn"),
      message: t("Bạn sắp xóa VĨNH VIỄN {n} {loai}. Hành động này không thể hoàn tác.", {
        n: sel.size,
        loai: tab === "classes" ? t("nhãn (kèm toàn bộ mẫu bên trong)") : t("mẫu"),
      }),
      confirmLabel: t("Xóa {size} mục", { size: sel.size }),
      onConfirm: () =>
        runBulk(t("Đã xóa vĩnh viễn"), () => (tab === "classes" ? bulkPurgeClasses(ids()) : bulkPurgeSamples(ids()))),
    });

  const askEmpty = () =>
    setConfirm({
      title: t("Làm trống thùng rác"),
      message: t("Xóa VĨNH VIỄN toàn bộ {n} {loai} trong thùng rác. Hành động này không thể hoàn tác.", {
        n: count,
        loai: tab === "classes" ? t("nhãn (kèm mẫu bên trong)") : t("mẫu"),
      }),
      confirmLabel: t("Làm trống"),
      onConfirm: () => runBulk(t("Đã làm trống"), () => (tab === "classes" ? emptyClassTrash() : emptySampleTrash())),
    });

  const askPurgeClass = (c: TrashClass) =>
    setConfirm({
      title: t("Xóa vĩnh viễn nhãn"),
      message: t("Xóa VĨNH VIỄN nhãn \"{label_original}\" và {sample_count} mẫu bên trong (file + Drive). Không thể hoàn tác.", { label_original: c.label_original || c.slug, sample_count: c.sample_count ?? 0 }),
      confirmLabel: t("Xóa vĩnh viễn"),
      onConfirm: () => runSingle(t("Đã xóa vĩnh viễn nhãn"), () => purgeClass(c.class_uid)),
    });

  const askPurgeSample = (s: TrashSample) =>
    setConfirm({
      title: t("Xóa vĩnh viễn mẫu"),
      message: t("Xóa VĨNH VIỄN mẫu {sample_uid}. Không thể hoàn tác.", { sample_uid: s.sample_uid }),
      confirmLabel: t("Xóa vĩnh viễn"),
      onConfirm: () => runSingle(t("Đã xóa vĩnh viễn mẫu"), () => purgeSample(s.sample_uid)),
    });

  const bulkRestore = () =>
    runBulk(t("Đã khôi phục"), () => (tab === "classes" ? bulkRestoreClasses(ids()) : bulkRestoreSamples(ids())));

  /* ---- UI pieces ---- */
  const TabPill = ({ t, label, n }: { t: Tab; label: string; n: number }) => {
    const active = tab === t;
    return (
      <button
        onClick={() => setTab(t)}
        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
          active ? "bg-white text-ctu-navy shadow-sm" : "text-slate-500 hover:text-slate-700"
        }`}
      >
        {label}
        <span className={`min-w-[22px] text-center px-1.5 py-0.5 rounded-full text-xs font-bold ${active ? "bg-ctu-blue/10 text-ctu-blue" : "bg-slate-200 text-slate-500"}`}>
          {n}
        </span>
      </button>
    );
  };

  const Checkbox = ({ checked, indeterminate, onChange }: { checked: boolean; indeterminate?: boolean; onChange: () => void }) => (
    <input
      type="checkbox"
      checked={checked}
      ref={(el) => { if (el) el.indeterminate = !!indeterminate && !checked; }}
      onChange={onChange}
      className="h-4 w-4 rounded border-slate-300 text-ctu-blue accent-ctu-blue cursor-pointer"
    />
  );

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
      {/* Header */}
      <div className="flex items-start gap-4 mb-6">
        <div className="h-12 w-12 rounded-2xl bg-red-50 text-ctu-red flex items-center justify-center ring-1 ring-red-100 flex-shrink-0">
          <TrashIcon className="h-6 w-6" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{t("Thùng rác")}</h1>
          <p className="text-sm text-slate-500 mt-1 max-w-2xl leading-relaxed">
            {isAdmin ? (
              <>
                <Trans
                  k="Nhãn và mẫu đã xóa mềm vẫn giữ nguyên dữ liệu. {khoi_phuc} để đưa lại, hoặc {xoa_han} (không thể hoàn tác). Xóa vĩnh viễn một nhãn sẽ xóa luôn các mẫu bên trong."
                  vars={{
                    khoi_phuc: <b className="text-slate-600">{t("Khôi phục")}</b>,
                    xoa_han: <b className="text-slate-600">{t("xóa vĩnh viễn")}</b>,
                  }}
                />
              </>
            ) : (
              <>
                <Trans
                  k="Thùng rác riêng của bạn — các lần quay bạn đã xóa vẫn giữ nguyên dữ liệu. {khoi_phuc} để đưa lại, hoặc {xoa_han} (không thể hoàn tác)."
                  vars={{
                    khoi_phuc: <b className="text-slate-600">{t("Khôi phục")}</b>,
                    xoa_han: <b className="text-slate-600">{t("xóa vĩnh viễn")}</b>,
                  }}
                />
              </>
            )}
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="inline-flex p-1 bg-slate-100 rounded-xl mb-4">
        {isAdmin && <TabPill t="classes" label={t("Nhãn đã xóa")} n={classes.length} />}
        <TabPill t="samples" label={t("Mẫu đã xóa")} n={samples.length} />
      </div>

      {/* Toolbar / selection bar */}
      <div
        className={`flex flex-wrap items-center gap-2 rounded-xl px-3 py-2.5 mb-3 border transition-colors ${
          sel.size > 0 ? "bg-ctu-blue/5 border-ctu-blue/25" : "bg-white border-slate-200"
        }`}
      >
        <label className="flex items-center gap-2 pl-1 pr-2 cursor-pointer select-none">
          <Checkbox checked={allSelected} indeterminate={someSelected} onChange={toggleAll} />
          <span className="text-sm font-medium text-slate-600">
            {sel.size > 0 ? t("Đã chọn {size}", { size: sel.size }) : t("Chọn tất cả")}
          </span>
        </label>

        <div className="flex-1" />

        <button
          disabled={busy || sel.size === 0}
          onClick={bulkRestore}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-sky-800 bg-sky-50 hover:bg-sky-100 ring-1 ring-sky-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <RestoreIcon /> {t("Khôi phục")}{sel.size ? ` (${sel.size})` : ""}
        </button>
        <button
          disabled={busy || sel.size === 0}
          onClick={askBulkPurge}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-white bg-ctu-red hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <TrashIcon className="h-4 w-4" /> {t("Xóa vĩnh viễn")}{sel.size ? ` (${sel.size})` : ""}
        </button>
        <div className="w-px h-6 bg-slate-200 mx-1" />
        <button
          disabled={busy || count === 0}
          onClick={askEmpty}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-ctu-red hover:bg-red-50 ring-1 ring-red-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {t("Làm trống thùng rác")}
        </button>
      </div>

      {/* Content card */}
      <div className="card p-0 overflow-hidden">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-400 gap-3">
            <LoadingSpinner size="lg" label={t("Đang tải thùng rác…")} />
          </div>
        ) : count === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center px-6">
            <div className="h-16 w-16 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mb-4">
              <TrashIcon className="h-8 w-8" />
            </div>
            <h3 className="text-lg font-semibold text-slate-700">{t("Thùng rác trống")}</h3>
            <p className="text-sm text-slate-500 mt-1">
              {tab === "classes" ? t("Chưa có nhãn nào bị xóa.") : t("Chưa có mẫu nào bị xóa.")}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <th className="py-3 pl-4 pr-2 w-10">
                    <Checkbox checked={allSelected} indeterminate={someSelected} onChange={toggleAll} />
                  </th>
                  {tab === "classes" ? (
                    <>
                      <th className="py-3 px-3">{t("Nhãn")}</th>
                      <th className="py-3 px-3">{t("Ngôn ngữ / Giọng")}</th>
                      <th className="py-3 px-3">{t("Số mẫu")}</th>
                    </>
                  ) : (
                    <>
                      <th className="py-3 px-3">{t("Mã mẫu")}</th>
                      <th className="py-3 px-3">{t("Nhãn")}</th>
                      <th className="py-3 px-3">{t("Người đóng góp")}</th>
                    </>
                  )}
                  <th className="py-3 px-3">{t("Đã xóa lúc")}</th>
                  <th className="py-3 pr-4 pl-3 text-right">{t("Thao tác")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {tab === "classes"
                  ? classes.map((c) => {
                      const checked = selClasses.has(c.class_uid);
                      return (
                        <tr key={c.class_uid} className={`transition-colors ${checked ? "bg-ctu-blue/5" : "hover:bg-slate-50/70"}`}>
                          <td className="py-3 pl-4 pr-2">
                            <Checkbox checked={checked} onChange={() => toggle(c.class_uid)} />
                          </td>
                          <td className="py-3 px-3">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-slate-900">{c.label_original || c.slug}</span>
                              <span className="text-xs font-medium text-slate-400 bg-slate-100 rounded px-1.5 py-0.5">#{c.class_idx}</span>
                            </div>
                          </td>
                          <td className="py-3 px-3 text-slate-500">{c.language} / {c.dialect || "—"}</td>
                          <td className="py-3 px-3">
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-ctu-blue/10 text-ctu-blue">
                              {t("{n} mẫu", { n: c.sample_count ?? 0 })}
                            </span>
                          </td>
                          <td className="py-3 px-3 text-slate-400 whitespace-nowrap">{fmtDate(c.deleted_at)}</td>
                          <td className="py-3 pr-4 pl-3">
                            <div className="flex gap-1.5 justify-end">
                              <button
                                disabled={busy}
                                onClick={() => runSingle(t("Đã khôi phục nhãn"), () => restoreClass(c.class_uid))}
                                title={t("Khôi phục")}
                                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-sky-800 hover:bg-sky-50 ring-1 ring-sky-200 disabled:opacity-50 transition-colors"
                              >
                                <RestoreIcon className="h-3.5 w-3.5" /> {t("Khôi phục")}
                              </button>
                              <button
                                disabled={busy}
                                onClick={() => askPurgeClass(c)}
                                title={t("Xóa vĩnh viễn")}
                                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-ctu-red hover:bg-red-50 ring-1 ring-red-200 disabled:opacity-50 transition-colors"
                              >
                                <TrashIcon className="h-3.5 w-3.5" /> {t("Xóa")}
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  : samples.map((s) => {
                      const checked = selSamples.has(s.sample_uid);
                      return (
                        <tr key={s.sample_uid} className={`transition-colors ${checked ? "bg-ctu-blue/5" : "hover:bg-slate-50/70"}`}>
                          <td className="py-3 pl-4 pr-2">
                            <Checkbox checked={checked} onChange={() => toggle(s.sample_uid)} />
                          </td>
                          <td className="py-3 px-3 font-mono text-xs text-slate-600">{s.sample_uid}</td>
                          <td className="py-3 px-3 font-medium text-slate-900">{s.label_original || s.slug}</td>
                          <td className="py-3 px-3 text-slate-500">{s.username || s.user_id || "—"}</td>
                          <td className="py-3 px-3 text-slate-400 whitespace-nowrap">{fmtDate(s.deleted_at)}</td>
                          <td className="py-3 pr-4 pl-3">
                            <div className="flex gap-1.5 justify-end">
                              <button
                                disabled={busy}
                                onClick={() => runSingle(t("Đã khôi phục mẫu"), () => restoreSample(s.sample_uid))}
                                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-sky-800 hover:bg-sky-50 ring-1 ring-sky-200 disabled:opacity-50 transition-colors"
                              >
                                <RestoreIcon className="h-3.5 w-3.5" /> {t("Khôi phục")}
                              </button>
                              <button
                                disabled={busy}
                                onClick={() => askPurgeSample(s)}
                                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-ctu-red hover:bg-red-50 ring-1 ring-red-200 disabled:opacity-50 transition-colors"
                              >
                                <TrashIcon className="h-3.5 w-3.5" /> {t("Xóa")}
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Confirm modal (destructive) */}
      <Modal isOpen={!!confirm} onClose={() => setConfirm(null)} size="sm">
        {confirm && (
          <div>
            <div className="flex items-start gap-4">
              <div className="h-11 w-11 rounded-full bg-red-50 text-ctu-red flex items-center justify-center flex-shrink-0">
                <WarnIcon />
              </div>
              <div className="pt-0.5">
                <h3 className="text-lg font-semibold text-slate-900">{confirm.title}</h3>
                <p className="text-sm text-slate-500 mt-1.5 leading-relaxed">{confirm.message}</p>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => setConfirm(null)}
                disabled={busy}
                className="px-4 py-2 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-50 transition-colors"
              >
                {t("Hủy")}
              </button>
              <button
                onClick={async () => {
                  const c = confirm;
                  setConfirm(null);
                  await c.onConfirm();
                }}
                disabled={busy}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold text-white bg-ctu-red hover:bg-red-700 disabled:opacity-50 transition-colors"
              >
                <TrashIcon className="h-4 w-4" /> {confirm.confirmLabel}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
