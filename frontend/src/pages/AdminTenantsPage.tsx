/**
 * Quản trị tổ chức (tenant).
 *
 * Backend có 20 endpoint cho việc này từ đợt v4; cho tới trang này thì **không
 * có mặt giao diện nào**. Hệ quả không chỉ là bất tiện: cô lập hai mặt phẳng
 * là lõi kiến trúc của hệ thống, mà nó chưa từng được vận hành bằng tay trên
 * dữ liệu thật — triển khai hiện tại có đúng MỘT tổ chức.
 *
 * Ba nguyên tắc dựng trang, và cả ba đều là về việc xoá
 * -------------------------------------------------------
 * 1. **Con số trước câu hỏi.** Nút xoá vĩnh viễn chỉ mở ra sau khi đã tải
 *    `purge-preview` và hiện số dòng thật của từng bảng. Một hộp thoại "Bạn có
 *    chắc không?" trống rỗng là thứ người ta bấm qua theo phản xạ.
 * 2. **Nhắc lại lý do máy chủ đưa ra, đừng tự đoán.** `blockers` là danh sách
 *    câu tiếng Việt do `tenant_lifecycle` soạn (chưa xoá mềm, còn trong ân
 *    hạn, là tổ chức gốc). Giao diện hiện nguyên văn thay vì tự suy luận —
 *    hai bộ quy tắc song song sẽ lệch nhau, và bên lệch sẽ là bên này.
 * 3. **Giao diện không phải cổng kiểm soát.** Nút bị ẩn không phải là quyền bị
 *    chặn. Mọi phép kiểm thật nằm ở `require_admin` / `require_tenant_admin` /
 *    `require_sudo` phía máy chủ; ở đây chỉ ẩn thứ chắc chắn sẽ bị từ chối, để
 *    người dùng không đâm vào một lỗi 403 mà không hiểu vì sao.
 *
 * @i18n-key-table — nhãn trạng thái tổ chức và `ROLE_LABEL` là KHOÁ từ điển.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useToast } from "../hooks/useToast";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import Badge from "../components/ui/Badge";
import { BuildingIcon, DownloadIcon, RefreshIcon, TrashIcon } from "../components/ui/Icons";
import { friendlyError } from "../lib/errors";
import { FOCUS_RING, toneClasses, toneForStatus, type StatusTone } from "../theme/status";
import { Trans, useI18n } from "../i18n";
import {
  addMember,
  createInvitation,
  createTenant,
  deleteTenant,
  exportDownloadUrl,
  fetchExports,
  fetchInvitations,
  fetchMembers,
  fetchPurgePreview,
  fetchTenants,
  purgeTenant,
  removeMember,
  requestExport,
  revokeInvitation,
  NO_ROLE_OPTION,
  ROLES,
  parseRole,
  roleLabel,
  setHomeTenant,
  updateMemberRole,
  updateTenant,
  type MemberRoleOrNone,
  type PurgePreview,
  type Tenant,
  type TenantExport,
  type TenantInvitation,
  type TenantMember,
} from "../api/tenants";

const when = (iso: string | null): string =>
  iso ? new Date(iso).toLocaleString("vi-VN") : "—";

function tenantStatus(t: Tenant): { text: string; tone: StatusTone } {
  if (t.deleted_at) return { text: "đã xoá mềm", tone: "danger" };
  if (!t.is_active) return { text: "tạm dừng", tone: "warning" };
  return { text: "đang hoạt động", tone: "success" };
}

export default function AdminTenantsPage() {
  const { t } = useI18n();
  const { toast } = useToast();

  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);

  const [members, setMembers] = useState<TenantMember[]>([]);
  const [invites, setInvites] = useState<TenantInvitation[]>([]);
  const [exports, setExports] = useState<TenantExport[]>([]);
  const [preview, setPreview] = useState<PurgePreview | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  // Liên kết mời chỉ về MỘT lần. Giữ trong state cho tới khi người dùng tự
  // đóng — đóng hộ họ là làm mất hẳn giá trị đó.
  const [freshInvite, setFreshInvite] = useState<
    { email: string; acceptUrl: string; emailSent: boolean } | null
  >(null);

  const [newTenant, setNewTenant] = useState({ tenant_id: "", display_name: "" });
  // Mặc định KHÔNG vai ở cả hai biểu mẫu. Mặc định cũ là `viewer`, tức là bấm
  // "Mời" mà không đụng ô chọn vai đã cấp quyền đọc hoá đơn, nhật ký kiểm toán,
  // khoá API và trạng thái đồng thuận — một quyết định phân quyền do một giá
  // trị mặc định đưa ra. Xem `tenant_admin.NO_ROLE`.
  const [inviteForm, setInviteForm] = useState<{ email: string; role: MemberRoleOrNone }>({
    email: "", role: null,
  });
  const [addForm, setAddForm] = useState<{ user_id: string; role: MemberRoleOrNone }>({
    user_id: "", role: null,
  });
  const [purgeConfirm, setPurgeConfirm] = useState("");

  const loadTenants = useCallback(async () => {
    setLoading(true);
    try {
      setTenants(await fetchTenants(includeDeleted));
    } catch (e) {
      toast.error(friendlyError(e, t("Không tải được danh sách tổ chức")));
    } finally {
      setLoading(false);
    }
  }, [includeDeleted, toast]);

  // Số thứ tự của lượt tải chi tiết gần nhất. Xem `loadDetail`.
  const detailRun = useRef(0);

  const loadDetail = useCallback(async (tenantId: string) => {
    // Bốn lời gọi song song, và `allSettled` chứ không phải `all`: một quản trị
    // viên tenant KHÔNG gọi được `purge-preview` (vòng nền tảng), nên `all` sẽ
    // để một lỗi 403 dự kiến làm hỏng cả ba phần còn lại.
    //
    // TRANH CHẤP: chọn tổ chức A rồi đổi nhanh sang B thì bốn request của A vẫn
    // đang bay. Nếu chúng về SAU của B — hoàn toàn bình thường, bốn request
    // song song không có thứ tự đảm bảo — thì `setMembers` của A ghi đè lên
    // của B, và màn hình hiện thành viên của tổ chức A dưới tiêu đề tổ chức B.
    // Với một trang có nút "Xoá vĩnh viễn", nhầm lẫn đó không dừng ở thẩm mỹ.
    //
    // Cách chặn: đánh số mỗi lượt và chỉ cho lượt MỚI NHẤT ghi vào state. Rẻ
    // hơn AbortController và không phụ thuộc việc axios có huỷ được hay không.
    const run = ++detailRun.current;

    const [m, i, x, p] = await Promise.allSettled([
      fetchMembers(tenantId),
      fetchInvitations(tenantId),
      fetchExports(tenantId),
      fetchPurgePreview(tenantId),
    ]);

    if (run !== detailRun.current) return;

    setMembers(m.status === "fulfilled" ? m.value : []);
    setInvites(i.status === "fulfilled" ? i.value : []);
    setExports(x.status === "fulfilled" ? x.value : []);
    setPreview(p.status === "fulfilled" ? p.value : null);
  }, []);

  useEffect(() => { loadTenants(); }, [loadTenants]);
  useEffect(() => {
    if (!selected) return;
    setPurgeConfirm("");
    loadDetail(selected);
  }, [selected, loadDetail]);

  const run = async (key: string, fn: () => Promise<void>, ok: string) => {
    setBusy(key);
    try {
      await fn();
      toast.success(ok);
    } catch (e) {
      toast.error(friendlyError(e));
    } finally {
      setBusy(null);
    }
  };

  const current = tenants.find((t) => t.tenant_id === selected) || null;

  return (
    <div className="p-6 space-y-5">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="flex items-center gap-2 text-xl font-semibold text-slate-800">
          <BuildingIcon className="w-5 h-5 text-ctu-blue" aria-hidden="true" />
          {t("Tổ chức")}
        </h1>
        <label className="flex items-center gap-1.5 text-xs text-slate-600 cursor-pointer">
          <input type="checkbox" checked={includeDeleted}
                 className="accent-sky-600"
                 onChange={(e) => setIncludeDeleted(e.target.checked)} />
          {t("Hiện cả tổ chức đã xoá mềm")}
        </label>
        <button onClick={loadTenants} disabled={loading}
                className={`ml-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border ${toneClasses("neutral", "outline")} ${FOCUS_RING} disabled:opacity-50`}>
          <RefreshIcon className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
          {t("Tải lại")}
        </button>
      </header>

      {/* Tạo tổ chức */}
      <section className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
        <h2 className="font-semibold text-slate-700 mb-3">{t("Tạo tổ chức mới")}</h2>
        <div className="flex flex-wrap gap-2">
          <input
            aria-label={t("Mã tổ chức")}
            placeholder="ma-to-chuc"
            value={newTenant.tenant_id}
            onChange={(e) => setNewTenant({ ...newTenant, tenant_id: e.target.value })}
            className="px-3 py-1.5 rounded-md border border-slate-200 text-sm font-mono"
          />
          <input
            aria-label={t("Tên hiển thị")}
            placeholder={t("Tên hiển thị")}
            value={newTenant.display_name}
            onChange={(e) => setNewTenant({ ...newTenant, display_name: e.target.value })}
            className="px-3 py-1.5 rounded-md border border-slate-200 text-sm flex-1 min-w-[200px]"
          />
          <button
            disabled={!newTenant.tenant_id.trim() || busy === "create"}
            onClick={() => run("create", async () => {
              await createTenant(newTenant);
              setNewTenant({ tenant_id: "", display_name: "" });
              await loadTenants();
            }, t("Đã tạo tổ chức"))}
            className={`px-3 py-1.5 rounded-md text-sm font-medium border ${toneClasses("success", "solid")} ${FOCUS_RING} disabled:opacity-40`}
          >
            {t("Tạo")}
          </button>
        </div>
        <p className="text-xs text-slate-400 mt-2">
          {t("Mã tổ chức là khoá dùng trong mọi bảng dữ liệu và")} <strong>{t("không đổi được")}</strong> {t("về sau.")}
        </p>
      </section>

      {/* Danh sách */}
      <section className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
        {loading ? <LoadingSpinner /> : tenants.length === 0 ? (
          <p className="text-sm text-slate-400">{t("Chưa có tổ chức nào.")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-slate-400 text-left text-xs">
                <tr className="border-b border-slate-100">
                  <th className="py-2 pr-3 font-medium">{t("Mã")}</th>
                  <th className="py-2 pr-3 font-medium">{t("Tên")}</th>
                  <th className="py-2 pr-3 font-medium">{t("Thành viên")}</th>
                  <th className="py-2 pr-3 font-medium">{t("Trạng thái")}</th>
                  <th className="py-2 pr-3 font-medium">{t("Tạo lúc")}</th>
                  <th className="py-2 pr-3" />
                </tr>
              </thead>
              <tbody>
                {/* `row` chứ không phải `t`: `t` là hàm dịch trong phạm vi này. */}
                {tenants.map((row) => {
                  const st = tenantStatus(row);
                  return (
                    <tr key={row.tenant_id}
                        className={`border-b border-slate-50 ${selected === row.tenant_id ? "bg-slate-50" : ""}`}>
                      <td className="py-2 pr-3 font-mono text-slate-700">{row.tenant_id}</td>
                      <td className="py-2 pr-3 text-slate-600">{row.display_name}</td>
                      <td className="py-2 pr-3 tabular-nums text-slate-600">{row.member_count}</td>
                      <td className="py-2 pr-3">
                        <Badge variant={st.tone} size="sm">{t(st.text)}</Badge>
                      </td>
                      <td className="py-2 pr-3 text-slate-400 text-xs tabular-nums">{when(row.created_at)}</td>
                      <td className="py-2 pr-3 text-right">
                        <button
                          onClick={() => setSelected(selected === row.tenant_id ? null : row.tenant_id)}
                          className="px-2 py-1 rounded-md text-xs font-medium bg-slate-50 text-slate-600 border border-slate-200 hover:bg-slate-100"
                        >
                          {selected === row.tenant_id ? t("Đóng") : t("Quản lý")}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {current && (
        <>
          {/* Thành viên */}
          <section className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h2 className="font-semibold text-slate-700 mb-3">
              {t("Thành viên —")} <span className="font-mono text-slate-500">{current.tenant_id}</span>
            </h2>
            {members.length === 0 ? (
              <p className="text-sm text-slate-400 mb-3">{t("Chưa có thành viên nào.")}</p>
            ) : (
              <div className="space-y-1.5 mb-4">
                {members.map((m) => (
                  <div key={m.user_id} className="flex items-center gap-2 text-sm border-b border-slate-50 pb-1.5">
                    <span className="text-slate-700">{m.username || m.user_id}</span>
                    <span className="text-slate-400 text-xs">{m.email}</span>
                    <select
                      aria-label={t("Vai của {username}", { username: m.username || m.user_id })}
                      value={m.role ?? NO_ROLE_OPTION}
                      disabled={busy === `role-${m.user_id}`}
                      onChange={(e) => run(`role-${m.user_id}`, async () => {
                        await updateMemberRole(current.tenant_id, m.user_id, parseRole(e.target.value));
                        await loadDetail(current.tenant_id);
                      }, t("Đã đổi vai"))}
                      className="ml-auto px-2 py-1 rounded-md border border-slate-200 text-xs"
                    >
                      {/* Mục rỗng đứng ĐẦU, và nó là một lựa chọn thật: chọn nó
                          là GỠ vai mà vẫn giữ tư cách thành viên. */}
                      <option value={NO_ROLE_OPTION}>{t(roleLabel(null))}</option>
                      {ROLES.map((r) => <option key={r} value={r}>{t(roleLabel(r))}</option>)}
                    </select>
                    <button
                      disabled={busy === `rm-${m.user_id}`}
                      onClick={() => run(`rm-${m.user_id}`, async () => {
                        await removeMember(current.tenant_id, m.user_id);
                        await loadDetail(current.tenant_id);
                        await loadTenants();
                      }, t("Đã gỡ thành viên"))}
                      className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium border ${toneClasses("danger", "outline")} ${FOCUS_RING} disabled:opacity-50`}
                    >
                      <TrashIcon className="w-3.5 h-3.5" aria-hidden="true" />
                      {t("Gỡ")}
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="flex flex-wrap gap-2 items-center">
              <input
                aria-label={t("ID tài khoản")}
                placeholder={t("ID tài khoản có sẵn")}
                value={addForm.user_id}
                onChange={(e) => setAddForm({ ...addForm, user_id: e.target.value })}
                className="px-3 py-1.5 rounded-md border border-slate-200 text-sm font-mono flex-1 min-w-[220px]"
              />
              <select value={addForm.role ?? NO_ROLE_OPTION} aria-label={t("Vai khi gắn")}
                      onChange={(e) => setAddForm({ ...addForm, role: parseRole(e.target.value) })}
                      className="px-2 py-1.5 rounded-md border border-slate-200 text-sm">
                <option value={NO_ROLE_OPTION}>{t(roleLabel(null))}</option>
                {ROLES.map((r) => <option key={r} value={r}>{t(roleLabel(r))}</option>)}
              </select>
              <button
                disabled={!addForm.user_id.trim() || busy === "add"}
                onClick={() => run("add", async () => {
                  await addMember(current.tenant_id, addForm.user_id.trim(), addForm.role);
                  setAddForm({ user_id: "", role: null });
                  await loadDetail(current.tenant_id);
                  await loadTenants();
                }, t("Đã gắn tài khoản vào tổ chức"))}
                className={`px-3 py-1.5 rounded-md text-sm font-medium border ${toneClasses("success", "solid")} ${FOCUS_RING} disabled:opacity-40`}
              >
                {t("Gắn tài khoản")}
              </button>
              {/* Hai nút, hai việc khác nhau — đừng gộp. "Gắn" cho tài khoản một
                  chỗ ngồi ở đây; "Chuyển về đây" đổi nơi DỮ LIỆU TƯƠNG LAI của họ
                  đổ vào. Một người có thể là thành viên nhiều tổ chức nhưng chỉ
                  có một tổ chức nhà. */}
              <button
                disabled={!addForm.user_id.trim() || busy === "home"}
                onClick={() => run("home", async () => {
                  await setHomeTenant(addForm.user_id.trim(), current.tenant_id, addForm.role);
                  setAddForm({ user_id: "", role: null });
                  await loadDetail(current.tenant_id);
                  await loadTenants();
                }, t("Đã chuyển tổ chức nhà của tài khoản"))}
                className={`px-3 py-1.5 rounded-md text-sm font-medium border ${toneClasses("neutral", "outline")} ${FOCUS_RING} disabled:opacity-40`}
              >
                {t("Chuyển tổ chức nhà về đây")}
              </button>
            </div>
            <p className="text-xs text-slate-400 mt-2">
              {t("Gắn thẳng theo ID là thao tác của quản trị viên nền tảng. Cách đưa người vào dành cho quản trị viên tổ chức là")} <strong>{t("lời mời")}</strong> {t("bên dưới — nó đòi hỏi chính người được mời phải hành động.")}
            </p>
            <p className="text-xs text-slate-400 mt-1">
              <strong>{t("Chuyển tổ chức nhà")}</strong> {t("khác với gắn: nó quyết định dữ liệu tài khoản đó thu về sau này thuộc tổ chức nào. Dữ liệu đã thu trước đó vẫn nằm ở tổ chức cũ.")}
            </p>
          </section>

          {/* Lời mời */}
          <section className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h2 className="font-semibold text-slate-700 mb-3">{t("Lời mời")}</h2>

            {freshInvite && (
              <div className="mb-3 p-3 rounded-lg bg-amber-50 border border-amber-200">
                <p className="text-xs text-amber-800 font-medium mb-1">
                  {freshInvite.emailSent
                    ? t("Đã gửi thư mời tới {email}", { email: freshInvite.email })
                    : t("Đường liên kết mời cho {email} — chỉ hiện một lần duy nhất", { email: freshInvite.email })}
                </p>

                {/* Thư gửi được hay không quyết định câu tiếp theo, nên nó phải
                    khác nhau thật sự. Nói "đã gửi" khi SMTP chưa cấu hình là để
                    người được mời ngồi đợi một lá thư không tồn tại. */}
                <p className="mb-1.5 text-xs text-amber-700">
                  {freshInvite.emailSent
                    ? t("Người được mời đã có liên kết trong hộp thư. Bản dưới đây là bản dự phòng, phòng khi thư vào mục rác.")
                    : t("Hệ thống chưa gửi được thư (thường là do chưa cấu hình SMTP). Lời mời VẪN hợp lệ — hãy chép liên kết dưới đây và gửi bằng tay.")}
                </p>

                <code className="block text-xs font-mono break-all text-amber-900 bg-white/70 rounded px-2 py-1">
                  {freshInvite.acceptUrl}
                </code>
                <p className="mt-1.5 text-xs text-amber-700">
                  {t("Gửi nguyên cả đường liên kết. Mã nằm sau dấu thăng nên trình duyệt không gửi nó lên máy chủ nào — cắt bớt là hỏng.")}
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <button
                    onClick={() => {
                      void navigator.clipboard
                        .writeText(freshInvite.acceptUrl)
                        .then(() => toast.success(t("Đã sao chép đường liên kết mời")))
                        // Chép được hay không phụ thuộc quyền của trình duyệt và
                        // ngữ cảnh bảo mật. Hỏng thì nói ra — mã vẫn nằm trên màn
                        // hình để chép tay, nhưng một nút im lặng không làm gì cả
                        // sẽ khiến người dùng tưởng mình đã có nó trong bộ nhớ tạm.
                        .catch(() => toast.error(t("Trình duyệt không cho sao chép. Hãy chọn và chép thủ công.")));
                    }}
                    className={`px-2 py-1 rounded-md text-xs font-medium border ${toneClasses("success", "outline")} ${FOCUS_RING}`}
                  >
                    {t("Sao chép liên kết")}
                  </button>
                  <button onClick={() => setFreshInvite(null)}
                          className="px-2 py-1 rounded-md text-xs font-medium bg-amber-100 text-amber-800 border border-amber-300">
                    {t("Tôi đã lưu liên kết này")}
                  </button>
                </div>
              </div>
            )}

            {invites.length === 0 ? (
              <p className="text-sm text-slate-400 mb-3">{t("Không có lời mời đang mở.")}</p>
            ) : (
              <div className="space-y-1.5 mb-4">
                {invites.map((iv) => (
                  <div key={iv.invitation_id} className="flex items-center gap-2 text-sm border-b border-slate-50 pb-1.5">
                    <span className="text-slate-700">{iv.email}</span>
                    <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 text-xs">{t(roleLabel(iv.role))}</span>
                    <span className="text-slate-400 text-xs ml-auto">
                      {t("hết hạn {khi}", { khi: when(iv.expires_at) })}
                    </span>
                    <button
                      disabled={busy === `rv-${iv.invitation_id}`}
                      onClick={() => run(`rv-${iv.invitation_id}`, async () => {
                        await revokeInvitation(current.tenant_id, iv.invitation_id);
                        await loadDetail(current.tenant_id);
                      }, t("Đã thu hồi lời mời"))}
                      className="px-2 py-1 rounded-md text-xs font-medium bg-slate-50 text-slate-600 border border-slate-200 hover:bg-slate-100 disabled:opacity-50"
                    >
                      {t("Thu hồi")}
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="flex flex-wrap gap-2 items-center">
              <input
                aria-label={t("Email được mời")}
                type="email"
                placeholder="email@vidu.vn"
                value={inviteForm.email}
                onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })}
                className="px-3 py-1.5 rounded-md border border-slate-200 text-sm flex-1 min-w-[220px]"
              />
              <select value={inviteForm.role ?? NO_ROLE_OPTION} aria-label={t("Vai khi mời")}
                      onChange={(e) => setInviteForm({ ...inviteForm, role: parseRole(e.target.value) })}
                      className="px-2 py-1.5 rounded-md border border-slate-200 text-sm">
                <option value={NO_ROLE_OPTION}>{t(roleLabel(null))}</option>
                {ROLES.map((r) => <option key={r} value={r}>{t(roleLabel(r))}</option>)}
              </select>
              <button
                disabled={!inviteForm.email.trim() || busy === "invite"}
                onClick={() => run("invite", async () => {
                  const created = await createInvitation(
                    current.tenant_id, inviteForm.email.trim(), inviteForm.role);
                  setFreshInvite({
                    email: created.email,
                    acceptUrl: created.accept_url,
                    emailSent: created.email_sent,
                  });
                  setInviteForm({ email: "", role: null });
                  await loadDetail(current.tenant_id);
                }, t("Đã tạo lời mời"))}
                className={`px-3 py-1.5 rounded-md text-sm font-medium border ${toneClasses("success", "solid")} ${FOCUS_RING} disabled:opacity-40`}
              >
                {t("Mời")}
              </button>
            </div>
          </section>

          {/* Xuất dữ liệu */}
          <section className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <div className="flex flex-wrap items-center gap-2 mb-3">
              <h2 className="font-semibold text-slate-700">{t("Xuất dữ liệu")}</h2>
              <div className="ml-auto flex gap-2">
                {(["metadata", "full"] as const).map((scope) => (
                  <button key={scope}
                    disabled={busy === `ex-${scope}`}
                    onClick={() => run(`ex-${scope}`, async () => {
                      await requestExport(current.tenant_id, scope);
                      await loadDetail(current.tenant_id);
                    }, t("Đã đặt hàng bản xuất; theo dõi trạng thái bên dưới"))}
                    className="px-3 py-1.5 rounded-md text-xs font-medium bg-slate-50 text-slate-600 border border-slate-200 hover:bg-slate-100 disabled:opacity-50"
                  >
                    {scope === "metadata" ? t("Xuất siêu dữ liệu") : t("Xuất toàn bộ")}
                  </button>
                ))}
              </div>
            </div>
            {exports.length === 0 ? (
              <p className="text-sm text-slate-400">{t("Chưa có bản xuất nào.")}</p>
            ) : (
              <div className="space-y-1.5">
                {exports.map((x) => (
                  <div key={x.export_id} className="flex items-center gap-2 text-xs border-b border-slate-50 pb-1.5">
                    <span className="text-slate-400 tabular-nums">{when(x.created_at)}</span>
                    <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">{x.scope}</span>
                    <span className={`px-1.5 py-0.5 rounded font-medium border ${toneClasses(toneForStatus(x.status), "soft")}`}>
                      {x.status}
                    </span>
                    {/* KHÔNG hiện `x.error` nguyên văn. Đó là chuỗi do tác vụ
                        nền ghi lại — nó mang được tên bảng, đường dẫn trong
                        container, hay vết ngăn xếp. Người dùng cần biết "hỏng
                        rồi, xuất lại đi", không cần biết hỏng ở dòng nào. */}
                    {x.error && (
                      <span className="text-red-700">
                        {t("Bản xuất thất bại — hãy thử đặt lại.")}
                      </span>
                    )}
                    {/* Chỉ hiện nút tải khi bản xuất THẬT SỰ sẵn sàng. Máy chủ
                        trả 202 lúc đặt hàng, không phải 201 — chưa có tệp nào. */}
                    {x.status === "ready" && (
                      <a href={exportDownloadUrl(current.tenant_id, x.export_id)}
                         className={`ml-auto inline-flex items-center gap-1 px-2 py-1 rounded-md font-medium border ${toneClasses("success", "outline")}`}>
                        <DownloadIcon className="w-3.5 h-3.5" aria-hidden="true" />
                        {t("Tải về")}
                      </a>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Vùng nguy hiểm */}
          <section className="bg-white rounded-xl shadow-sm border border-red-200 p-5">
            <h2 className="font-semibold text-red-700 mb-3">{t("Vùng nguy hiểm")}</h2>

            <div className="flex flex-wrap gap-2 items-center mb-4">
              <button
                disabled={busy === "toggle"}
                onClick={() => run("toggle", async () => {
                  await updateTenant(current.tenant_id, { is_active: !current.is_active });
                  await loadTenants();
                }, current.is_active ? t("Đã tạm dừng tổ chức") : t("Đã bật lại tổ chức"))}
                className={`px-3 py-1.5 rounded-md text-sm font-medium border ${toneClasses("warning", "outline")} ${FOCUS_RING} disabled:opacity-50`}
              >
                {current.is_active ? t("Tạm dừng") : t("Bật lại")}
              </button>
              {!current.deleted_at && (
                <button
                  disabled={busy === "soft"}
                  onClick={() => run("soft", async () => {
                    await deleteTenant(current.tenant_id);
                    // Bật sẵn "hiện cả tổ chức đã xoá mềm". Không có dòng này,
                    // tổ chức vừa xoá biến khỏi danh sách ngay lập tức và người
                    // dùng phải tự đoán ra cái ô tích để tìm lại nó — trong khi
                    // xoá mềm gần như luôn là bước ĐẦU của một quy trình còn
                    // tiếp diễn (xuất dữ liệu, rồi xoá vĩnh viễn).
                    setIncludeDeleted(true);
                    await loadDetail(current.tenant_id);
                  }, t("Đã xoá mềm. Dữ liệu vẫn còn nguyên."))}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium border ${toneClasses("danger", "outline")} ${FOCUS_RING} disabled:opacity-50`}
                >
                  <TrashIcon className="w-4 h-4 inline -mt-0.5 mr-1" aria-hidden="true" />
                  {t("Xoá mềm")}
                </button>
              )}
            </div>

            {!preview ? (
              <p className="text-xs text-slate-400">
                {t("Không đọc được bản xem trước xoá vĩnh viễn — thao tác này dành cho quản trị viên nền tảng.")}
              </p>
            ) : (
              <>
                <p className="text-sm text-slate-600 mb-2">
                  <Trans
                    k="Xoá vĩnh viễn sẽ lấy đi {n} dòng dữ liệu:"
                    vars={{ n: <strong className="tabular-nums">{preview.total_rows.toLocaleString("vi-VN")}</strong> }}
                  />
                </p>
                <div className="flex flex-wrap gap-1.5 mb-3">
                  {Object.entries(preview.row_counts)
                    .filter(([, n]) => n > 0)
                    .sort((a, b) => b[1] - a[1])
                    .map(([table, n]) => (
                      <span key={table} className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 text-xs font-mono">
                        {table} <span className="tabular-nums font-semibold">{n}</span>
                      </span>
                    ))}
                </div>

                {preview.blockers.length > 0 ? (
                  <ul className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-3 space-y-1">
                    {preview.blockers.map((b, i) => <li key={i}>• {b}</li>)}
                  </ul>
                ) : (
                  <div className="flex flex-wrap gap-2 items-center">
                    <input
                      aria-label={t("Gõ lại mã tổ chức để xác nhận")}
                      placeholder={t("Gõ lại: {tenant_id}", { tenant_id: current.tenant_id })}
                      value={purgeConfirm}
                      onChange={(e) => setPurgeConfirm(e.target.value)}
                      className="px-3 py-1.5 rounded-md border border-red-300 text-sm font-mono"
                    />
                    <button
                      disabled={purgeConfirm !== current.tenant_id || busy === "purge"}
                      onClick={() => run("purge", async () => {
                        await purgeTenant(current.tenant_id, purgeConfirm);
                        setSelected(null);
                        setPurgeConfirm("");
                        await loadTenants();
                      }, t("Đã xoá vĩnh viễn tổ chức"))}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium border ${toneClasses("danger", "solid")} ${FOCUS_RING} disabled:opacity-40`}
                    >
                      <TrashIcon className="w-4 h-4" aria-hidden="true" />
                      {t("Xoá vĩnh viễn")}
                    </button>
                    {!preview.has_ready_export && (
                      <span className="text-xs text-amber-700">
                        {t("Chưa có bản xuất nào sẵn sàng — nên xuất dữ liệu trước khi xoá.")}
                      </span>
                    )}
                  </div>
                )}
              </>
            )}
          </section>
        </>
      )}
    </div>
  );
}
