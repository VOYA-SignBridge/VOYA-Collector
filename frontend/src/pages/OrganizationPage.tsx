/**
 * Tổ chức của tôi — mặt tự phục vụ cho quản trị viên TENANT.
 *
 * Vì sao trang này tồn tại
 * -------------------------
 * `routers/tenants.py` có 19 endpoint và đã chạy từ đợt v4. Mặt giao diện duy
 * nhất đứng trên chúng là `/admin/tenants`, và trang đó gác sau `requireAdmin`
 * — tức quản trị viên **nền tảng**. Chủ một tổ chức không có màn hình nào: mời
 * thành viên, đổi vai, xem ai đang ở trong tổ chức mình, mang dữ liệu đi — tất
 * cả chỉ làm được bằng curl.
 *
 * Đây cũng chính là ví dụ sống cho một khái niệm bị gộp: **admin hệ thống ≠
 * admin tổ chức**. Hai vòng quyền đã tách rành mạch ở backend
 * (`require_admin` vs `require_tenant_admin`); trang này là mặt còn lại của
 * vòng thứ hai.
 *
 * Ba luật trang này giữ
 * ----------------------
 * 1. **Không đoán tenant.** Tenant lấy từ `user.tenant_id` của phiên đăng nhập,
 *    đúng cách middleware phía sau phân giải. Không ô nhập, không tham số URL —
 *    để người dùng chọn tenant là biến ranh giới cô lập thành một trường của
 *    request.
 * 2. **Không tự suy ra quyền.** Backend mới là nơi cưỡng chế. Trang chỉ ẩn nút
 *    mà người dùng chắc chắn không bấm được, và khi máy chủ trả 403 thì nói
 *    thẳng lý do thay vì hiện một trang vỡ.
 * 3. **Không hứa quá.** Lời mời gửi thư hỏng vẫn là lời mời hợp lệ — giao diện
 *    phải nói ra khác biệt đó và đưa liên kết để gửi tay.
 *
 * @i18n-key-table — `EXPORT_STATUS_LABEL` và `BILLING_LABEL` là bảng KHOÁ, dịch
 * tại chỗ đọc.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import PageHeader from "../components/ui/PageHeader";
import RequestOrganizationCard from "../components/organization/RequestOrganizationCard";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Modal from "../components/ui/Modal";
import {
  AlertTriangleIcon,
  BuildingIcon,
  CopyIcon,
  DownloadIcon,
  MailIcon,
  UsersIcon,
} from "../components/ui/Icons";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../hooks/useToast";
import { friendlyError } from "../lib/errors";
import { Trans, useI18n } from "../i18n";
import {
  NO_ROLE_OPTION,
  ROLES,
  parseRole,
  roleLabel,
  createInvitation,
  exportDownloadUrl,
  fetchExports,
  fetchInvitations,
  fetchMembers,
  fetchSubscription,
  fetchTenant,
  removeMember,
  requestExport,
  revokeInvitation,
  setAutoRenew,
  updateMemberRole,
  type InvitationCreated,
  type MemberRoleOrNone,
  type SubscriptionInfo,
  type Tenant,
  type TenantExport,
  type TenantInvitation,
  type TenantMember,
} from "../api/tenants";

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString("vi-VN");
}

function fmtBytes(n: number | null): string {
  if (n === null || n === undefined) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1048576) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1048576).toFixed(1)} MB`;
}

/** Trạng thái bản xuất → sắc thái. `ready` là thứ duy nhất tải được. */
function exportTone(status: string): "success" | "warning" | "danger" | "neutral" {
  if (status === "ready") return "success";
  if (status === "failed") return "danger";
  if (status === "pending" || status === "running") return "warning";
  return "neutral";
}

const EXPORT_STATUS_LABEL: Record<string, string> = {
  pending: "Đang chờ",
  running: "Đang chạy",
  ready: "Sẵn sàng",
  failed: "Thất bại",
};

export default function OrganizationPage() {
  const { t } = useI18n();
  const { user, loading: authLoading } = useAuth();
  const tenantId = user?.tenant_id ?? "";
  const { toast } = useToast();

  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [members, setMembers] = useState<TenantMember[]>([]);
  const [invitations, setInvitations] = useState<TenantInvitation[]>([]);
  const [exports, setExports] = useState<TenantExport[]>([]);
  const [subscription, setSubscription] = useState<SubscriptionInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [denied, setDenied] = useState(false);
  const [error, setError] = useState("");

  // Bộ đếm lượt tải: một lượt nạp chậm không được ghi đè kết quả mới hơn.
  const run = useRef(0);

  const load = useCallback(async () => {
    if (!tenantId) return;
    const mine = ++run.current;
    setLoading(true);
    try {
      // `fetchTenant` là lời gọi gác cổng: nó đòi `require_tenant_admin`, nên
      // một thành viên thường dừng ngay ở đây với 403 — và đó là câu trả lời
      // đúng, không phải lỗi cần giấu.
      const t = await fetchTenant(tenantId);
      if (mine !== run.current) return;
      setTenant(t);
      setDenied(false);
      setError("");

      const [m, inv, ex, sub] = await Promise.all([
        fetchMembers(tenantId),
        fetchInvitations(tenantId),
        fetchExports(tenantId).catch(() => [] as TenantExport[]),
        // Đăng ký nạp riêng và nuốt lỗi: một bản triển khai chưa dùng tới khái
        // niệm kỳ hạn vẫn phải xem được thành viên. Mất một khối không được
        // kéo theo cả trang.
        fetchSubscription(tenantId).catch(() => null),
      ]);
      if (mine !== run.current) return;
      setMembers(m);
      setInvitations(inv);
      setExports(ex);
      setSubscription(sub);
    } catch (err) {
      if (mine !== run.current) return;
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 403) {
        setDenied(true);
      } else {
        setError(friendlyError(err, t("Không đọc được thông tin tổ chức của bạn.")));
      }
    } finally {
      if (mine === run.current) setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    void load();
  }, [load]);

  const pendingInvitations = useMemo(
    () => invitations.filter((i) => !i.accepted_at && !i.revoked_at),
    [invitations],
  );

  if (authLoading) return <p className="text-slate-500">{t("Đang tải…")}</p>;

  if (!tenantId) {
    return (
      <>
        <PageHeader title={t("Tổ chức của tôi")} />
        <div className="space-y-4">
          <NoticeCard
            title={t("Tài khoản của bạn chưa thuộc tổ chức nào")}
            body={t("Bạn vẫn đóng góp dữ liệu bình thường. Tổ chức là thứ cần khi bạn muốn quản lý một nhóm người thu, hạn mức riêng và bản xuất riêng.")}
          />
          {/* Bản trước dừng ở câu "hãy liên hệ quản trị viên hệ thống" — một
              ngõ cụt có thiện chí: nói ra việc cần làm mà không đưa cách làm. */}
          <RequestOrganizationCard />
        </div>
      </>
    );
  }

  if (denied) {
    return (
      <>
        <PageHeader title={t("Tổ chức của tôi")} />
        <NoticeCard
          title={t("Bạn không phải quản trị viên của tổ chức này")}
          body={t("Trang này dành cho người quản trị tổ chức. Bạn vẫn dùng được mọi tính năng đóng góp dữ liệu như bình thường — chỉ phần quản lý thành viên là do quản trị viên tổ chức phụ trách.")}
        />
      </>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title={t("Tổ chức của tôi")}
        subtitle={t("Thành viên, lời mời, và mang dữ liệu của tổ chức đi.")}
        breadcrumb={[{ label: t("Trang chủ"), href: "/" }, { label: t("Tổ chức") }]}
      />

      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      {loading && !tenant && <p className="text-slate-500">{t("Đang tải…")}</p>}

      {tenant && (
        <>
          <IdentityCard tenant={tenant} memberCount={members.length} />
          <SubscriptionSection
            tenantId={tenantId}
            info={subscription}
            onChanged={load}
            toast={toast}
          />
          <MembersSection
            tenantId={tenantId}
            members={members}
            meId={user?.id ?? ""}
            onChanged={load}
            toast={toast}
          />
          <InvitationsSection
            tenantId={tenantId}
            invitations={pendingInvitations}
            onChanged={load}
            toast={toast}
          />
          <ExportsSection
            tenantId={tenantId}
            exports={exports}
            onChanged={load}
            toast={toast}
          />
        </>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ dùng chung

type Toast = ReturnType<typeof useToast>["toast"];

function NoticeCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      <p className="mt-2 max-w-2xl text-sm text-slate-600">{body}</p>
    </div>
  );
}

function Section({
  title,
  description,
  action,
  children,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
          {description && <p className="mt-1 text-sm text-slate-600">{description}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

// ------------------------------------------------------------------ danh tính

function IdentityCard({ tenant, memberCount }: { tenant: Tenant; memberCount: number }) {
  const { t } = useI18n();
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="flex flex-wrap items-start gap-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-ctu-navy to-ctu-blue text-white">
          <BuildingIcon className="h-6 w-6" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-xl font-semibold text-slate-900">{tenant.display_name}</h2>
            <Badge variant={tenant.is_active ? "success" : "warning"} size="sm">
              {tenant.is_active ? t("Đang hoạt động") : t("Đã tạm dừng")}
            </Badge>
          </div>
          <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-slate-500">{t("Mã tổ chức")}</dt>
              <dd className="font-mono text-xs text-slate-800">{tenant.tenant_id}</dd>
            </div>
            <div>
              <dt className="text-slate-500">{t("Thành viên")}</dt>
              <dd className="font-medium text-slate-900">{memberCount}</dd>
            </div>
            <div>
              <dt className="text-slate-500">{t("Lập ngày")}</dt>
              <dd className="font-medium text-slate-900">{fmtDate(tenant.created_at)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">{t("Định danh rút gọn")}</dt>
              <dd className="font-mono text-xs text-slate-800">{tenant.slug || "—"}</dd>
            </div>
          </dl>
        </div>
      </div>
    </section>
  );
}

// -------------------------------------------------------------------- đăng ký

const BILLING_LABEL: Record<string, string> = {
  trialing: "Đang dùng thử",
  active: "Đang hoạt động",
  past_due: "Quá hạn — đang trong thời gian ân hạn",
  suspended: "Chỉ đọc",
  cancelled: "Đã huỷ",
};

function SubscriptionSection({
  tenantId,
  info,
  onChanged,
  toast,
}: {
  tenantId: string;
  info: SubscriptionInfo | null;
  onChanged: () => Promise<void>;
  toast: Toast;
}) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const toggle = useCallback(
    async (enabled: boolean) => {
      setBusy(true);
      try {
        await setAutoRenew(tenantId, enabled);
        toast.success(
          enabled
            ? t("Đã bật tự động gia hạn.")
            : t("Đã tắt tự động gia hạn. Kỳ hiện tại vẫn chạy hết."),
        );
        setConfirming(false);
        await onChanged();
      } catch (err) {
        toast.error(friendlyError(err, t("Không đổi được thiết lập gia hạn.")));
      } finally {
        setBusy(false);
      }
    },
    [tenantId, onChanged, toast],
  );

  if (!info || !info.has_subscription) {
    return (
      <Section title={t("Gói dịch vụ")}>
        <p className="text-sm text-slate-500">
          {t("Tổ chức này chưa có đăng ký nào. Hãy liên hệ quản trị viên nền tảng.")}
        </p>
      </Section>
    );
  }

  const tone = info.read_only
    ? "danger"
    : info.billing_status === "past_due"
      ? "warning"
      : "success";

  return (
    <Section
      title={t("Gói dịch vụ")}
      description={t("Kỳ hạn hiện tại và thiết lập gia hạn của tổ chức.")}
    >
      <div className="flex flex-wrap items-center gap-3">
        <Badge variant={tone} size="md">
          {t(BILLING_LABEL[info.billing_status]) ?? info.billing_status}
        </Badge>
        {/* `days_left === null` nghĩa là gói KHÔNG có kỳ hạn. Vẽ "còn 0 ngày"
            ở đây là một câu sai — xem chú thích ở `api/tenants.ts`. */}
        {info.days_left !== null && (
          <span className="text-sm text-slate-600">
            {t("Còn")} <b>{info.days_left}</b> ngày
            {info.current_period_end && t(" · hết hạn {p1}", { p1: fmtDate(info.current_period_end) })}
          </span>
        )}
        {info.days_left === null && (
          <span className="text-sm text-slate-500">{t("Gói không có kỳ hạn")}</span>
        )}
      </div>

      {/* Chỉ-đọc phải nói rõ hai điều: cái gì KHÔNG làm được, và — quan trọng
          hơn — cái gì VẪN còn. Người đọc một cảnh báo đỏ mà không thấy câu thứ
          hai sẽ tưởng dữ liệu của mình đã mất. */}
      {info.read_only && (
        <div className="mt-3 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>
            <Trans
              k="Tổ chức đang ở chế độ {chedo}: không thêm được dữ liệu mới. Toàn bộ dữ liệu đã có {trangthai} và bạn vẫn tải về được ở mục “Mang dữ liệu đi” bên dưới. Liên hệ quản trị viên nền tảng để mở lại."
              vars={{
                chedo: <b>{t("chỉ đọc")}</b>,
                trangthai: <b>{t("vẫn còn nguyên")}</b>,
              }}
            />
          </span>
        </div>
      )}

      {info.billing_status === "past_due" && !info.read_only && (
        <div className="mt-3 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>
            <Trans
              k="Kỳ hạn đã kết thúc. Bạn {quyen} tới {moc}; sau mốc đó tổ chức chuyển sang chỉ đọc."
              vars={{
                quyen: <b>{t("vẫn ghi được")}</b>,
                moc: info.grace_until
                  ? fmtDate(info.grace_until)
                  : t("hết thời gian ân hạn"),
              }}
            />
          </span>
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-slate-50/60 p-4">
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-slate-900">{t("Tự động gia hạn")}</div>
          <p className="mt-0.5 text-xs text-slate-500">
            {info.auto_renew
              ? t("Kỳ mới sẽ mở ngay khi kỳ này kết thúc.")
              : t("Kỳ này kết thúc là dừng — dữ liệu vẫn giữ, tổ chức chuyển sang chỉ đọc.")}
          </p>
        </div>
        {info.auto_renew ? (
          <Button size="sm" variant="secondary" disabled={busy}
                  onClick={() => setConfirming(true)}>
            {t("Tắt tự gia hạn")}
          </Button>
        ) : (
          <Button size="sm" loading={busy} onClick={() => void toggle(true)}>
            {t("Bật tự gia hạn")}
          </Button>
        )}
      </div>

      <Modal
        isOpen={confirming}
        onClose={() => setConfirming(false)}
        title={t("Tắt tự động gia hạn?")}
        size="sm"
      >
        {/* Câu quan trọng nhất trong cả trang: tắt gia hạn KHÔNG cắt dịch vụ
            ngay. Thiếu nó, người dùng tưởng mình vừa tự khoá tổ chức của mình
            và sẽ bật lại ngay — hoặc tệ hơn, không dám bấm gì cả. */}
        <p className="text-sm text-slate-700">
          {t("Kỳ hiện tại")} <b>{t("vẫn chạy hết")}</b>
          {info.current_period_end && t(" (tới {p1})", { p1: fmtDate(info.current_period_end) })}. Bạn
          không mất gì ngay bây giờ.
        </p>
        <p className="mt-2 text-sm text-slate-600">
          <Trans
            k="Sau đó tổ chức chuyển sang {chedo}: dữ liệu còn nguyên, tải về được, nhưng không thêm mới. Bật lại bất cứ lúc nào ở chính chỗ này."
            vars={{ chedo: <b>{t("chỉ đọc")}</b> }}
          />
        </p>
        <div className="mt-5 flex flex-wrap gap-2">
          {/* "Xác nhận tắt", không lặp lại "Tắt tự gia hạn" của nút mở hộp
              thoại — cùng lý do như nút rút đồng thuận ở AccountPage: hai nút
              cùng chữ ở hai bước khác nhau làm người dùng không chắc mình đang
              ở bước nào. */}
          <Button variant="danger" loading={busy} onClick={() => void toggle(false)}>
            {t("Xác nhận tắt")}
          </Button>
          <Button variant="ghost" onClick={() => setConfirming(false)}>
            {t("Giữ nguyên")}
          </Button>
        </div>
      </Modal>
    </Section>
  );
}

// ------------------------------------------------------------------ thành viên

function MembersSection({
  tenantId,
  members,
  meId,
  onChanged,
  toast,
}: {
  tenantId: string;
  members: TenantMember[];
  meId: string;
  onChanged: () => Promise<void>;
  toast: Toast;
}) {
  const { t } = useI18n();
  const [busy, setBusy] = useState<string | null>(null);
  const [removing, setRemoving] = useState<TenantMember | null>(null);

  const changeRole = useCallback(
    async (m: TenantMember, role: MemberRoleOrNone) => {
      if (role === m.role) return;
      setBusy(m.user_id);
      try {
        await updateMemberRole(tenantId, m.user_id, role);
        // `roleLabel` chứ không `ROLE_LABEL[role]`: gỡ vai là một lựa chọn
        // thật ở ô này, và `null` tra bảng trực tiếp sẽ cho ra một câu
        // "Đã đổi vai của X thành ." mà người đọc tưởng là lỗi.
        toast.success(t("Đã đổi vai của {ai} thành {vai}.", {
          ai: m.username ?? t("thành viên"),
          vai: t(roleLabel(role)),
        }));
        await onChanged();
      } catch (err) {
        toast.error(friendlyError(err, t("Không đổi được vai của thành viên này.")));
      } finally {
        setBusy(null);
      }
    },
    [tenantId, onChanged, toast],
  );

  const confirmRemove = useCallback(async () => {
    if (!removing) return;
    setBusy(removing.user_id);
    try {
      await removeMember(tenantId, removing.user_id);
      toast.success(t("Đã gỡ {ai} khỏi tổ chức.", { ai: removing.username ?? t("thành viên") }));
      setRemoving(null);
      await onChanged();
    } catch (err) {
      toast.error(friendlyError(err, t("Không gỡ được thành viên này.")));
    } finally {
      setBusy(null);
    }
  }, [removing, tenantId, onChanged, toast]);

  return (
    <Section
      title={t("Thành viên")}
      description={t("Vai quyết định người đó làm được gì với dữ liệu của tổ chức.")}
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="pb-2 pr-4 font-medium">{t("Người dùng")}</th>
              <th className="pb-2 pr-4 font-medium">Vai</th>
              <th className="pb-2 pr-4 font-medium">Tham gia</th>
              <th className="pb-2 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {members.map((m) => {
              const isMe = m.user_id === meId;
              return (
                <tr key={m.user_id} className="border-b border-slate-100 last:border-0">
                  <td className="py-3 pr-4">
                    <div className="font-medium text-slate-900">
                      {m.username ?? t("(không tên)")}
                      {isMe && <span className="ml-2 text-xs text-slate-400">{t("— bạn")}</span>}
                    </div>
                    <div className="text-xs text-slate-500">{m.email ?? "—"}</div>
                  </td>
                  <td className="py-3 pr-4">
                    {/* Không cho tự hạ vai của CHÍNH MÌNH: một tổ chức không còn
                        quản trị viên nào là trạng thái không ai gỡ ra được từ
                        trong giao diện. Backend vẫn là nơi cưỡng chế thật. */}
                    {isMe ? (
                      <Badge variant="neutral" size="sm">{t(roleLabel(m.role))}</Badge>
                    ) : (
                      <select
                        value={m.role ?? NO_ROLE_OPTION}
                        disabled={busy === m.user_id}
                        onChange={(e) => void changeRole(m, parseRole(e.target.value))}
                        className="rounded-lg border border-slate-300 px-2 py-1 text-sm focus:border-ctu-blue focus:outline-none focus:ring-1 focus:ring-ctu-blue"
                        aria-label={t("Vai của {ai}", { ai: m.username ?? t("thành viên") })}
                      >
                        <option value={NO_ROLE_OPTION}>{t(roleLabel(null))}</option>
                        {ROLES.map((r) => (
                          <option key={r} value={r}>{t(roleLabel(r))}</option>
                        ))}
                      </select>
                    )}
                  </td>
                  <td className="py-3 pr-4 text-slate-600">{fmtDate(m.created_at)}</td>
                  <td className="py-3 text-right">
                    {!isMe && (
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={busy === m.user_id}
                        onClick={() => setRemoving(m)}
                      >
                        {t("Gỡ")}
                      </Button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <Modal
        isOpen={!!removing}
        onClose={() => setRemoving(null)}
        title={t("Gỡ thành viên khỏi tổ chức?")}
        size="sm"
      >
        <p className="text-sm text-slate-700">
          <b>{removing?.username ?? t("Thành viên này")}</b> {t("sẽ mất quyền truy cập dữ liệu của tổ chức.")}
        </p>
        {/* Nói đúng những gì xảy ra. Gỡ thành viên KHÔNG xoá dữ liệu họ đã đóng
            góp — dữ liệu thuộc về tổ chức, và hứa ngược lại là hứa một việc hệ
            thống không làm. */}
        <p className="mt-2 text-sm text-slate-600">
          {t("Những mẫu họ đã đóng góp")} <b>{t("vẫn ở lại")}</b> {t("với tổ chức. Tài khoản của họ không bị xoá, và bạn có thể mời lại bất cứ lúc nào.")}
        </p>
        <div className="mt-5 flex flex-wrap gap-2">
          <Button variant="danger" onClick={() => void confirmRemove()} loading={!!busy}>
            {t("Gỡ khỏi tổ chức")}
          </Button>
          <Button variant="ghost" onClick={() => setRemoving(null)}>
            {t("Giữ nguyên")}
          </Button>
        </div>
      </Modal>
    </Section>
  );
}

// ------------------------------------------------------------------- lời mời

function InvitationsSection({
  tenantId,
  invitations,
  onChanged,
  toast,
}: {
  tenantId: string;
  invitations: TenantInvitation[];
  onChanged: () => Promise<void>;
  toast: Toast;
}) {
  const { t } = useI18n();
  const [email, setEmail] = useState("");
  // Mời vào tổ chức KHÔNG kèm vai, mặc định. Xem `tenant_admin.NO_ROLE`.
  const [role, setRole] = useState<MemberRoleOrNone>(null);
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<InvitationCreated | null>(null);

  const canInvite = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()) && !busy;

  const invite = useCallback(async () => {
    if (!canInvite) return;
    setBusy(true);
    try {
      const res = await createInvitation(tenantId, email.trim(), role);
      setCreated(res);
      setEmail("");
      await onChanged();
    } catch (err) {
      toast.error(friendlyError(err, t("Không tạo được lời mời.")));
    } finally {
      setBusy(false);
    }
  }, [canInvite, tenantId, email, role, onChanged, toast]);

  const revoke = useCallback(
    async (inv: TenantInvitation) => {
      try {
        await revokeInvitation(tenantId, inv.invitation_id);
        toast.success(t("Đã thu hồi lời mời gửi tới {email}.", { email: inv.email }));
        await onChanged();
      } catch (err) {
        toast.error(friendlyError(err, t("Không thu hồi được lời mời.")));
      }
    },
    [tenantId, onChanged, toast],
  );

  const copyLink = useCallback(() => {
    if (!created?.accept_url) return;
    void navigator.clipboard.writeText(created.accept_url).then(
      () => toast.success(t("Đã chép liên kết mời.")),
      () => toast.error(t("Trình duyệt không cho chép. Hãy bôi đen rồi chép tay.")),
    );
  }, [created, toast]);

  return (
    <Section
      title={t("Lời mời")}
      description={t("Người được mời tự tạo tài khoản bằng liên kết. Bạn không cần biết mật khẩu của họ.")}
    >
      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-slate-50/60 p-4">
        <label className="min-w-[220px] flex-1">
          <span className="mb-1 block text-xs font-medium text-slate-500">{t("Email người được mời")}</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="vd: giangvien@ctu.edu.vn"
            className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-ctu-blue focus:outline-none focus:ring-1 focus:ring-ctu-blue"
          />
        </label>
        <label>
          <span className="mb-1 block text-xs font-medium text-slate-500">Vai</span>
          <select
            value={role ?? NO_ROLE_OPTION}
            onChange={(e) => setRole(parseRole(e.target.value))}
            className="rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-ctu-blue focus:outline-none focus:ring-1 focus:ring-ctu-blue"
          >
            <option value={NO_ROLE_OPTION}>{t(roleLabel(null))}</option>
            {ROLES.map((r) => (
              <option key={r} value={r}>{t(roleLabel(r))}</option>
            ))}
          </select>
        </label>
        <Button onClick={() => void invite()} disabled={!canInvite} loading={busy}>
          <MailIcon className="mr-1.5 h-4 w-4" aria-hidden="true" />
          {t("Gửi lời mời")}
        </Button>
      </div>

      {invitations.length === 0 ? (
        <p className="mt-4 text-sm text-slate-500">{t("Chưa có lời mời nào đang chờ.")}</p>
      ) : (
        <ul className="mt-4 divide-y divide-slate-100">
          {invitations.map((inv) => (
            <li key={inv.invitation_id} className="flex flex-wrap items-center gap-3 py-3">
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium text-slate-900">{inv.email}</div>
                <div className="text-xs text-slate-500">
                  {t(roleLabel(inv.role))} · hết hạn {fmtDate(inv.expires_at)}
                </div>
              </div>
              <Button size="sm" variant="ghost" onClick={() => void revoke(inv)}>
                {t("Thu hồi")}
              </Button>
            </li>
          ))}
        </ul>
      )}

      <Modal
        isOpen={!!created}
        onClose={() => setCreated(null)}
        title={t("Đã tạo lời mời")}
        size="lg"
      >
        {created && (
          <>
            {/* `email_sent` nói thật. Thư hỏng KHÔNG huỷ lời mời — nó vẫn hợp lệ,
                chỉ là phải gửi liên kết bằng tay. Gộp hai trường hợp này lại là
                để người dùng ngồi chờ một lá thư không bao giờ tới. */}
            {created.email_sent ? (
              <p className="text-sm text-slate-700">
                <Trans
                  k="Đã gửi thư tới {email}. Bạn có thể chép thêm liên kết bên dưới để gửi qua kênh khác."
                  vars={{ email: <b>{created.email}</b> }}
                />
              </p>
            ) : (
              <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                <span>
                  <Trans
                    k="Hệ thống {trang_thai} tới {email}. Lời mời vẫn hợp lệ — hãy chép liên kết bên dưới và gửi cho họ."
                    vars={{
                      trang_thai: <b>{t("chưa gửi được thư")}</b>,
                      email: created.email,
                    }}
                  />
                </span>
              </div>
            )}

            <div className="mt-4">
              <span className="mb-1 block text-xs font-medium text-slate-500">{t("Liên kết mời")}</span>
              <div className="flex flex-wrap items-center gap-2">
                <code className="min-w-0 flex-1 break-all rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
                  {created.accept_url}
                </code>
                <Button size="sm" variant="secondary" onClick={copyLink}>
                  <CopyIcon className="mr-1.5 h-4 w-4" aria-hidden="true" />
                  {t("Chép")}
                </Button>
              </div>
              <p className="mt-2 text-xs text-slate-500">
                {t("Liên kết chỉ hiện ra một lần này. Người nhận phải dùng đúng địa chỉ email đã được mời.")}
              </p>
            </div>

            <div className="mt-5">
              <Button onClick={() => setCreated(null)}>Xong</Button>
            </div>
          </>
        )}
      </Modal>
    </Section>
  );
}

// -------------------------------------------------------------- xuất dữ liệu

function ExportsSection({
  tenantId,
  exports,
  onChanged,
  toast,
}: {
  tenantId: string;
  exports: TenantExport[];
  onChanged: () => Promise<void>;
  toast: Toast;
}) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);

  const start = useCallback(
    async (scope: "metadata" | "full") => {
      setBusy(true);
      try {
        await requestExport(tenantId, scope);
        // Máy chủ trả 202: đã nhận việc, chưa có gì tải được. Nói đúng như vậy.
        toast.success(t("Đã nhận yêu cầu. Bản xuất sẽ hiện ở danh sách khi xong."));
        await onChanged();
      } catch (err) {
        toast.error(friendlyError(err, t("Không tạo được bản xuất.")));
      } finally {
        setBusy(false);
      }
    },
    [tenantId, onChanged, toast],
  );

  return (
    <Section
      title={t("Mang dữ liệu đi")}
      description={t("Toàn bộ dữ liệu của tổ chức, đóng thành một gói tải về được. Đây là quyền của bạn, không phải một ưu đãi.")}
      action={
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" loading={busy} onClick={() => void start("metadata")}>
            {t("Xuất siêu dữ liệu")}
          </Button>
          <Button size="sm" loading={busy} onClick={() => void start("full")}>
            <UsersIcon className="mr-1.5 h-4 w-4" aria-hidden="true" />
            {t("Xuất toàn bộ")}
          </Button>
        </div>
      }
    >
      {exports.length === 0 ? (
        <p className="text-sm text-slate-500">{t("Chưa có bản xuất nào.")}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="pb-2 pr-4 font-medium">{t("Tạo lúc")}</th>
                <th className="pb-2 pr-4 font-medium">{t("Phạm vi")}</th>
                <th className="pb-2 pr-4 font-medium">{t("Trạng thái")}</th>
                <th className="pb-2 pr-4 font-medium">{t("Dung lượng")}</th>
                <th className="pb-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {exports.map((ex) => (
                <tr key={ex.export_id} className="border-b border-slate-100 last:border-0">
                  <td className="py-3 pr-4 text-slate-600">{fmtDate(ex.created_at)}</td>
                  <td className="py-3 pr-4 text-slate-600">
                    {ex.scope === "full" ? t("Toàn bộ") : t("Siêu dữ liệu")}
                  </td>
                  <td className="py-3 pr-4">
                    <Badge variant={exportTone(ex.status)} size="sm">
                      {t(EXPORT_STATUS_LABEL[ex.status]) ?? ex.status}
                    </Badge>
                  </td>
                  <td className="py-3 pr-4 text-slate-600">{fmtBytes(ex.size_bytes)}</td>
                  <td className="py-3 text-right">
                    {/* Chỉ `ready` mới tải được — máy chủ trả 202 lúc nhận việc,
                        nên một nút Tải về hiện sớm là một nút chắc chắn hỏng. */}
                    {ex.status === "ready" ? (
                      <a
                        href={exportDownloadUrl(tenantId, ex.export_id)}
                        className="inline-flex items-center gap-1.5 text-sm font-medium text-ctu-blue hover:underline"
                      >
                        <DownloadIcon className="h-4 w-4" aria-hidden="true" />
                        {t("Tải về")}
                      </a>
                    ) : ex.status === "failed" ? (
                      <span className="text-xs text-red-600">{ex.error || t("Thất bại")}</span>
                    ) : (
                      <span className="text-xs text-slate-400">{t("Đang xử lý…")}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}
