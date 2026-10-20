/**
 * Quản lý người ký (UC11).
 *
 * Sổ `dataset/signers.csv` đã ghi hồ sơ người ký từ lâu, nhưng chỉ có máy ghi
 * vào — không màn hình nào đọc ra. Trang này là mặt người của sổ đó: xem ai
 * đã đóng góp bao nhiêu, sửa phần mô tả, vô hiệu hoá, và tuyên bố hai id là
 * một người.
 *
 * Ba điều trang này CỐ Ý hiển thị thẳng thay vì làm đẹp:
 *
 *  - Số mẫu không mang `signer_id` nào. Chia số đó vào các hồ sơ đang có sẽ
 *    cho một bảng cộng đủ tổng nhưng sai người; để riêng thì nhìn là biết phần
 *    dữ liệu nào chưa quy được về ai.
 *  - Đồng thuận đọc từ `signer_consents`, và "chưa từng ký" khác "đã rút".
 *    Gộp hai thứ vào một chữ "không" là xoá mất một quyết định của con người.
 *  - Gộp KHÔNG viết lại mẫu đã thu. Bảng hiện hồ sơ cũ kèm mũi tên sang hồ sơ
 *    giữ lại, vì đó đúng là những gì `signer_aliases` lưu.
 */
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useToast } from "../hooks/useToast";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";
import {
  getSigners,
  updateSigner,
  mergeSigner,
  type SignerRow,
  type SignersResponse,
} from "../api/signers";
import { friendlyError } from "../lib/errors";
import { useI18n } from "../i18n";
import { UsersIcon, CameraIcon, TagIcon, SearchIcon, XIcon } from "../components/ui/Icons";

function fmtDate(v?: string | null): string {
  if (!v) return "—";
  const d = new Date(v);
  return isNaN(d.getTime()) ? String(v) : d.toLocaleString();
}

function Card({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-2.5">
        <span className="w-9 h-9 rounded-lg bg-ctu-blue/10 text-ctu-blue flex items-center justify-center shrink-0">
          {icon}
        </span>
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</span>
      </div>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function Badge({ tone, children }: { tone: "green" | "gray" | "red" | "blue" | "amber"; children: ReactNode }) {
  const tones: Record<string, string> = {
    green: "bg-sky-100 text-sky-800 border-sky-200",
    gray: "bg-slate-100 text-slate-700 border-slate-200",
    red: "bg-red-100 text-red-800 border-red-200",
    blue: "bg-ctu-blue/10 text-ctu-blue border-ctu-blue/30",
    amber: "bg-amber-100 text-amber-800 border-amber-200",
  };
  return (
    <span className={`inline-flex items-center border px-2 py-0.5 rounded-full text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

export default function AdminSignersPage() {
  const { t } = useI18n();
  const { toast } = useToast();

  const [data, setData] = useState<SignersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [showInactive, setShowInactive] = useState(false);

  // Hồ sơ đang sửa -> bản nháp của các trường sửa được.
  const [editing, setEditing] = useState<SignerRow | null>(null);
  const [draftName, setDraftName] = useState("");
  const [draftGroup, setDraftGroup] = useState("");
  const [saving, setSaving] = useState(false);

  // Hồ sơ đang gộp ĐI -> đích giữ lại.
  const [merging, setMerging] = useState<SignerRow | null>(null);
  const [mergeTarget, setMergeTarget] = useState("");
  const [mergeReason, setMergeReason] = useState("");

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setData(await getSigners());
    } catch (e) {
      toast.error(friendlyError(e, t("Không tải được danh sách người ký")));
    } finally {
      setLoading(false);
    }
  }, [t, toast]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (data?.signers ?? []).filter((s) => {
      if (!showInactive && !s.is_active) return false;
      if (!q) return true;
      return (
        s.signer_id.toLowerCase().includes(q) ||
        s.display_name.toLowerCase().includes(q) ||
        s.regional_group.toLowerCase().includes(q)
      );
    });
  }, [data, query, showInactive]);

  const attributed = (data?.total_samples ?? 0) - (data?.unattributed_samples ?? 0);

  const openEdit = (s: SignerRow) => {
    setEditing(s);
    setDraftName(s.display_name);
    setDraftGroup(s.regional_group);
  };

  const saveEdit = async () => {
    if (!editing) return;
    try {
      setSaving(true);
      await updateSigner(editing.signer_id, {
        display_name: draftName.trim(),
        regional_group: draftGroup.trim(),
      });
      toast.success(t("Đã cập nhật {id}", { id: editing.signer_id }));
      setEditing(null);
      await load();
    } catch (e) {
      toast.error(friendlyError(e, t("Cập nhật thất bại")));
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (s: SignerRow) => {
    const next = !s.is_active;
    if (!next && !window.confirm(
      t("Vô hiệu hoá {id}? Hồ sơ và mẫu đã thu được giữ nguyên, chỉ không hiện khi chọn người ký nữa.",
        { id: s.signer_id })
    )) return;
    try {
      await updateSigner(s.signer_id, { is_active: next });
      toast.success(next ? t("Đã kích hoạt lại {id}", { id: s.signer_id })
                         : t("Đã vô hiệu hoá {id}", { id: s.signer_id }));
      await load();
    } catch (e) {
      toast.error(friendlyError(e, t("Không đổi được trạng thái")));
    }
  };

  const doMerge = async () => {
    if (!merging || !mergeTarget) return;
    try {
      setSaving(true);
      await mergeSigner(merging.signer_id, mergeTarget, mergeReason.trim());
      toast.success(t("Đã gộp {old} vào {new}", { old: merging.signer_id, new: mergeTarget }));
      setMerging(null);
      setMergeTarget("");
      setMergeReason("");
      await load();
    } catch (e) {
      toast.error(friendlyError(e, t("Gộp thất bại")));
    } finally {
      setSaving(false);
    }
  };

  const consentBadge = (s: SignerRow) => {
    if (s.consent_state === "granted")
      return <Badge tone="green">{s.consent_scope}</Badge>;
    if (s.consent_state === "withdrawn")
      return <Badge tone="red">{t("đã rút")}</Badge>;
    return <Badge tone="gray">{t("chưa ký")}</Badge>;
  };

  if (loading && !data) {
    return (
      <div className="flex justify-center py-20">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 max-w-6xl mx-auto space-y-6 animate-fade-in">
      <PageHeader
        title={t("Người ký")}
        subtitle={t("Hồ sơ người thực hiện ký hiệu, số mẫu đã đóng góp và trạng thái đồng thuận.")}
        actions={
          <button
            onClick={load}
            className="px-3 py-2 rounded-lg border border-slate-300 bg-white text-sm text-slate-700 font-medium hover:bg-slate-50 transition-colors"
          >
            {t("Làm mới")}
          </button>
        }
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card title={t("Hồ sơ người ký")} icon={<UsersIcon className="w-5 h-5" />}>
          <div className="text-2xl font-bold text-slate-900 tabular-nums">{data?.signers.length ?? 0}</div>
        </Card>
        <Card title={t("Đang hoạt động")} icon={<UsersIcon className="w-5 h-5" />}>
          <div className="text-2xl font-bold text-slate-900 tabular-nums">
            {(data?.signers ?? []).filter((s) => s.is_active).length}
          </div>
        </Card>
        <Card title={t("Mẫu đã quy được chủ")} icon={<CameraIcon className="w-5 h-5" />}>
          <div className="text-2xl font-bold text-slate-900 tabular-nums">{attributed.toLocaleString("vi-VN")}</div>
        </Card>
        <Card title={t("Mẫu chưa quy được chủ")} icon={<TagIcon className="w-5 h-5" />}>
          <div className="text-2xl font-bold text-slate-900 tabular-nums">
            {(data?.unattributed_samples ?? 0).toLocaleString("vi-VN")}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {t("Không mang signer_id — không suy ra chủ được.")}
          </p>
        </Card>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 p-4 border-b border-slate-200">
          <div className="relative flex-1">
            <SearchIcon className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("Tìm theo mã, tên hiển thị hoặc nhóm vùng")}
              className="w-full pl-9 pr-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-ctu-blue/30"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-600 shrink-0">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(e) => setShowInactive(e.target.checked)}
              className="rounded border-slate-300"
            />
            {t("Hiện cả hồ sơ đã vô hiệu hoá")}
          </label>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="text-left font-medium py-2.5 px-3">{t("Mã")}</th>
                <th className="text-left font-medium py-2.5 px-3">{t("Tên hiển thị")}</th>
                <th className="text-left font-medium py-2.5 px-3">{t("Nhóm vùng")}</th>
                <th className="text-right font-medium py-2.5 px-3">{t("Mẫu")}</th>
                <th className="text-right font-medium py-2.5 px-3">{t("Lớp")}</th>
                <th className="text-left font-medium py-2.5 px-3">{t("Mẫu gần nhất")}</th>
                <th className="text-left font-medium py-2.5 px-3">{t("Đồng thuận")}</th>
                <th className="text-right font-medium py-2.5 px-3">{t("Thao tác")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-400">
                    {t("Không có hồ sơ nào khớp.")}
                  </td>
                </tr>
              )}
              {rows.map((s) => (
                <tr key={s.signer_id} className="border-t border-slate-100 hover:bg-slate-50/60">
                  <td className="py-2.5 px-3 font-mono text-slate-700">{s.signer_id}</td>
                  <td className="py-2.5 px-3">
                    <div className="text-slate-900">{s.display_name || "—"}</div>
                    {s.merged_into && (
                      <div className="text-xs text-amber-700 mt-0.5">
                        {t("đã gộp vào {id}", { id: s.merged_into })}
                        {s.merged_reason ? ` — ${s.merged_reason}` : ""}
                      </div>
                    )}
                    {!s.is_active && !s.merged_into && (
                      <div className="text-xs text-slate-400 mt-0.5">{t("đã vô hiệu hoá")}</div>
                    )}
                  </td>
                  <td className="py-2.5 px-3 text-slate-600">{s.regional_group || "—"}</td>
                  <td className="py-2.5 px-3 text-right tabular-nums font-semibold text-slate-700">
                    {s.sample_count.toLocaleString("vi-VN")}
                  </td>
                  <td className="py-2.5 px-3 text-right tabular-nums text-slate-600">{s.class_count}</td>
                  <td className="py-2.5 px-3 text-slate-500 whitespace-nowrap">{fmtDate(s.last_sample_at)}</td>
                  <td className="py-2.5 px-3">{consentBadge(s)}</td>
                  <td className="py-2.5 px-3">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => openEdit(s)}
                        className="px-2.5 py-1 rounded-md border border-slate-300 text-xs text-slate-700 hover:bg-slate-100 transition-colors"
                      >
                        {t("Sửa")}
                      </button>
                      {!s.merged_into && (
                        <button
                          onClick={() => { setMerging(s); setMergeTarget(""); setMergeReason(""); }}
                          className="px-2.5 py-1 rounded-md border border-slate-300 text-xs text-slate-700 hover:bg-slate-100 transition-colors"
                        >
                          {t("Gộp")}
                        </button>
                      )}
                      <button
                        onClick={() => toggleActive(s)}
                        className="px-2.5 py-1 rounded-md border border-slate-300 text-xs text-slate-700 hover:bg-slate-100 transition-colors"
                      >
                        {s.is_active ? t("Vô hiệu hoá") : t("Kích hoạt")}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ------- Sửa hồ sơ ------- */}
      {editing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white shadow-lg">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
              <h3 className="font-semibold text-slate-800">
                {t("Sửa hồ sơ {id}", { id: editing.signer_id })}
              </h3>
              <button onClick={() => setEditing(null)} className="text-slate-400 hover:text-slate-600">
                <XIcon className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">{t("Tên hiển thị")}</label>
                <input
                  value={draftName}
                  onChange={(e) => setDraftName(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-ctu-blue/30"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">{t("Nhóm vùng")}</label>
                <input
                  value={draftGroup}
                  onChange={(e) => setDraftGroup(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-ctu-blue/30"
                />
              </div>
              <p className="text-xs text-slate-500">
                {t("Mã người ký không sửa được: mẫu đã thu đang trỏ vào nó. Muốn hai mã chỉ về một người thì dùng chức năng Gộp.")}
              </p>
            </div>
            <div className="flex justify-end gap-2 border-t border-slate-200 px-5 py-3">
              <button
                onClick={() => setEditing(null)}
                className="px-3 py-2 rounded-lg border border-slate-300 text-sm text-slate-700 hover:bg-slate-50"
              >
                {t("Huỷ")}
              </button>
              <button
                onClick={saveEdit}
                disabled={saving}
                className="px-3 py-2 rounded-lg bg-ctu-blue text-white text-sm font-medium hover:bg-ctu-blue/90 disabled:opacity-50"
              >
                {saving ? t("Đang lưu…") : t("Lưu")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ------- Gộp hồ sơ ------- */}
      {merging && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white shadow-lg">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
              <h3 className="font-semibold text-slate-800">
                {t("Gộp {id} vào hồ sơ khác", { id: merging.signer_id })}
              </h3>
              <button onClick={() => setMerging(null)} className="text-slate-400 hover:text-slate-600">
                <XIcon className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">{t("Giữ lại hồ sơ")}</label>
                <select
                  value={mergeTarget}
                  onChange={(e) => setMergeTarget(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-ctu-blue/30"
                >
                  <option value="">{t("— chọn hồ sơ giữ lại —")}</option>
                  {(data?.signers ?? [])
                    .filter((s) => s.signer_id !== merging.signer_id && !s.merged_into)
                    .map((s) => (
                      <option key={s.signer_id} value={s.signer_id}>
                        {s.signer_id} — {s.display_name || t("(không tên)")} ({s.sample_count})
                      </option>
                    ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">{t("Lý do")}</label>
                <input
                  value={mergeReason}
                  onChange={(e) => setMergeReason(e.target.value)}
                  placeholder={t("vd: cùng một người, đăng ký hai lần")}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-ctu-blue/30"
                />
              </div>
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
                {t("Mẫu đã thu KHÔNG bị viết lại. Chúng giữ nguyên mã cũ, và hệ thống đi theo ánh xạ này khi phân giải đồng thuận và khi chia tập theo người ký.")}
              </div>
            </div>
            <div className="flex justify-end gap-2 border-t border-slate-200 px-5 py-3">
              <button
                onClick={() => setMerging(null)}
                className="px-3 py-2 rounded-lg border border-slate-300 text-sm text-slate-700 hover:bg-slate-50"
              >
                {t("Huỷ")}
              </button>
              <button
                onClick={doMerge}
                disabled={saving || !mergeTarget}
                className="px-3 py-2 rounded-lg bg-ctu-blue text-white text-sm font-medium hover:bg-ctu-blue/90 disabled:opacity-50"
              >
                {saving ? t("Đang gộp…") : t("Gộp")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
