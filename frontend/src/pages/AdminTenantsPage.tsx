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
import { useSearchParams } from "react-router-dom";
import { useToast } from "../hooks/useToast";
import Tabs, { useUrlTab, type TabItem } from "../components/ui/Tabs";
import { slugify } from "../utils/markdownOutline";
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
  memberIdentity,
  purgeTenant,
  removeMember,
  requestExport,
  revokeInvitation,
  searchAccounts,
  NO_ROLE_OPTION,
  ROLES,
  parseRole,
  roleDescription,
  roleLabel,
  setHomeTenant,
  updateMemberRole,
  updateTenant,
  EXPORT_AGREEMENT_TEXT,
  type AccountSearchResult,
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

/**
 * Bốn tab chi tiết. Chỉ `id` được `useUrlTab` đọc để xác nhận tham số URL còn
 * hợp lệ; nhãn thật (đã dịch, kèm số đếm) dựng riêng ở nơi gọi `<Tabs>`.
 */
const DETAIL_TAB_DEFS: readonly TabItem<"members" | "invites" | "exports" | "settings">[] = [
  { id: "members", label: "members" },
  { id: "invites", label: "invites" },
  { id: "exports", label: "exports" },
  { id: "settings", label: "settings" },
];

export default function AdminTenantsPage() {
  const { t } = useI18n();
  const { toast } = useToast();

  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [loading, setLoading] = useState(true);
  // Tổ chức đang mở nằm ở URL (?org=…), không chỉ ở state: gửi được link
  // thẳng tới "tổ chức X" cho đồng nghiệp, và bấm back/forward trình duyệt quay
  // đúng chỗ vừa xem thay vì rơi về danh sách trống.
  const [urlParams, setUrlParams] = useSearchParams();
  const selected = urlParams.get("org");
  const setSelected = useCallback((tenantId: string | null) => {
    setUrlParams((prev) => {
      const next = new URLSearchParams(prev);
      if (tenantId) next.set("org", tenantId);
      else { next.delete("org"); next.delete("tab"); }
      return next;
    });
  }, [setUrlParams]);

  const [members, setMembers] = useState<TenantMember[]>([]);
  const [invites, setInvites] = useState<TenantInvitation[]>([]);
  const [exports, setExports] = useState<TenantExport[]>([]);
  const [preview, setPreview] = useState<PurgePreview | null>(null);
  // Chi tiết đang hiện THUỘC tổ chức nào, và từng khối có lỗi gì (TEN-03).
  //
  // Bản trước để nguyên thành viên của A trên màn hình trong lúc tải B, và
  // đổi mọi lỗi request thành mảng rỗng — "mất mạng" đọc lên y hệt "chưa có
  // thành viên". Với một trang có nút "Xoá vĩnh viễn", hai điều đó không dừng
  // ở thẩm mỹ. Nay: đổi lựa chọn là xoá sạch, khối nào lỗi thì khối đó nói,
  // và mọi thao tác bị khoá cho tới khi chi tiết khớp tổ chức đang chọn.
  type DetailErrors = Partial<Record<"members" | "invites" | "exports" | "preview", string>>;
  const [detail, setDetail] = useState<{
    tenantId: string | null;
    loading: boolean;
    errors: DetailErrors;
  }>({ tenantId: null, loading: false, errors: {} });
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
  // Tìm tài khoản để "Gắn" bằng email/tên đăng nhập thay vì ID thô — người
  // quản trị nhớ được cái trước, không nhớ được UUID. `accountPicked` giữ mục
  // đã chọn để hiện tên thay vì lại hiện một chuỗi mã.
  const [accountQuery, setAccountQuery] = useState("");
  const [accountResults, setAccountResults] = useState<AccountSearchResult[]>([]);
  const [accountSearching, setAccountSearching] = useState(false);
  const [accountPicked, setAccountPicked] = useState<AccountSearchResult | null>(null);
  const [purgeConfirm, setPurgeConfirm] = useState("");
  // Cam kết sử dụng dữ liệu — phải tự tay tích lại mỗi lần mở tổ chức khác,
  // không giữ từ tổ chức trước: đồng ý cho gói của A không phải đồng ý cho B.
  const [exportAgree, setExportAgree] = useState(false);
  const [detailTab, setDetailTab] = useUrlTab("tab", DETAIL_TAB_DEFS, "members");
  // Tên hiển thị đang sửa ở tab Cài đặt — tách khỏi `current.display_name` để
  // gõ dở không tự ghi đè tên thật cho tới khi bấm Lưu.
  const [nameDraft, setNameDraft] = useState("");
  /** Lọc danh sách theo tên hoặc mã — người mới tìm theo TÊN, không nhớ mã. */
  const [query, setQuery] = useState("");

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

  const current = tenants.find((t) => t.tenant_id === selected) || null;
  const visibleTenants = tenants.filter((row) => {
    // Không phân biệt dấu và hoa/thường: "truong c" phải ra "Trường C".
    const q = slugify(query);
    if (!query.trim()) return true;
    return slugify(row.display_name || "").includes(q) || slugify(row.tenant_id).includes(q);
  });

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
    setDetail({ tenantId, loading: true, errors: {} });
    setMembers([]);
    setInvites([]);
    setExports([]);
    setPreview(null);

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

    const errors: DetailErrors = {};
    if (m.status === "rejected") errors.members = friendlyError(m.reason, t("Không tải được danh sách thành viên"));
    if (i.status === "rejected") errors.invites = friendlyError(i.reason, t("Không tải được lời mời"));
    if (x.status === "rejected") errors.exports = friendlyError(x.reason, t("Không tải được bản xuất"));
    // `purge-preview` bị 403 với quản trị viên tenant là DỰ KIẾN — không phải
    // lỗi; khối đó tự nói "dành cho quản trị viên nền tảng". Lỗi khác thì báo.
    if (p.status === "rejected" && (p.reason as { response?: { status?: number } })?.response?.status !== 403) {
      errors.preview = friendlyError(p.reason, t("Không tải được bản xem trước xoá"));
    }
    setDetail({ tenantId, loading: false, errors });
  }, [t]);

  /** Chi tiết trên màn hình đúng là của tổ chức đang chọn, và đã tải xong. */
  const detailReady = !!current && detail.tenantId === current.tenant_id && !detail.loading;

  const BlockError = ({ text }: { text: string }) => (
    <p role="alert" className="mb-3 flex flex-wrap items-center gap-2 text-sm text-red-700">
      <span>{text}</span>
      {current && (
        <button
          type="button"
          onClick={() => void loadDetail(current.tenant_id)}
          className="rounded border border-red-200 px-2 py-0.5 text-xs font-medium hover:bg-red-50"
        >
          {t("Thử lại")}
        </button>
      )}
    </p>
  );

  useEffect(() => { loadTenants(); }, [loadTenants]);
  useEffect(() => {
    if (!selected) return;
    setPurgeConfirm("");
    setAddForm({ user_id: "", role: null });
    setAccountQuery("");
    setAccountResults([]);
    setAccountPicked(null);
    setExportAgree(false);
    loadDetail(selected);
  }, [selected, loadDetail]);

  // Nháp tên hiển thị theo đúng tổ chức đang mở. Đổi tổ chức phải nạp lại từ
  // dữ liệu máy chủ, không giữ nháp dở dang của tổ chức vừa rời đi.
  useEffect(() => {
    setNameDraft(current?.display_name ?? "");
  }, [current?.tenant_id, current?.display_name]);

  // Tìm tài khoản theo email/tên đăng nhập, có trễ để không gọi API mỗi phím
  // gõ. Đã chọn một mục rồi thì ngưng tìm — đổi ô tìm sau khi chọn nghĩa là
  // người dùng muốn chọn lại, xử lý ở nút "Đổi" thay vì tự tìm ngầm.
  useEffect(() => {
    if (accountPicked) return;
    const q = accountQuery.trim();
    if (q.length < 2) { setAccountResults([]); return; }
    setAccountSearching(true);
    const id = setTimeout(() => {
      searchAccounts(q)
        .then(setAccountResults)
        .catch(() => setAccountResults([]))
        .finally(() => setAccountSearching(false));
    }, 300);
    return () => clearTimeout(id);
  }, [accountQuery, accountPicked]);

  // Bản xuất "full" chạy khoảng một phút. Một bảng chỉ nạp một lần thì không
  // phân biệt được với một bảng hỏng — hỏi lại chừng nào còn việc chưa xong.
  const hasPendingExport = exports.some(
    (ex) => ex.status === "pending" || ex.status === "running",
  );
  useEffect(() => {
    if (!hasPendingExport || !selected) return;
    const id = setInterval(() => {
      fetchExports(selected).then(setExports).catch(() => undefined);
    }, 3000);
    return () => clearInterval(id);
  }, [hasPendingExport, selected]);

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

      {/* Tạo tổ chức — hiếm dùng, gấp lại để danh sách đứng đầu trang. */}
      <details className="bg-white rounded-xl shadow-sm border border-slate-200">
        <summary className="cursor-pointer px-5 py-4 font-semibold text-slate-700">{t("Tạo tổ chức mới")}</summary>
        <div className="px-5 pb-5">
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
        </div>
      </details>

      {/* Danh sách */}
      <section className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("Tìm theo tên hoặc mã tổ chức")}
            aria-label={t("Tìm tổ chức")}
            className="w-full max-w-sm rounded-lg border border-slate-300 px-3 py-2 text-sm placeholder:text-slate-400 focus:border-ctu-blue focus:outline-none focus:ring-2 focus:ring-ctu-blue/30"
          />
          <span className="text-xs text-slate-500">
            {t("{n} tổ chức", { n: visibleTenants.length })}
          </span>
        </div>
        {loading ? <LoadingSpinner /> : tenants.length === 0 ? (
          <p className="text-sm text-slate-400">{t("Chưa có tổ chức nào.")}</p>
        ) : visibleTenants.length === 0 ? (
          <p className="text-sm text-slate-400">{t("Không có tổ chức nào khớp với từ khoá.")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-slate-400 text-left text-xs">
                <tr className="border-b border-slate-100">
                  <th className="py-2 pr-3 font-medium">{t("Tên")}</th>
                  <th className="py-2 pr-3 font-medium">{t("Mã")}</th>
                  <th className="py-2 pr-3 font-medium">{t("Thành viên")}</th>
                  <th className="py-2 pr-3 font-medium">{t("Trạng thái")}</th>
                  <th className="py-2 pr-3 font-medium">{t("Tạo lúc")}</th>
                  <th className="py-2 pr-3" />
                </tr>
              </thead>
              <tbody>
                {/* `row` chứ không phải `t`: `t` là hàm dịch trong phạm vi này. */}
                {visibleTenants.map((row) => {
                  const st = tenantStatus(row);
                  return (
                    <tr key={row.tenant_id}
                        className={`border-b border-slate-50 ${selected === row.tenant_id ? "bg-slate-50" : ""}`}>
                      <td className="py-2 pr-3 font-medium text-slate-800">{row.display_name || row.tenant_id}</td>
                      <td className="py-2 pr-3 font-mono text-xs text-slate-500">{row.tenant_id}</td>
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
                          {selected === row.tenant_id ? t("Đóng") : t("Mở tổ chức")}
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
        <fieldset disabled={!detailReady} className="contents" data-testid="tenant-detail" data-ready={detailReady ? "1" : "0"}>
          {detail.loading && (
            <p role="status" className="text-sm text-slate-500">
              {t("Đang tải chi tiết của {ten}…", { ten: current.display_name || current.tenant_id })}
            </p>
          )}
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-lg font-semibold text-slate-900">
                {current.display_name || current.tenant_id}
                <span className="ml-2 font-mono text-xs font-normal text-slate-400">{current.tenant_id}</span>
              </h2>
              <button type="button" onClick={() => setSelected(null)}
                      className="rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50">
                {t("Đóng chi tiết")}
              </button>
            </div>
            <Tabs
              tabs={[
                { id: "members", label: t("Thành viên"), count: members.length },
                { id: "invites", label: t("Lời mời"), count: invites.length },
                { id: "exports", label: t("Xuất dữ liệu") },
                { id: "settings", label: t("Cài đặt") },
              ]}
              value={detailTab}
              onChange={setDetailTab}
              label={t("Mục của tổ chức đang mở")}
            >
              <div className="space-y-6">
          {detailTab === "members" && (<>
          {/* Thành viên */}
          <section className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h2 className="font-semibold text-slate-700 mb-3">
              {t("Thành viên —")} <span className="font-mono text-slate-500">{current.tenant_id}</span>
            </h2>
            {detail.errors.members ? (
              <BlockError text={detail.errors.members} />
            ) : detail.loading ? null : members.length === 0 ? (
              <p className="text-sm text-slate-400 mb-3">{t("Chưa có thành viên nào.")}</p>
            ) : (
              <div className="space-y-1.5 mb-4">
                {members.map((m) => (
                  <div key={m.user_id} className="flex flex-wrap items-center gap-2 text-sm border-b border-slate-50 py-1.5">
                    <span className="min-w-0">
                      <span className="block truncate text-slate-700">{memberIdentity(m).primary}</span>
                      {memberIdentity(m).secondary ? (
                        <span className="block truncate text-xs text-slate-500">
                          {memberIdentity(m).secondary}
                        </span>
                      ) : null}
                    </span>
                    <span className="text-slate-400 text-xs">{m.email}</span>
                    <select
                      aria-label={t("Vai của {username}", { username: memberIdentity(m).primary })}
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
              {accountPicked ? (
                <span className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm">
                  <span className="font-medium text-slate-700">{accountPicked.email || accountPicked.username || accountPicked.id}</span>
                  {accountPicked.username && accountPicked.email && (
                    <span className="text-slate-400">({accountPicked.username})</span>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      setAccountPicked(null);
                      setAddForm({ ...addForm, user_id: "" });
                      setAccountQuery("");
                    }}
                    className="text-xs font-medium text-ctu-blue hover:underline"
                  >
                    {t("Đổi")}
                  </button>
                </span>
              ) : (
                <div className="relative min-w-[220px] flex-1">
                  <input
                    aria-label={t("Tìm tài khoản theo email hoặc tên đăng nhập")}
                    placeholder={t("Tìm theo email hoặc tên đăng nhập")}
                    value={accountQuery}
                    onChange={(e) => setAccountQuery(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-md border border-slate-200 text-sm"
                  />
                  {(accountSearching || accountResults.length > 0) && accountQuery.trim().length >= 2 && (
                    <div className="absolute z-10 mt-1 w-full max-h-56 overflow-y-auto rounded-md border border-slate-200 bg-white shadow-lg">
                      {accountSearching ? (
                        <p className="px-3 py-2 text-xs text-slate-400">{t("Đang tìm…")}</p>
                      ) : accountResults.length === 0 ? (
                        <p className="px-3 py-2 text-xs text-slate-400">{t("Không khớp tài khoản nào.")}</p>
                      ) : (
                        accountResults.map((acc) => (
                          <button
                            key={acc.id}
                            type="button"
                            onClick={() => {
                              setAccountPicked(acc);
                              setAddForm({ ...addForm, user_id: acc.id });
                            }}
                            className="block w-full px-3 py-1.5 text-left text-sm hover:bg-slate-50"
                          >
                            <span className="font-medium text-slate-700">{acc.email || acc.username}</span>
                            {acc.username && acc.email && (
                              <span className="ml-1.5 text-xs text-slate-400">{acc.username}</span>
                            )}
                            {!acc.is_active && (
                              <span className="ml-1.5 text-xs text-amber-600">{t("đã khoá")}</span>
                            )}
                          </button>
                        ))
                      )}
                    </div>
                  )}
                </div>
              )}
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
                  setAccountPicked(null);
                  setAccountQuery("");
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
                  setAccountPicked(null);
                  setAccountQuery("");
                  await loadDetail(current.tenant_id);
                  await loadTenants();
                }, t("Đã chuyển tổ chức nhà của tài khoản"))}
                className={`px-3 py-1.5 rounded-md text-sm font-medium border ${toneClasses("neutral", "outline")} ${FOCUS_RING} disabled:opacity-40`}
              >
                {t("Chuyển tổ chức nhà về đây")}
              </button>
              <p className="mt-2 w-full text-xs text-slate-600" data-testid="role-hint-add">
                {roleDescription(addForm.role)}
              </p>
            </div>
            <p className="text-xs text-slate-400 mt-2">
              {t("Gắn thẳng là thao tác của quản trị viên nền tảng. Cách đưa người vào dành cho quản trị viên tổ chức là")} <strong>{t("lời mời")}</strong> {t("bên dưới — nó đòi hỏi chính người được mời phải hành động.")}
            </p>
            <p className="text-xs text-slate-400 mt-1">
              <strong>{t("Chuyển tổ chức nhà")}</strong> {t("khác với gắn: nó quyết định dữ liệu tài khoản đó thu về sau này thuộc tổ chức nào. Dữ liệu đã thu trước đó vẫn nằm ở tổ chức cũ.")}
            </p>
          </section>

          </>)}
          {detailTab === "invites" && (<>
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

            {detail.errors.invites ? (
              <BlockError text={detail.errors.invites} />
            ) : detail.loading ? null : invites.length === 0 ? (
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
              <p className="mt-2 w-full text-xs text-slate-600" data-testid="role-hint-invite">
                {roleDescription(inviteForm.role)}
              </p>
            </div>
          </section>

          </>)}
          {detailTab === "exports" && (<>
          {/* Xuất dữ liệu */}
          <section className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <div className="flex flex-wrap items-center gap-2 mb-3">
              <h2 className="font-semibold text-slate-700">{t("Xuất dữ liệu")}</h2>
            </div>
            {/* Gói này chứa dữ liệu của NHIỀU người đóng góp, không chỉ của
                người bấm nút — nên phải tự tay đồng ý mỗi lần, không có nút
                nào gọi được khi chưa tích. Máy chủ kiểm lại điều này, ô này
                chỉ là chỗ HIỆN cam kết ra trước mắt người bấm. */}
            <label className="mb-3 flex items-start gap-2 text-xs text-slate-600">
              <input
                type="checkbox"
                checked={exportAgree}
                onChange={(e) => setExportAgree(e.target.checked)}
                className="mt-0.5 accent-sky-600"
              />
              <span>{t(EXPORT_AGREEMENT_TEXT)}</span>
            </label>
            <div className="mb-3 flex gap-2">
              {(["metadata", "full"] as const).map((scope) => (
                <button key={scope}
                  disabled={!exportAgree || busy === `ex-${scope}`}
                  onClick={() => run(`ex-${scope}`, async () => {
                    await requestExport(current.tenant_id, scope, exportAgree);
                    await loadDetail(current.tenant_id);
                  }, t("Đã đặt hàng bản xuất; theo dõi trạng thái bên dưới"))}
                  className="px-3 py-1.5 rounded-md text-xs font-medium bg-slate-50 text-slate-600 border border-slate-200 hover:bg-slate-100 disabled:opacity-50"
                >
                  {scope === "metadata" ? t("Xuất siêu dữ liệu") : t("Xuất toàn bộ")}
                </button>
              ))}
            </div>
            {detail.errors.exports ? (
              <BlockError text={detail.errors.exports} />
            ) : detail.loading ? null : exports.length === 0 ? (
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

          </>)}
          {detailTab === "settings" && (<>
          {/* Cài đặt chung — trước đây tab này chỉ có Vùng nguy hiểm, nên bấm
              vào "Cài đặt" mong đổi tên tổ chức lại rơi thẳng vào khu vực phá
              huỷ dữ liệu. Mục này đứng riêng, phía trên, với việc duy nhất
              hiện làm được ở đây: đổi tên hiển thị. */}
          <section className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h2 className="font-semibold text-slate-700 mb-3">{t("Cài đặt chung")}</h2>
            <label className="block text-xs font-medium text-slate-600 mb-1" htmlFor="tenant-name-draft">
              {t("Tên hiển thị")}
            </label>
            <div className="flex flex-wrap gap-2 items-center">
              <input
                id="tenant-name-draft"
                value={nameDraft}
                onChange={(e) => setNameDraft(e.target.value)}
                className="px-3 py-1.5 rounded-md border border-slate-200 text-sm flex-1 min-w-[220px]"
              />
              <button
                disabled={!nameDraft.trim() || nameDraft.trim() === current.display_name || busy === "rename"}
                onClick={() => run("rename", async () => {
                  await updateTenant(current.tenant_id, { display_name: nameDraft.trim() });
                  await loadTenants();
                }, t("Đã đổi tên tổ chức"))}
                className={`px-3 py-1.5 rounded-md text-sm font-medium border ${toneClasses("success", "solid")} ${FOCUS_RING} disabled:opacity-40`}
              >
                {t("Lưu")}
              </button>
            </div>
            <p className="text-xs text-slate-400 mt-2">
              {t("Mã tổ chức")} <code className="font-mono">{current.tenant_id}</code> {t("là khoá trong mọi bảng dữ liệu và không đổi được — chỉ tên hiển thị đổi được ở đây.")}
            </p>
          </section>

            <p className="text-sm text-slate-600">
              {t("Việc dưới đây hiếm khi cần và khó hoàn tác — tách khỏi cài đặt thường ngày ở trên.")}
            </p>
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

            {detail.errors.preview ? (
              <BlockError text={detail.errors.preview} />
            ) : !preview ? (
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
          </>)}
              </div>
            </Tabs>
          </div>
        </fieldset>
      )}
    </div>
  );
}
