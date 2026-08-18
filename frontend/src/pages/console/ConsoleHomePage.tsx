/**
 * Tổng quan console tổ chức — `/console`.
 *
 * Trang này trả lời đúng bốn câu mà người điều hành một tổ chức hỏi mỗi khi mở
 * hệ thống: *tổ chức đang ở gói nào và còn bao nhiêu hạn mức · có bao nhiêu
 * phạm vi làm việc · cơ chế phân quyền đang ở chế độ nào · còn việc gì phải làm*.
 *
 * Nó cố ý KHÔNG là một bảng điều khiển đầy biểu đồ. Bốn thẻ và một danh sách
 * việc còn nợ đọc được trong một cái liếc; thêm biểu đồ vào đây là đẩy bốn câu
 * trên xuống dưới màn hình đầu.
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Badge from "../../components/ui/Badge";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import ErrorBanner from "../../components/ErrorBanner";
import { useI18n } from "../../i18n";
import { friendlyError } from "../../lib/errors";
import { fetchBillingSummary, quotaLines, type BillingSummary } from "../../api/billing";
import { getScopeSummary, type ScopeSummary } from "../../api/workspaces";

export default function ConsoleHomePage() {
  const { t } = useI18n();
  const [billing, setBilling] = useState<BillingSummary | null>(null);
  const [scope, setScope] = useState<ScopeSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        /* `allSettled` chứ không phải `all`: gói cước và cây phạm vi là hai
           nguồn độc lập, và một nguồn hỏng không nên làm trắng cả trang. */
        const [b, s] = await Promise.allSettled([fetchBillingSummary(), getScopeSummary()]);
        if (b.status === "fulfilled") setBilling(b.value);
        if (s.status === "fulfilled") setScope(s.value);
        if (b.status === "rejected" && s.status === "rejected") {
          setError(friendlyError(b.reason, t("Không đọc được thông tin tổ chức.")));
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [t]);

  if (loading) return <LoadingSpinner size="lg" label={t("Đang tải tổng quan…")} />;

  const lines = billing ? quotaLines(billing) : [];

  return (
    <div className="space-y-6">
      {error && <ErrorBanner message={error} />}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Card label={t("Gói dịch vụ")} value={billing?.plan?.display_name ?? "—"} />
        <Card label={t("Workspace")} value={String(scope?.workspaces ?? "—")} />
        <Card label={t("Project")} value={String(scope?.projects ?? "—")} />
        <Card
          label={t("Vai theo phạm vi")}
          value={String((scope?.workspace_members ?? 0) + (scope?.project_members ?? 0))}
        />
      </div>

      {lines.length > 0 && (
        <section className="rounded-xl border border-slate-200 p-4">
          <h2 className="mb-3 text-lg font-semibold text-slate-900">{t("Hạn mức đang dùng")}</h2>
          <div className="space-y-3">
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
                    style={{
                      width: l.limit ? `${Math.min(100, (l.used / l.limit) * 100)}%` : "8%",
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
          <Link
            to="/console/allocations"
            className="mt-4 inline-block text-sm font-medium text-ctu-blue hover:underline"
          >
            {t("Chia hạn mức xuống từng project →")}
          </Link>
        </section>
      )}

      {/* Danh sách này là phần TRUNG THỰC của trang. Nó nêu đúng những gì chưa
          có hiệu lực, thay vì để bốn thẻ số ở trên được đọc thành "mọi thứ đã
          chạy". Gỡ nó đi chỉ hợp lệ khi hai dòng dưới đã đóng thật. */}
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <h2 className="mb-2 font-semibold">{t("Trạng thái thật của cơ chế phạm vi")}</h2>
        <ul className="ml-5 list-disc space-y-1">
          <li>
            {t("Chế độ phân quyền:")}{" "}
            <Badge variant={scope?.authz_mode === "casbin" ? "success" : "default"} size="sm">
              {scope?.authz_mode ?? "—"}
            </Badge>{" "}
            {scope?.authz_mode === "shadow" &&
              t("— Casbin đang quan sát, hệ cũ hai phạm vi là bên quyết định.")}
          </li>
          <li>
            {scope?.data_carries_project_id
              ? t("Dữ liệu đã mang project_id.")
              : t("Dữ liệu chưa mang project_id — cấp phát ở cấp project là hạn mức dự kiến, chưa tự chặn đường ghi.")}
          </li>
        </ul>
      </section>
    </div>
  );
}

function Card({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <div className="text-xs font-medium text-slate-500">{label}</div>
      <div className="mt-1 truncate text-xl font-semibold text-slate-900">{value}</div>
    </div>
  );
}
