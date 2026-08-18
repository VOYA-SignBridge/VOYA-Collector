/**
 * Workspace & Project — `/settings/workspaces`.
 *
 * Vì sao trang này tồn tại
 * -------------------------
 * Đề cương cam kết một kiến trúc **Workspace–Project**, mỗi workspace có
 * projects, members và dataset ownership riêng, cùng **RBAC ba phạm vi**
 * system / workspace / project. Lược đồ đã dựng đủ: hai bảng, khoá ngoại ghép
 * chống bắc cầu tenant, `memberships.scope_level` bốn giá trị, 13 vai dựng sẵn
 * (2 SYSTEM / 5 TENANT / 2 WORKSPACE / 4 PROJECT).
 *
 * Nhưng cho tới trước đợt này **không có endpoint nào** tạo được chúng, nên hai
 * tầng dưới là *cấu trúc dữ liệu, chưa phải bề mặt vận hành* — và mọi phát biểu
 * trong tài liệu phải kèm mệnh đề đó. Trang này cùng `routers/workspaces.py`
 * đóng đúng khoảng trống ấy.
 *
 * Ba điều trang này TỪ CHỐI làm
 * ------------------------------
 * 1. **Không giấu hai giới hạn còn lại.** Băng thông tin ở đầu trang in ra
 *    nguyên văn: dữ liệu chưa mang `project_id`, và `AUTHZ_MODE` đang là
 *    `shadow`. Một trang tạo được project mà im lặng về hai điều đó sẽ được đọc
 *    thành "phân quyền bốn cấp đã chạy" — sai, và sai theo hướng có lợi cho
 *    người viết tài liệu, tức là kiểu sai tệ nhất.
 * 2. **Không tự suy ra quyền.** Nút sửa ẩn theo `is_admin`/vai tổ chức chỉ để
 *    khỏi mời người dùng bấm vào thứ chắc chắn 403; máy chủ vẫn là nơi cưỡng chế.
 * 3. **Không cho lưu trữ workspace/project mặc định.** Máy chủ từ chối, và giao
 *    diện nói trước lý do thay vì để người dùng nhận 409.
 *
 * @i18n-key-table — nhãn trạng thái là KHOÁ từ điển, dịch tại chỗ đọc.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import PageHeader from "../../components/ui/PageHeader";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/ui/EmptyState";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import ErrorBanner from "../../components/ErrorBanner";
import {
  BuildingIcon, FolderIcon, UsersIcon, InfoCircleIcon, TrashIcon, CheckIcon,
} from "../../components/ui/Icons";
import { useAuth } from "../../contexts/AuthContext";
import { isTenantAdmin } from "../../api/auth";
import { useToast } from "../../hooks/useToast";
import { friendlyError } from "../../lib/errors";
import { useI18n } from "../../i18n";
import {
  createProject, createWorkspace, getScopeSummary, grantScopeRole, listProjects,
  listScopeMembers, listScopeRoles, listWorkspaces, revokeScopeRole, updateProject,
  updateWorkspace,
  type Project, type ScopeMember, type ScopeRole, type ScopeSummary, type Workspace,
} from "../../api/workspaces";

const STATUS_TONE: Record<string, "success" | "default" | "danger"> = {
  ACTIVE: "success",
  ARCHIVED: "default",
  DELETED: "danger",
};

export default function WorkspacesPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const { toast } = useToast();

  const [summary, setSummary] = useState<ScopeSummary | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [members, setMembers] = useState<ScopeMember[]>([]);
  const [roles, setRoles] = useState<ScopeRole[]>([]);
  const [scopeProject, setScopeProject] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [wsName, setWsName] = useState("");
  const [wsDesc, setWsDesc] = useState("");
  const [prjName, setPrjName] = useState("");
  const [prjDesc, setPrjDesc] = useState("");
  const [grantUser, setGrantUser] = useState("");
  const [grantRole, setGrantRole] = useState("");

  // Giao diện KHÔNG cưỡng chế quyền; cờ này chỉ để không mời người dùng bấm vào
  // một nút chắc chắn trả 403. Máy chủ vẫn kiểm bằng `require_tenant_admin`.
  const canEdit = isTenantAdmin(user);

  const current = useMemo(
    () => workspaces.find((w) => w.workspace_id === selected) ?? null,
    [workspaces, selected],
  );

  const loadWorkspaces = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [rows, sum] = await Promise.all([listWorkspaces(true), getScopeSummary()]);
      setWorkspaces(rows);
      setSummary(sum);
      setSelected((prev) => prev ?? rows[0]?.workspace_id ?? null);
    } catch (err) {
      setError(friendlyError(err, t("Không đọc được danh sách workspace.")));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => { void loadWorkspaces(); }, [loadWorkspaces]);

  const loadDetail = useCallback(async (workspaceId: string, projectId: string) => {
    try {
      const level = projectId ? "PROJECT" : "WORKSPACE";
      const [prj, mem, rls] = await Promise.all([
        listProjects(workspaceId, true),
        listScopeMembers(workspaceId, projectId || null),
        listScopeRoles(level),
      ]);
      setProjects(prj);
      setMembers(mem);
      setRoles(rls);
      setGrantRole((prev) => (rls.some((r) => r.role_code === prev) ? prev : rls[0]?.role_code ?? ""));
    } catch (err) {
      setError(friendlyError(err, t("Không đọc được chi tiết workspace.")));
    }
  }, [t]);

  useEffect(() => {
    if (selected) void loadDetail(selected, scopeProject);
  }, [selected, scopeProject, loadDetail]);

  const run = async (fn: () => Promise<unknown>, ok: string, fail: string) => {
    setBusy(true);
    try {
      await fn();
      toast.success(ok);
      await loadWorkspaces();
      if (selected) await loadDetail(selected, scopeProject);
    } catch (err) {
      toast.error(friendlyError(err, fail));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Workspace & Project")}
        subtitle={t("Hai tầng phạm vi bên trong tổ chức: nhóm công việc và phạm vi hoạt động.")}
        breadcrumb={[{ label: t("Trang chủ"), href: "/" }, { label: t("Workspace") }]}
      />

      {/* Băng này KHÔNG được gỡ khi chưa đóng hai khoảng trống nó nêu. Xem chú
          thích đầu tệp: nó là thứ ngăn trang được đọc thành một lời tuyên bố
          rằng phân quyền bốn cấp đã có hiệu lực. */}
      {summary && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <div className="mb-2 flex items-center gap-2 font-semibold">
            <InfoCircleIcon className="h-4 w-4" aria-hidden="true" />
            {t("Trạng thái thật của hai tầng phạm vi này")}
          </div>
          <ul className="ml-5 list-disc space-y-1">
            <li>
              {summary.data_carries_project_id
                ? t("Dữ liệu đã mang project_id.")
                : t("Dữ liệu (mẫu, lớp, tác vụ huấn luyện) hiện CHƯA mang project_id — tạo project không tự phân dữ liệu về project.")}
            </li>
            <li>
              {t("Chế độ phân quyền: {mode}.", { mode: summary.authz_mode })}{" "}
              {summary.authz_mode === "shadow"
                ? t("Casbin đang QUAN SÁT; hệ phân quyền cũ hai phạm vi là bên quyết định, nên vai cấp workspace/project chưa đổi được kết quả kiểm quyền.")
                : t("Casbin là bên quyết định.")}
            </li>
          </ul>
        </div>
      )}

      {summary && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label={t("Workspace")} value={summary.workspaces} icon={<BuildingIcon className="h-4 w-4" />} />
          <Stat label={t("Project")} value={summary.projects} icon={<FolderIcon className="h-4 w-4" />} />
          <Stat label={t("Vai cấp workspace")} value={summary.workspace_members} icon={<UsersIcon className="h-4 w-4" />} />
          <Stat label={t("Vai cấp project")} value={summary.project_members} icon={<UsersIcon className="h-4 w-4" />} />
        </div>
      )}

      {error && <ErrorBanner message={error} />}
      {loading && <LoadingSpinner size="lg" label={t("Đang tải cây phạm vi…")} />}

      {!loading && (
        <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
          {/* ------------------------------------------------ cột trái: workspace */}
          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-slate-900">{t("Workspace")}</h2>

            {workspaces.length === 0 ? (
              <EmptyState
                title={t("Chưa có workspace nào")}
                description={t("Workspace là nhóm công việc bên trong tổ chức — ví dụ một lớp học hoặc một đợt thu.")}
              />
            ) : (
              <ul className="space-y-2">
                {workspaces.map((w) => (
                  <li key={w.workspace_id}>
                    <button
                      type="button"
                      onClick={() => { setSelected(w.workspace_id); setScopeProject(""); }}
                      className={`w-full rounded-lg border p-3 text-left transition-colors ${
                        w.workspace_id === selected
                          ? "border-ctu-blue bg-ctu-blue/5"
                          : "border-slate-200 hover:border-slate-300"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium text-slate-900">{w.name}</span>
                        <Badge variant={STATUS_TONE[w.status] ?? "default"} size="sm">
                          {t(w.status)}
                        </Badge>
                      </div>
                      <div className="mt-1 text-xs text-slate-500">
                        {t("{p} project · {m} vai", { p: w.project_count, m: w.member_count })}
                        {w.is_default && ` · ${t("mặc định")}`}
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {canEdit && (
              <form
                className="space-y-2 rounded-lg border border-slate-200 p-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  void run(
                    () => createWorkspace(wsName, wsDesc).then(() => { setWsName(""); setWsDesc(""); }),
                    t("Đã tạo workspace"),
                    t("Không tạo được workspace."),
                  );
                }}
              >
                <div className="text-sm font-medium text-slate-700">{t("Tạo workspace mới")}</div>
                <input
                  value={wsName}
                  onChange={(e) => setWsName(e.target.value)}
                  placeholder={t("Tên workspace, ví dụ: Lớp VSL K47")}
                  aria-label={t("Tên workspace")}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                />
                <input
                  value={wsDesc}
                  onChange={(e) => setWsDesc(e.target.value)}
                  placeholder={t("Mô tả (tuỳ chọn)")}
                  aria-label={t("Mô tả workspace")}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                />
                <Button type="submit" disabled={busy || !wsName.trim()} className="w-full">
                  {t("Tạo workspace")}
                </Button>
              </form>
            )}
          </section>

          {/* ------------------------------------------------ cột phải: chi tiết */}
          <section className="space-y-6">
            {!current ? (
              <EmptyState
                title={t("Chọn một workspace")}
                description={t("Chọn ở danh sách bên trái để xem project và vai bên trong.")}
              />
            ) : (
              <>
                <div className="rounded-xl border border-slate-200 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <h2 className="text-lg font-semibold text-slate-900">{current.name}</h2>
                      <p className="text-sm text-slate-500">
                        {current.description || t("(không có mô tả)")}
                      </p>
                    </div>
                    {canEdit && !current.is_default && (
                      <Button
                        variant="secondary"
                        disabled={busy}
                        onClick={() =>
                          void run(
                            () => updateWorkspace(current.workspace_id, {
                              status: current.status === "ACTIVE" ? "ARCHIVED" : "ACTIVE",
                            }),
                            current.status === "ACTIVE" ? t("Đã lưu trữ workspace") : t("Đã mở lại workspace"),
                            t("Không đổi được trạng thái workspace."),
                          )
                        }
                      >
                        {current.status === "ACTIVE" ? t("Lưu trữ") : t("Mở lại")}
                      </Button>
                    )}
                    {current.is_default && (
                      <span className="text-xs text-slate-500">
                        {t("Workspace mặc định không lưu trữ được — dữ liệu chưa mang project_id vẫn đang rơi về đây.")}
                      </span>
                    )}
                  </div>
                </div>

                {/* ---------------------------------------------------- projects */}
                <div className="space-y-3">
                  <h3 className="text-base font-semibold text-slate-900">{t("Project trong workspace này")}</h3>
                  {projects.length === 0 ? (
                    <EmptyState
                      title={t("Chưa có project nào")}
                      description={t("Project là phạm vi hoạt động hẹp nhất — ví dụ một đợt thu bảng chữ cái.")}
                    />
                  ) : (
                    <div className="overflow-x-auto rounded-lg border border-slate-200">
                      <table className="w-full text-sm">
                        <thead className="bg-slate-50 text-left text-slate-600">
                          <tr>
                            <th className="px-3 py-2">{t("Tên")}</th>
                            <th className="px-3 py-2">{t("Trạng thái")}</th>
                            <th className="px-3 py-2 text-right">{t("Vai")}</th>
                            <th className="px-3 py-2 text-right">{t("Thao tác")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {projects.map((p) => (
                            <tr key={p.project_id} className="border-t border-slate-100">
                              <td className="px-3 py-2">
                                <span className="font-medium text-slate-900">{p.name}</span>
                                {p.is_default && (
                                  <span className="ml-2 text-xs text-slate-400">{t("mặc định")}</span>
                                )}
                                <div className="text-xs text-slate-500">{p.description}</div>
                              </td>
                              <td className="px-3 py-2">
                                <Badge variant={STATUS_TONE[p.status] ?? "default"} size="sm">
                                  {t(p.status)}
                                </Badge>
                              </td>
                              <td className="px-3 py-2 text-right">{p.member_count}</td>
                              <td className="px-3 py-2 text-right">
                                <div className="flex items-center justify-end gap-3">
                                  <button
                                    type="button"
                                    onClick={() => setScopeProject(
                                      scopeProject === p.project_id ? "" : p.project_id,
                                    )}
                                    className="text-xs font-medium text-ctu-blue hover:underline"
                                  >
                                    {scopeProject === p.project_id ? t("Bỏ chọn") : t("Xem vai")}
                                  </button>
                                  {canEdit && !p.is_default && (
                                    <button
                                      type="button"
                                      disabled={busy}
                                      onClick={() =>
                                        void run(
                                          () => updateProject(current.workspace_id, p.project_id, {
                                            status: p.status === "ACTIVE" ? "ARCHIVED" : "ACTIVE",
                                          }),
                                          p.status === "ACTIVE" ? t("Đã lưu trữ project") : t("Đã mở lại project"),
                                          t("Không đổi được trạng thái project."),
                                        )
                                      }
                                      className="text-xs font-medium text-slate-600 hover:underline"
                                    >
                                      {p.status === "ACTIVE" ? t("Lưu trữ") : t("Mở lại")}
                                    </button>
                                  )}
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {canEdit && current.status === "ACTIVE" && (
                    <form
                      className="flex flex-wrap gap-2"
                      onSubmit={(e) => {
                        e.preventDefault();
                        void run(
                          () => createProject(current.workspace_id, prjName, prjDesc)
                            .then(() => { setPrjName(""); setPrjDesc(""); }),
                          t("Đã tạo project"),
                          t("Không tạo được project."),
                        );
                      }}
                    >
                      <input
                        value={prjName}
                        onChange={(e) => setPrjName(e.target.value)}
                        placeholder={t("Tên project")}
                        aria-label={t("Tên project")}
                        className="min-w-[160px] flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
                      />
                      <input
                        value={prjDesc}
                        onChange={(e) => setPrjDesc(e.target.value)}
                        placeholder={t("Mô tả (tuỳ chọn)")}
                        aria-label={t("Mô tả project")}
                        className="min-w-[160px] flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
                      />
                      <Button type="submit" disabled={busy || !prjName.trim()}>
                        {t("Thêm project")}
                      </Button>
                    </form>
                  )}
                </div>

                {/* ------------------------------------------------------- vai */}
                <div className="space-y-3">
                  <h3 className="text-base font-semibold text-slate-900">
                    {scopeProject
                      ? t("Vai ở cấp PROJECT")
                      : t("Vai ở cấp WORKSPACE")}
                  </h3>
                  <p className="text-sm text-slate-500">
                    {t("Người được gán phải ĐÃ là thành viên của tổ chức. Gán vai ở đây không phải một đường đưa người lạ vào tổ chức.")}
                  </p>

                  {members.length === 0 ? (
                    <EmptyState
                      title={t("Chưa gán vai nào ở phạm vi này")}
                      description={t("Gán vai để phân biệt ai làm được gì bên trong nhóm công việc này.")}
                    />
                  ) : (
                    <div className="overflow-x-auto rounded-lg border border-slate-200">
                      <table className="w-full text-sm">
                        <thead className="bg-slate-50 text-left text-slate-600">
                          <tr>
                            <th className="px-3 py-2">{t("Người dùng")}</th>
                            <th className="px-3 py-2">{t("Vai")}</th>
                            <th className="px-3 py-2">{t("Cấp")}</th>
                            <th className="px-3 py-2 text-right">{t("Thao tác")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {members.map((m) => (
                            <tr key={m.assignment_id} className="border-t border-slate-100">
                              <td className="px-3 py-2">
                                <div className="font-medium text-slate-900">{m.username ?? t("(không tên)")}</div>
                                <div className="text-xs text-slate-500">{m.email}</div>
                              </td>
                              <td className="px-3 py-2">
                                <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{m.role_code}</code>
                              </td>
                              <td className="px-3 py-2 text-xs text-slate-500">{m.scope_level}</td>
                              <td className="px-3 py-2 text-right">
                                {canEdit && (
                                  <button
                                    type="button"
                                    disabled={busy}
                                    onClick={() =>
                                      void run(
                                        () => revokeScopeRole(current.workspace_id, m.assignment_id),
                                        t("Đã thu vai"),
                                        t("Không thu được vai."),
                                      )
                                    }
                                    className="inline-flex items-center gap-1 text-xs font-medium text-red-600 hover:underline"
                                  >
                                    <TrashIcon className="h-3.5 w-3.5" aria-hidden="true" />
                                    {t("Thu vai")}
                                  </button>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {canEdit && (
                    <form
                      className="flex flex-wrap gap-2"
                      onSubmit={(e) => {
                        e.preventDefault();
                        void run(
                          () => grantScopeRole(current.workspace_id, {
                            user_id: grantUser.trim(),
                            role_code: grantRole,
                            project_id: scopeProject || null,
                          }).then(() => setGrantUser("")),
                          t("Đã gán vai"),
                          t("Không gán được vai."),
                        );
                      }}
                    >
                      <input
                        value={grantUser}
                        onChange={(e) => setGrantUser(e.target.value)}
                        placeholder={t("Mã tài khoản (UUID) của thành viên tổ chức")}
                        aria-label={t("Mã tài khoản")}
                        className="min-w-[240px] flex-1 rounded-md border border-slate-300 px-3 py-2 font-mono text-xs"
                      />
                      <select
                        value={grantRole}
                        onChange={(e) => setGrantRole(e.target.value)}
                        aria-label={t("Vai cần gán")}
                        className="rounded-md border border-slate-300 px-3 py-2 text-sm"
                      >
                        {roles.length === 0 && <option value="">{t("(chưa có vai nào)")}</option>}
                        {roles.map((r) => (
                          <option key={r.role_id} value={r.role_code}>
                            {r.role_name || r.role_code}
                          </option>
                        ))}
                      </select>
                      <Button type="submit" disabled={busy || !grantUser.trim() || !grantRole}>
                        <CheckIcon className="mr-1 inline h-4 w-4" aria-hidden="true" />
                        {t("Gán vai")}
                      </Button>
                    </form>
                  )}
                </div>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, icon }: { label: string; value: number; icon: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
        {icon}
        {label}
      </div>
      <div className="mt-1 text-2xl font-semibold text-slate-900">{value}</div>
    </div>
  );
}
