/**
 * Cấp phát tài nguyên xuống cấp project — `/console/allocations`.
 *
 * Bài toán trang này giải
 * ------------------------
 * Gói cước đặt trần cho **cả tổ chức**: bao nhiêu mẫu, bao nhiêu dung lượng,
 * bao nhiêu lượt huấn luyện mỗi tháng. Nhưng một tổ chức có nhiều nhóm cùng
 * thu dữ liệu, và trước trang này không có cách nào nói *"lớp K47 được 500 mẫu,
 * lớp K48 được 300"* — mọi nhóm dùng chung một cái trần, ai chạm trước thì
 * người sau hết chỗ.
 *
 * Ba con số phải hiện cùng lúc, và đó là quyết định thiết kế
 * -----------------------------------------------------------
 * Mỗi chỉ tiêu hiện **trần gói · đã cấp phát · còn lại**. Bản chỉ hiện phần đã
 * cấp cho từng project buộc người dùng tự cộng trừ để biết còn bao nhiêu — và
 * hai người cùng làm phép tính đó sẽ ra hai kết quả khác nhau vào đúng lúc một
 * người vừa cấp thêm.
 *
 * Máy chủ cũng kiểm lại tổng: `set_allocation` từ chối khi tổng cấp phát vượt
 * trần. Giao diện hiện phần còn lại để người dùng không phải chạm vào phép kiểm
 * đó mới biết mình vượt.
 *
 * Ô trống nghĩa là KHÔNG GIỚI HẠN, không phải BẰNG KHÔNG
 * -------------------------------------------------------
 * Cùng quy ước với `plans` và với `project_allocations.allocated`. Đây là chỗ
 * đọc nhầm sẽ chặn toàn bộ hoạt động của một project, nên nhãn nói thẳng ra
 * thay vì để người dùng suy đoán từ một ô rỗng.
 */

import { useCallback, useEffect, useState } from "react";
import PageHeader from "../../components/ui/PageHeader";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/ui/EmptyState";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import ErrorBanner from "../../components/ErrorBanner";
import { useAuth } from "../../contexts/AuthContext";
import { isTenantAdmin } from "../../api/auth";
import { useToast } from "../../hooks/useToast";
import { friendlyError } from "../../lib/errors";
import { useI18n } from "../../i18n";
import {
  listAllocations, listWorkspaces, setAllocation,
  type AllocationTable, type Workspace,
} from "../../api/workspaces";

/** @i18n-key-table — nhãn chỉ tiêu là KHOÁ, dịch tại chỗ đọc. */
const METRIC_LABEL: Record<string, string> = {
  samples: "Số mẫu",
  storage_mb: "Dung lượng (MB)",
  training_jobs_per_month: "Lượt huấn luyện / tháng",
};

const fmt = (v: number | null | undefined, unlimited: string) =>
  v === null || v === undefined ? unlimited : v.toLocaleString("vi-VN");

export default function ConsoleAllocationsPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const { toast } = useToast();

  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [table, setTable] = useState<AllocationTable | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});

  // Vai TỔ CHỨC, không phải cờ quản trị nền tảng — xem `isTenantAdmin`.
  const canEdit = isTenantAdmin(user);

  useEffect(() => {
    (async () => {
      try {
        const rows = await listWorkspaces(false);
        setWorkspaces(rows);
        setSelected((prev) => prev || rows[0]?.workspace_id || "");
      } catch (err) {
        setError(friendlyError(err, t("Không đọc được danh sách workspace.")));
      } finally {
        setLoading(false);
      }
    })();
  }, [t]);

  const load = useCallback(async (workspaceId: string) => {
    if (!workspaceId) return;
    try {
      const data = await listAllocations(workspaceId);
      setTable(data);
      const next: Record<string, string> = {};
      data.projects.forEach((p) => {
        data.metrics.forEach((m) => {
          const cell = p.allocations[m];
          next[`${p.project_id}:${m}`] =
            cell && cell.allocated !== null ? String(cell.allocated) : "";
        });
      });
      setDraft(next);
    } catch (err) {
      setError(friendlyError(err, t("Không đọc được bảng cấp phát.")));
    }
  }, [t]);

  useEffect(() => { void load(selected); }, [selected, load]);

  const save = async (projectId: string, metric: string) => {
    const raw = (draft[`${projectId}:${metric}`] ?? "").trim();
    const value = raw === "" ? null : Number(raw);
    if (value !== null && (!Number.isFinite(value) || value < 0)) {
      toast.error(t("Giá trị cấp phát phải là số không âm, hoặc để trống nghĩa là không giới hạn."));
      return;
    }
    setBusy(true);
    try {
      await setAllocation(selected, { project_id: projectId, metric, allocated: value });
      toast.success(t("Đã cập nhật cấp phát"));
      await load(selected);
    } catch (err) {
      toast.error(friendlyError(err, t("Không cập nhật được cấp phát.")));
    } finally {
      setBusy(false);
    }
  };

  const unlimited = t("không giới hạn");

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Cấp phát tài nguyên")}
        subtitle={t("Chia hạn mức của gói cước xuống từng project trong một workspace.")}
      />


      {error && <ErrorBanner message={error} />}
      {loading && <LoadingSpinner size="lg" label={t("Đang tải…")} />}

      {!loading && workspaces.length === 0 && (
        <EmptyState
          title={t("Chưa có workspace nào")}
          description={t("Tạo workspace ở mục Workspace & Project trước khi cấp phát tài nguyên.")}
        />
      )}

      {!loading && workspaces.length > 0 && (
        <>
          <label className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium text-slate-700">{t("Workspace")}</span>
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              {workspaces.map((w) => (
                <option key={w.workspace_id} value={w.workspace_id}>{w.name}</option>
              ))}
            </select>
          </label>

          {table && (
            <>
              <div className="grid gap-3 sm:grid-cols-3">
                {table.metrics.map((m) => (
                  <div key={m} className="rounded-lg border border-slate-200 p-3">
                    <div className="text-xs font-medium text-slate-500">
                      {t(METRIC_LABEL[m] ?? m)}
                    </div>
                    <dl className="mt-2 space-y-1 text-sm">
                      <div className="flex justify-between">
                        <dt className="text-slate-500">{t("Trần gói")}</dt>
                        <dd className="font-semibold text-slate-900">
                          {fmt(table.tenant_ceiling[m], unlimited)}
                        </dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-slate-500">{t("Đã cấp phát")}</dt>
                        <dd className="text-slate-900">
                          {(table.allocated_total[m] ?? 0).toLocaleString("vi-VN")}
                        </dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-slate-500">{t("Còn lại")}</dt>
                        <dd className="font-semibold text-ctu-blue">
                          {fmt(table.remaining[m], unlimited)}
                        </dd>
                      </div>
                    </dl>
                  </div>
                ))}
              </div>

              {table.projects.length === 0 ? (
                <EmptyState
                  title={t("Workspace này chưa có project")}
                  description={t("Tạo project trước, rồi quay lại đây để chia hạn mức.")}
                />
              ) : (
                <div className="overflow-x-auto rounded-lg border border-slate-200">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 text-left text-slate-600">
                      <tr>
                        <th className="px-3 py-2">{t("Project")}</th>
                        {table.metrics.map((m) => (
                          <th key={m} className="px-3 py-2">{t(METRIC_LABEL[m] ?? m)}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {table.projects.map((p) => (
                        <tr key={p.project_id} className="border-t border-slate-100">
                          <td className="px-3 py-2">
                            <div className="font-medium text-slate-900">{p.name}</div>
                            <div className="mt-1 flex items-center gap-2">
                              <Badge variant={p.status === "ACTIVE" ? "success" : "default"} size="sm">
                                {t(p.status)}
                              </Badge>
                              {p.is_default && (
                                <span className="text-xs text-slate-400">{t("mặc định")}</span>
                              )}
                            </div>
                          </td>
                          {table.metrics.map((m) => {
                            const key = `${p.project_id}:${m}`;
                            return (
                              <td key={m} className="px-3 py-2">
                                <div className="flex items-center gap-1.5">
                                  <input
                                    value={draft[key] ?? ""}
                                    onChange={(e) =>
                                      setDraft((d) => ({ ...d, [key]: e.target.value }))
                                    }
                                    inputMode="numeric"
                                    placeholder={unlimited}
                                    aria-label={t("Cấp phát {chi_tieu} cho {project}", {
                                      chi_tieu: t(METRIC_LABEL[m] ?? m), project: p.name,
                                    })}
                                    disabled={!canEdit}
                                    className="w-28 rounded-md border border-slate-300 px-2 py-1.5 text-sm disabled:bg-slate-50"
                                  />
                                  {canEdit && (
                                    <Button
                                      size="sm"
                                      variant="secondary"
                                      disabled={busy}
                                      onClick={() => void save(p.project_id, m)}
                                    >
                                      {t("Lưu")}
                                    </Button>
                                  )}
                                </div>
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
