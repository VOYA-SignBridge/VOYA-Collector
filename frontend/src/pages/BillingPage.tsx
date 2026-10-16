/**
 * Gói dịch vụ và mức dùng của tổ chức.
 *
 * Mở cho MỌI thành viên, không chỉ quản trị viên. Người bị chặn vì hết hạn mức
 * là người đang thao tác, và nếu họ không xem được vì sao thì thông báo lỗi
 * "gói của bạn cho phép tối đa 500 mẫu" trở thành một điều bí ẩn — họ không
 * kiểm chứng được, không biết còn bao nhiêu, và sẽ hỏi người khác.
 *
 * Hai thứ cố ý KHÔNG có ở đây:
 *
 *  - Nút "nâng gói ngay". Chưa có cổng thanh toán; một nút dẫn tới trang trắng
 *    tệ hơn hẳn một dòng chữ nói rõ phải liên hệ ai.
 *  - Trần dạng "không giới hạn" vẽ thành thanh 0%. `limit === null` thì không
 *    vẽ thanh nào cả — một thanh rỗng gợi ý "sắp hết", đúng ngược nghĩa.
 *
 * @i18n-key-table — `STATUS_LABEL` là bảng KHOÁ, dịch tại chỗ đọc.
 */

import { useCallback, useEffect, useState } from "react";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import PageHeader from "../components/ui/PageHeader";
import { useI18n } from "../i18n";
import {
  fetchBillingSummary,
  fetchUsage,
  quotaLines,
  formatPrice,
  type BillingSummary,
  type QuotaLine,
  type UsageResponse,
} from "../api/billing";

const STATUS_LABEL: Record<string, string> = {
  trialing: "Đang dùng thử",
  active: "Đang hoạt động",
  past_due: "Quá hạn thanh toán",
  suspended: "Tạm ngưng",
  cancelled: "Đã huỷ",
};

const STATUS_TONE: Record<string, string> = {
  trialing: "bg-sky-100 text-sky-800",
  active: "bg-sky-100 text-sky-800",
  past_due: "bg-amber-100 text-amber-800",
  suspended: "bg-red-100 text-red-800",
  cancelled: "bg-slate-200 text-slate-700",
};

/**
 * Thứ tự các dòng hạn mức, quan trọng nhất lên đầu.
 *
 * `samples`, `classes`, `seats` và `training_jobs_this_month` ĐÃ GỠ ở v8: mô
 * hình bốn gói bỏ cả bốn, và từ đó ràng buộc dữ liệu duy nhất là DUNG LƯỢNG.
 * Để tên cũ lại đây thì vô hại (backend không trả chúng nữa) nhưng nó nói dối
 * người đọc mã về việc hệ thống đang cưỡng chế cái gì.
 *
 * Tên nào backend trả mà không có ở đây vẫn hiện — ở cuối danh sách. Nên thêm
 * một hạn mức mới ở backend không làm nó biến mất khỏi giao diện.
 */
const METRIC_ORDER = [
  "storage",
  "api_keys",
  "webhook_endpoints",
  "training_jobs_running",
  "training_jobs_queued",
];

/** MB/GB cho dòng dung lượng; phép đếm cho mọi dòng còn lại. */
function formatQuotaValue(n: number, unit?: string): string {
  if (unit !== "bytes") return n.toLocaleString("vi-VN");
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

/** Ngưỡng đổi màu. 100% là đã chặn, 80% là sắp chặn — hai tin khác nhau. */
function barTone(percent: number): string {
  if (percent >= 100) return "bg-red-500";
  if (percent >= 80) return "bg-amber-500";
  return "bg-ctu-blue";
}

function QuotaBar({ line }: { line: QuotaLine & { key: string } }) {
  const { t } = useI18n();
  return (
    <div className="py-3">
      <div className="mb-1.5 flex items-baseline justify-between gap-3">
        <span className="text-sm font-medium text-slate-700">{line.label}</span>
        <span className="font-mono text-sm tabular-nums text-slate-600">
          {formatQuotaValue(line.used, line.unit)}
          {line.unlimited ? (
            <span className="ml-1 text-slate-400">{t("/ không giới hạn")}</span>
          ) : (
            <span className="ml-1 text-slate-400">
              / {formatQuotaValue(line.limit ?? 0, line.unit)}
            </span>
          )}
        </span>
      </div>
      {line.percent === null ? null : (
        <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className={`h-full rounded-full transition-all ${barTone(line.percent)}`}
            style={{ width: `${Math.min(100, line.percent)}%` }}
            role="progressbar"
            aria-valuenow={Math.round(line.percent)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={line.label}
          />
        </div>
      )}
    </div>
  );
}

function TotalsGrid({ totals }: { totals: Record<string, number> }) {
  const { t } = useI18n();
  const cards: Array<[string, string, (v: number) => string]> = [
    ["samples_created", t("Mẫu đã thu"), (v) => v.toLocaleString("vi-VN")],
    ["training_jobs_started", t("Lượt huấn luyện"), (v) => v.toLocaleString("vi-VN")],
    [
      "training_seconds",
      t("Thời gian huấn luyện"),
      (v) => (v < 3600 ? t("{n} phút", { n: Math.round(v / 60) }) : t("{n} giờ", { n: (v / 3600).toFixed(1) })),
    ],
    ["active_users", t("Người đóng góp"), (v) => v.toLocaleString("vi-VN")],
  ];
  // `storage_mb` CỐ Ý không có ở đây. Dung lượng đã là một dòng hạn mức ở trên,
  // đọc từ bộ đếm bền và cập nhật ngay khi ghi. Số ở lưới này đến từ lượt gộp
  // hằng ngày, nên nó trễ tới một ngày — hai con số cho cùng một câu hỏi, lệch
  // nhau, trên cùng một trang. Người dùng gặp thế thì không tin con nào.
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {cards.map(([key, label, fmt]) => (
        <div key={key} className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
            {label}
          </div>
          <div className="mt-1 font-mono text-xl font-semibold tabular-nums text-slate-900">
            {fmt(totals[key] ?? 0)}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function BillingPage() {
  const { t } = useI18n();
  const [summary, setSummary] = useState<BillingSummary | null>(null);
  const [usage, setUsage] = useState<UsageResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Song song: hai lượt gọi không phụ thuộc nhau, và nối tiếp chúng làm
      // trang chậm gấp đôi mà không đổi gì.
      const [summaryData, usageData] = await Promise.all([
        fetchBillingSummary(),
        fetchUsage(30),
      ]);
      setSummary(summaryData);
      setUsage(usageData);
    } catch (err) {
      setError(
        err instanceof Error ? err.message: t("Không tải được thông tin gói dịch vụ."),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <LoadingSpinner />;

  if (error) {
    return (
      <div className="p-4">
        <PageHeader title={t("Gói dịch vụ")} subtitle={t("Hạn mức và mức dùng của tổ chức")} />
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-800">
          {error}
          <button
            type="button"
            onClick={() => void load()}
            className="ml-3 rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
          >
            {t("Thử lại")}
          </button>
        </div>
      </div>
    );
  }

  if (!summary) return null;

  const lines = quotaLines(summary);
  const ordered = [
    ...METRIC_ORDER.map((key) => lines.find((l) => l.key === key)).filter(
      (l): l is QuotaLine & { key: string } => Boolean(l),
    ),
    // Chỉ số mới thêm ở backend mà chưa có trong METRIC_ORDER vẫn phải hiện,
    // ở cuối. Bỏ sót chúng nghĩa là một hạn mức có thật mà người dùng không
    // bao giờ nhìn thấy.
    ...lines.filter((l) => !METRIC_ORDER.includes(l.key)),
  ];
  const status = summary.tenant.billing_status;

  return (
    <div className="space-y-6 p-4">
      <PageHeader title={t("Gói dịch vụ")} subtitle={t("Hạn mức và mức dùng của tổ chức")} />

      <section className="rounded-2xl border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-sm text-slate-500">
              {summary.tenant.display_name || summary.tenant.tenant_id}
            </div>
            <h2 className="mt-0.5 text-2xl font-bold text-slate-900">
              {summary.plan.display_name}
            </h2>
            {summary.plan.description ? (
              <p className="mt-1 max-w-prose text-sm text-slate-600">
                {summary.plan.description}
              </p>
            ) : null}
          </div>
          <div className="text-right">
            <span
              className={`inline-block rounded-full px-3 py-1 text-xs font-semibold ${
                STATUS_TONE[status] ?? "bg-slate-100 text-slate-700"
              }`}
            >
              {t(STATUS_LABEL[status]) ?? status}
            </span>
            <div className="mt-2 font-mono text-lg font-semibold tabular-nums text-slate-900">
              {formatPrice(summary.plan.price_cents, summary.plan.currency)}
              {summary.plan.billing_period === "monthly" ? (
                <span className="ml-1 text-sm font-normal text-slate-500">{t("/tháng")}</span>
              ) : null}
            </div>
          </div>
        </div>

        {summary.tenant.trial_ends_at ? (
          <p className="mt-4 rounded-lg bg-sky-50 px-4 py-2.5 text-sm text-sky-900">
            {t("Bản dùng thử kết thúc vào {ngay}. Liên hệ quản trị viên nền tảng để chuyển sang gói chính thức.", { ngay: new Date(summary.tenant.trial_ends_at).toLocaleDateString("vi-VN") })}
          </p>
        ) : null}

        {status === "suspended" || status === "cancelled" ? (
          <p className="mt-4 rounded-lg bg-red-50 px-4 py-2.5 text-sm text-red-900">
            {t("Tổ chức đang tạm ngưng: bạn vẫn xem được dữ liệu nhưng không thêm mới được. Vui lòng liên hệ quản trị viên nền tảng.")}
          </p>
        ) : null}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6">
        <h3 className="mb-1 text-lg font-semibold text-slate-900">{t("Hạn mức")}</h3>
        <p className="mb-2 text-sm text-slate-500">
          {t("Các chỉ số đếm được đọc thẳng từ dữ liệu hiện có. Dung lượng dùng một bộ đếm riêng, được đối chiếu với đĩa mỗi ngày.")}
        </p>
        <div className="divide-y divide-slate-100">
          {ordered.map((line) => (
            <QuotaBar key={line.key} line={line} />
          ))}
        </div>
      </section>

      {usage ? (
        <section>
          <h3 className="mb-1 text-lg font-semibold text-slate-900">
            {t("Mức dùng 30 ngày qua")}
          </h3>
          <p className="mb-3 text-sm text-slate-500">
            {t("Hoạt động trong kỳ, không phải hạn mức. Dung lượng hiện ở phần Hạn mức phía trên.")}
          </p>
          <TotalsGrid totals={usage.totals} />
        </section>
      ) : null}
    </div>
  );
}
