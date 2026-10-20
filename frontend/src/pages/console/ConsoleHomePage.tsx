/**
 * Tổng quan một tổ chức — trang index của `/org/:tenantId`.
 *
 * Người mở trang này thường KHÔNG phải quản trị viên: giáo viên vào để tổ
 * chức một buổi, học sinh vào để thực hành, người đóng góp vào để ghi hình.
 * Bản trước trả lời bốn câu của người điều hành ("gói nào, bao nhiêu
 * workspace, bao nhiêu project, phân quyền chế độ nào") — đúng cho họ, vô
 * nghĩa với mọi người khác. Bố cục Đợt 2 (kế hoạch UX 13/09/2026, wireframe
 * "TỔ CHỨC: TRƯỜNG A") đảo thứ tự:
 *
 *   1. BA VIỆC CHÍNH — đóng góp dữ liệu, nhận dạng, thư viện nhãn. Nút to,
 *      một câu giải thích, không thuật ngữ.
 *   2. HƯỚNG DẪN BẮT ĐẦU — ba bước, mỗi bước trả lời một câu: đúng tổ chức
 *      chưa? vai của bạn cho phép gì? mở việc nào?
 *   3. GÓI & HẠN MỨC — cho người điều hành, nói bằng chữ thường ("Nhóm & lớp"
 *      thay cho "Workspace / Project"), và chỉ khi có số để nói.
 *
 * Số liệu vẫn lấy từ hai nguồn độc lập (`allSettled`): nguồn nào hỏng thì
 * phần đó vắng, phần còn lại vẫn dùng được — ba việc chính không phụ thuộc
 * vào gói cước.
 */

import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import ErrorBanner from "../../components/ErrorBanner";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import { HandIcon, TagIcon, UploadIcon } from "../../components/ui/Icons";
import { useI18n } from "../../i18n";
import { friendlyError } from "../../lib/errors";
import { fetchBillingSummary, quotaLines, type BillingSummary } from "../../api/billing";
import { fetchMyTenant, roleDescription, roleLabel, type MemberRoleOrNone, type MyTenant } from "../../api/tenants";
import { getScopeSummary, type ScopeSummary } from "../../api/workspaces";

export default function ConsoleHomePage() {
  const { t } = useI18n();
  const [billing, setBilling] = useState<BillingSummary | null>(null);
  const [scope, setScope] = useState<ScopeSummary | null>(null);
  const [me, setMe] = useState<MyTenant | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [b, s, m] = await Promise.allSettled([fetchBillingSummary(), getScopeSummary(), fetchMyTenant()]);
        if (b.status === "fulfilled") setBilling(b.value);
        if (s.status === "fulfilled") setScope(s.value);
        if (m.status === "fulfilled") setMe(m.value);
        if (b.status === "rejected" && s.status === "rejected" && m.status === "rejected") {
          setError(friendlyError(b.reason, t("Không đọc được thông tin tổ chức.")));
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [t]);

  if (loading) return <LoadingSpinner size="lg" label={t("Đang tải tổng quan…")} />;

  const lines = billing ? quotaLines(billing) : [];
  const role = (me?.my_role ?? null) as MemberRoleOrNone;
  const groups = (scope?.workspaces ?? 0) + (scope?.projects ?? 0);

  return (
    <div className="space-y-8">
      {error && <ErrorBanner message={error} />}

      {/* ---------------- 1. Ba việc chính ---------------- */}
      <section aria-labelledby="org-actions">
        <h2 id="org-actions" className="sr-only">{t("Việc chính")}</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <ActionCard
            to="upload"
            icon={<UploadIcon className="h-6 w-6" aria-hidden="true" />}
            title={t("Đóng góp dữ liệu")}
            hint={t("Ghi hình hoặc tải video ký hiệu vào tổ chức này.")}
            primary
          />
          <ActionCard
            to="realtime"
            icon={<HandIcon className="h-6 w-6" aria-hidden="true" />}
            title={t("Nhận dạng thử")}
            hint={t("Bật camera, làm một ký hiệu, xem hệ thống nhận ra gì.")}
          />
          <ActionCard
            to="labels"
            icon={<TagIcon className="h-6 w-6" aria-hidden="true" />}
            title={t("Thư viện nhãn")}
            hint={t("Danh sách ký hiệu đã có và số mẫu của từng ký hiệu.")}
          />
        </div>
      </section>

      {/* ---------------- 2. Hướng dẫn bắt đầu ---------------- */}
      <section className="rounded-xl border border-slate-200 bg-slate-50 p-5" data-testid="getting-started">
        <h2 className="text-base font-semibold text-slate-900">{t("Hướng dẫn bắt đầu")}</h2>
        <ol className="mt-3 space-y-3 text-sm text-slate-700">
          <Step n={1} title={t("Bạn đang ở đúng tổ chức chưa?")}>
            {me ? (
              <>
                {t("Đang làm việc tại {ten}.", { ten: me.display_name || me.tenant_id })}{" "}
                <Link to="/org" className="font-medium text-ctu-blue hover:underline">{t("Đổi tổ chức")}</Link>
              </>
            ) : (
              <Link to="/org" className="font-medium text-ctu-blue hover:underline">{t("Chọn tổ chức")}</Link>
            )}
          </Step>
          <Step n={2} title={t("Bạn được làm gì ở đây?")}>
            <span className="font-medium text-slate-900">{t(roleLabel(role))}</span>
            {" — "}
            {roleDescription(role)}
          </Step>
          <Step n={3} title={t("Mở công việc")}>
            {t("Chọn một trong ba việc ở trên, hoặc dùng thanh bên trái. Mọi thứ bạn ghi sẽ thuộc về tổ chức này.")}
          </Step>
        </ol>
      </section>

      {/* ---------------- 3. Gói & hạn mức (người điều hành) ---------------- */}
      {(billing || scope) && (
        <section className="rounded-xl border border-slate-200 p-5">
          <h2 className="text-base font-semibold text-slate-900">{t("Gói dịch vụ & hạn mức")}</h2>
          <dl className="mt-3 grid gap-3 sm:grid-cols-3">
            <Fact label={t("Gói dịch vụ")} value={billing?.plan?.display_name ?? "—"} />
            <Fact label={t("Nhóm & lớp")} value={scope ? String(groups) : "—"} />
            <Fact label={t("Thành viên có vai riêng trong nhóm/lớp")} value={scope ? String((scope.workspace_members ?? 0) + (scope.project_members ?? 0)) : "—"} />
          </dl>

          {lines.length > 0 && (
            <div className="mt-5 space-y-3">
              {lines.map((l) => (
                <div key={l.key}>
                  <div className="mb-1 flex justify-between text-sm">
                    <span className="text-slate-600">{t(l.label)}</span>
                    <span className="font-medium text-slate-900">
                      {l.limit === null || l.limit === undefined
                        ? t("{n} / không giới hạn", { n: l.used })
                        : `${l.used} / ${l.limit}`}
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-ctu-blue"
                      style={{ width: l.limit ? `${Math.min(100, (l.used / l.limit) * 100)}%` : "8%" }}
                    />
                  </div>
                </div>
              ))}
              <Link
                // Tương đối, không tuyệt đối: trang này được vẽ ở `/org/<id>`.
                to="settings/allocations"
                className="inline-block text-sm font-medium text-ctu-blue hover:underline"
              >
                {t("Chia hạn mức xuống từng nhóm/lớp →")}
              </Link>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function ActionCard({ to, icon, title, hint, primary = false }: {
  to: string;
  icon: ReactNode;
  title: string;
  hint: string;
  primary?: boolean;
}) {
  return (
    <Link
      to={to}
      className={`flex min-h-[7rem] flex-col gap-2 rounded-xl border p-4 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue ${
        primary
          ? "border-ctu-blue bg-ctu-blue text-white hover:bg-ctu-navy"
          : "border-slate-200 bg-white text-slate-900 hover:border-ctu-blue/50 hover:bg-ctu-blue/5"
      }`}
    >
      <span className={primary ? "text-white" : "text-ctu-blue"}>{icon}</span>
      <span className="text-base font-semibold">{title}</span>
      <span className={`text-sm ${primary ? "text-white/85" : "text-slate-600"}`}>{hint}</span>
    </Link>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <li className="flex gap-3">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ctu-blue text-xs font-semibold text-white">{n}</span>
      <div>
        <p className="font-medium text-slate-900">{title}</p>
        <p className="mt-0.5 leading-relaxed">{children}</p>
      </div>
    </li>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-4 py-3">
      <dt className="text-xs font-medium text-slate-500">{label}</dt>
      <dd className="mt-1 truncate text-lg font-semibold text-slate-900">{value}</dd>
    </div>
  );
}
