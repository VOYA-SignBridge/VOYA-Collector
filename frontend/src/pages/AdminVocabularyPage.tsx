/**
 * Admin: vocabulary registry.
 *
 * Closes the loop opened by AddDialectModal. A contributor proposing a dialect
 * files it as PENDING; without this screen nothing could ever approve it, so
 * proposals accumulated invisibly and the picker could never grow.
 *
 * Two deliberate constraints from the API, surfaced in the UI rather than
 * hidden:
 *
 *  - Rejecting REQUIRES a merge target. Rejection here means "this is a
 *    duplicate of that one", so anything already recorded under the rejected
 *    slug has somewhere to go. The API answers 400 without it, so the confirm
 *    button stays disabled until a target is chosen.
 *  - dialect_id is immutable. It is the key used by dataset/samples.csv, the
 *    sample folder names and the realtime model id; renaming it would orphan
 *    every row already filed under it. Only display_name and is_active can
 *    change.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useToast } from "../hooks/useToast";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";
import CatalogVersionSection from "../components/vocabulary/CatalogVersionSection";
import { dialectLabel } from "../config/dialectLabels";
import { useVocabularyRegistry } from "../hooks/useVocabularyRegistry";
import { Trans, useI18n } from "../i18n";
import {
  approveDialect,
  getPendingDialects,
  rejectDialect,
  updateDialect,
  type PendingDialect,
} from "../api/vocabulary";

function fmtDate(v?: string | null): string {
  if (!v) return "—";
  const d = new Date(v);
  return isNaN(d.getTime()) ? String(v) : d.toLocaleString();
}

function Slug({ children }: { children: React.ReactNode }) {
  return (
    <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-sm text-slate-800">
      {children}
    </code>
  );
}

export default function AdminVocabularyPage() {
  const { t } = useI18n();
  const { toast } = useToast();
  const { dialects, profiles, registryVersion, loading, error, refresh } =
    useVocabularyRegistry();

  const [pending, setPending] = useState<PendingDialect[]>([]);
  const [pendingLoading, setPendingLoading] = useState(true);
  const [pendingError, setPendingError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  // dialect_id currently being rejected -> chosen merge target
  const [rejecting, setRejecting] = useState<Record<string, string>>({});
  // dialect_id being renamed -> draft display name
  const [renaming, setRenaming] = useState<Record<string, string>>({});

  const loadPending = useCallback(async () => {
    setPendingLoading(true);
    const res = await getPendingDialects();
    if (res.ok) {
      setPending(res.data);
      setPendingError(null);
    } else {
      setPendingError(res.error);
    }
    setPendingLoading(false);
  }, []);

  useEffect(() => {
    void loadPending();
  }, [loadPending]);

  /** Approved dialects are the only valid merge targets for a rejection. */
  const mergeTargets = useMemo(
    () =>
      dialects
        .filter((d) => !pending.some((p) => p.dialect_id === d.dialect_id))
        .map((d) => d.dialect_id),
    [dialects, pending]
  );

  const onApprove = async (id: string) => {
    setBusy(id);
    const res = await approveDialect(id);
    setBusy(null);
    if (res.ok) {
      toast.success(t("Đã duyệt {id}", { id }));
      await Promise.all([loadPending(), refresh()]);
    } else {
      toast.error(res.error);
    }
  };

  const onReject = async (id: string) => {
    const target = rejecting[id];
    if (!target) return;
    setBusy(id);
    const res = await rejectDialect(id, target);
    setBusy(null);
    if (res.ok) {
      toast.success(t("Đã từ chối {id}, gộp vào {target}", { id, target }));
      setRejecting((p) => {
        const n = { ...p };
        delete n[id];
        return n;
      });
      await Promise.all([loadPending(), refresh()]);
    } else {
      toast.error(res.error);
    }
  };

  const onRename = async (id: string) => {
    const name = (renaming[id] ?? "").trim();
    if (!name) return;
    setBusy(id);
    const res = await updateDialect(id, { display_name: name });
    setBusy(null);
    if (res.ok) {
      toast.success(t("Đã đổi tên hiển thị của {id}", { id }));
      setRenaming((p) => {
        const n = { ...p };
        delete n[id];
        return n;
      });
      await refresh();
    } else {
      toast.error(res.error);
    }
  };

  const onToggleActive = async (id: string, next: boolean) => {
    setBusy(id);
    const res = await updateDialect(id, { is_active: next });
    setBusy(null);
    if (res.ok) {
      toast.success(next ? t("Đã bật {id}", { id }) : t("Đã tắt {id}", { id }));
      await refresh();
    } else {
      toast.error(res.error);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Từ vựng & phương ngữ")}
        subtitle={t("Registry phiên bản {ver} · {so_phuong_ngu} phương ngữ · {so_ho_so} hồ sơ nhận diện", {
          ver: registryVersion || "—",
          so_phuong_ngu: dialects.length,
          so_ho_so: profiles.length,
        })}
      />

      {/* ---------------- Phiên bản danh mục (UC10) ---------------- */}
      <CatalogVersionSection />

      {/* ---------------- Pending queue ---------------- */}
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            {t("Chờ duyệt")}
          </h3>
          {pending.length > 0 && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">
              {pending.length}
            </span>
          )}
        </div>

        {pendingLoading ? (
          <div className="py-6">
            <LoadingSpinner />
          </div>
        ) : pendingError ? (
          <p className="mt-3 text-sm text-red-600">{pendingError}</p>
        ) : pending.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">
            {t("Không có đề xuất nào đang chờ.")}
          </p>
        ) : (
          <ul className="mt-4 space-y-4">
            {pending.map((d) => (
              <li
                key={d.dialect_id}
                className="rounded-lg border border-slate-200 p-4"
              >
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <Slug>{d.dialect_id}</Slug>
                  {d.display_name && d.display_name !== d.dialect_id && (
                    <span className="text-sm text-slate-500">{d.display_name}</span>
                  )}
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  {t("Đề xuất bởi {ai} · {luc}", { ai: d.created_by_username || d.created_by || "—", luc: fmtDate(d.created_at) })}
                </p>

                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    disabled={busy === d.dialect_id}
                    onClick={() => onApprove(d.dialect_id)}
                    className="rounded-lg bg-sky-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-700 disabled:opacity-50"
                  >
                    {t("Duyệt")}
                  </button>

                  <span className="text-slate-300">|</span>

                  <label className="text-sm text-slate-600" htmlFor={`merge-${d.dialect_id}`}>
                    {t("Từ chối, gộp vào")}
                  </label>
                  <select
                    id={`merge-${d.dialect_id}`}
                    value={rejecting[d.dialect_id] ?? ""}
                    onChange={(e) =>
                      setRejecting((p) => ({ ...p, [d.dialect_id]: e.target.value }))
                    }
                    className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm font-mono"
                  >
                    <option value="">{t("— chọn phương ngữ —")}</option>
                    {mergeTargets.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    disabled={!rejecting[d.dialect_id] || busy === d.dialect_id}
                    onClick={() => onReject(d.dialect_id)}
                    className="rounded-lg border border-red-300 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-40"
                  >
                    {t("Từ chối")}
                  </button>
                </div>
                <p className="mt-2 text-xs text-slate-400">
                  {t("Từ chối bắt buộc chọn nơi gộp — dữ liệu đã gắn mã này sẽ chuyển sang đó thay vì mồ côi.")}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ---------------- All dialects ---------------- */}
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          {t("Tất cả phương ngữ")}
        </h3>
        <p className="mt-1 text-xs text-slate-500">
          <Trans
            k="Mã ({ma}) là thứ xuất hiện trong {csv}, tên thư mục mẫu và {model} — không sửa được. Chỉ đổi được tên hiển thị và trạng thái bật/tắt."
            vars={{
              ma: <span className="font-mono">dialect_id</span>,
              csv: <span className="font-mono">samples.csv</span>,
              model: <span className="font-mono">model_id</span>,
            }}
          />
        </p>

        {loading ? (
          <div className="py-6">
            <LoadingSpinner />
          </div>
        ) : error ? (
          <p className="mt-3 text-sm text-red-600">{error}</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
                  <th className="pb-2 pr-4">{t("Mã")}</th>
                  <th className="pb-2 pr-4">{t("Tên hiển thị")}</th>
                  <th className="pb-2 pr-4">{t("Trạng thái")}</th>
                  <th className="pb-2">{t("Thao tác")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {dialects.map((d) => {
                  const draft = renaming[d.dialect_id];
                  const isActive = d.is_active !== false;
                  return (
                    <tr key={d.dialect_id}>
                      <td className="py-3 pr-4">
                        <Slug>{dialectLabel(d.dialect_id)}</Slug>
                      </td>
                      <td className="py-3 pr-4">
                        {draft === undefined ? (
                          <span className="text-slate-600">{d.display_name || "—"}</span>
                        ) : (
                          <input
                            value={draft}
                            onChange={(e) =>
                              setRenaming((p) => ({ ...p, [d.dialect_id]: e.target.value }))
                            }
                            className="w-48 rounded-lg border border-slate-300 px-2 py-1"
                          />
                        )}
                      </td>
                      <td className="py-3 pr-4">
                        <span
                          className={
                            isActive
                              ? "rounded-full bg-sky-100 px-2 py-0.5 text-xs font-medium text-sky-800"
                              : "rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600"
                          }
                        >
                          {isActive ? t("đang bật") : t("đã tắt")}
                        </span>
                      </td>
                      <td className="py-3">
                        <div className="flex flex-wrap gap-2">
                          {draft === undefined ? (
                            <button
                              type="button"
                              onClick={() =>
                                setRenaming((p) => ({
                                  ...p,
                                  [d.dialect_id]: d.display_name || "",
                                }))
                              }
                              className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs hover:bg-slate-50"
                            >
                              {t("Đổi tên")}
                            </button>
                          ) : (
                            <>
                              <button
                                type="button"
                                disabled={busy === d.dialect_id}
                                onClick={() => onRename(d.dialect_id)}
                                className="rounded-lg bg-slate-900 px-2.5 py-1 text-xs text-white disabled:opacity-50"
                              >
                                {t("Lưu")}
                              </button>
                              <button
                                type="button"
                                onClick={() =>
                                  setRenaming((p) => {
                                    const n = { ...p };
                                    delete n[d.dialect_id];
                                    return n;
                                  })
                                }
                                className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs hover:bg-slate-50"
                              >
                                {t("Hủy")}
                              </button>
                            </>
                          )}
                          <button
                            type="button"
                            disabled={busy === d.dialect_id}
                            onClick={() => onToggleActive(d.dialect_id, !isActive)}
                            className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs hover:bg-slate-50 disabled:opacity-50"
                          >
                            {isActive ? t("Tắt") : t("Bật")}
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
      </section>

      {/* ---------------- Profiles (read-only) ---------------- */}
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          {t("Hồ sơ nhận diện")}
        </h3>
        <p className="mt-1 text-xs text-slate-500">
          {t("Thứ tự do máy chủ quyết định (theo địa lý, không theo bảng chữ cái) — hiển thị đúng thứ tự nhận được, không sắp xếp lại.")}
        </p>
        <ul className="mt-3 flex flex-wrap gap-2">
          {profiles.map((p) => (
            <li
              key={p.profile_id}
              className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-1.5"
            >
              <Slug>{p.profile_id}</Slug>
              {!p.is_trainable && (
                <span className="text-xs text-slate-400">{t("(không huấn luyện)")}</span>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
