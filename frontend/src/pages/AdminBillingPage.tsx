import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import PageHeader from "../components/ui/PageHeader";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import Badge from "../components/ui/Badge";
import { useToast } from "../hooks/useToast";
import { isSudoRequired, useSudo } from "../hooks/useSudo";
import { friendlyError } from "../lib/errors";
import { toneClasses, toneForStatus, FOCUS_RING } from "../theme/status";
import { AlertTriangleIcon, RefreshIcon } from "../components/ui/Icons";
import { Trans, useI18n } from "../i18n";
import {
  BILLING_STATUSES,
  BILLING_STATUS_LABEL,
  changeTenantPlan,
  changeTenantStatus,
  fetchPlans,
  fetchPlatformUsage,
  formatPrice,
  updatePlan,
  type BillingStatus,
  type Plan,
  type PlanChanges,
  type PlatformUsageRow,
} from "../api/billing";

/**
 * Quản trị gói dịch vụ — mặt giao diện cho bốn endpoint nền tảng của
 * `routers/billing.py` vốn không có chỗ nào gọi tới.
 *
 * Trước trang này, đổi gói của một trường hay treo một tổ chức quá hạn chỉ làm
 * được bằng `curl`, và sửa hạn mức của một gói chỉ làm được bằng cách gõ SQL
 * vào cơ sở dữ liệu sản xuất — đúng thứ mà chú thích trong `plans.update_plan`
 * nói là nó tồn tại để tránh.
 *
 * Ba thao tác đòi **sudo**, và giao diện không hỏi trước
 * ------------------------------------------------------
 * Giao diện không biết phiên sudo còn hạn hay không. Hỏi mật khẩu trước mỗi
 * lượt bấm là bắt người vận hành gõ lại cả khi phiên vẫn còn. Nên: gọi thẳng,
 * bắt `sudo_required`, hỏi, rồi gọi lại đúng một lần. Xem `hooks/useSudo`.
 *
 * `null` ở một trần nghĩa là KHÔNG GIỚI HẠN
 * ------------------------------------------
 * Không phải "để nguyên". Ô trống trong biểu mẫu dưới đây gửi lên `null`, và
 * đó là ý nghĩa mạnh nhất trong cả trang — nhầm nó với "bỏ qua" là gỡ trần của
 * mọi tenant đang ở gói đó. Vì vậy ô trống hiện chữ "không giới hạn" chứ không
 * để rỗng suông.
 *
 * @i18n-key-table — nhãn hạn mức trong bảng cấu hình là KHOÁ từ điển.
 */

const LIMIT_FIELDS: { key: keyof PlanChanges; label: string; nullable: boolean }[] = [
  { key: "max_seats", label: "Số tài khoản", nullable: true },
  { key: "max_samples", label: "Số mẫu", nullable: true },
  { key: "max_storage_mb", label: "Dung lượng (MB)", nullable: true },
  { key: "max_classes", label: "Số lớp", nullable: true },
  { key: "max_training_jobs_per_month", label: "Lượt huấn luyện / tháng", nullable: true },
  { key: "max_concurrent_training_jobs", label: "Huấn luyện song song", nullable: false },
  { key: "max_queued_training_jobs", label: "Hàng đợi huấn luyện", nullable: false },
  { key: "max_api_keys", label: "Số khoá API", nullable: false },
  { key: "max_webhook_endpoints", label: "Số webhook", nullable: false },
];

export default function AdminBillingPage() {
  const { t } = useI18n();
  const { toast } = useToast();
  const { ensureSudo } = useSudo();

  const [plans, setPlans] = useState<Plan[]>([]);
  const [usageRows, setUsageRows] = useState<PlatformUsageRow[]>([]);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);

  // Lượt tải gần nhất thắng. Đổi khoảng ngày hai lần liên tiếp mà không canh
  // thì phản hồi của lượt cũ về sau sẽ vẽ đè lên số liệu mới.
  const run = useRef(0);

  const load = useCallback(async () => {
    const mine = ++run.current;
    setLoading(true);
    try {
      const [p, u] = await Promise.all([fetchPlans(), fetchPlatformUsage(days)]);
      if (mine !== run.current) return;
      setPlans(p);
      setUsageRows(u);
      setLoadError("");
    } catch (err) {
      if (mine !== run.current) return;
      setLoadError(friendlyError(err, t("Không tải được bảng giá và số liệu sử dụng.")));
    } finally {
      if (mine === run.current) setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    void load();
  }, [load]);

  /**
   * Chạy một thao tác cần sudo: thử một lần, nếu bị đòi thì hỏi rồi thử lại
   * đúng một lần nữa. Không lặp — hai lần sai mật khẩu là hai lần bị từ chối,
   * và một vòng lặp ở đây sẽ khoá tài khoản của chính người vận hành.
   */
  const withSudo = useCallback(
    async (key: string, why: string, action: () => Promise<unknown>, ok: string) => {
      setBusy(key);
      try {
        try {
          await action();
        } catch (err) {
          if (!isSudoRequired(err)) throw err;
          if (!(await ensureSudo(why))) {
            toast.error(t("Đã huỷ: thao tác này cần xác thực lại mật khẩu."));
            return;
          }
          await action();
        }
        toast.success(ok);
        await load();
      } catch (err) {
        toast.error(friendlyError(err, t("Thao tác không thành công.")));
      } finally {
        setBusy(null);
      }
    },
    [ensureSudo, toast, load],
  );

  const planByCode = useMemo(
    () => new Map(plans.map((p) => [p.plan_code, p])),
    [plans],
  );

  return (
    <div className="px-4 py-6 sm:px-6 lg:px-8">
      <PageHeader
        title={t("Gói dịch vụ & thanh toán")}
        subtitle={t("Sửa hạn mức của từng gói, đổi gói cho một tổ chức, và treo tổ chức quá hạn. Các thao tác thay đổi đều cần xác thực lại mật khẩu và được ghi vào nhật ký kiểm toán.")}
        breadcrumb={[{ label: t("Trang chủ"), href: "/" }, { label: t("Gói dịch vụ") }]}
        actions={
          <button
            type="button"
            onClick={() => void load()}
            className={`inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-medium ${toneClasses("neutral", "outline")} ${FOCUS_RING}`}
          >
            <RefreshIcon className="h-4 w-4" aria-hidden="true" />
            {t("Tải lại")}
          </button>
        }
      />

      {loadError ? (
        <div
          role="alert"
          className={`mb-5 flex items-start gap-3 rounded-xl border px-4 py-3 text-sm ${toneClasses("danger", "soft")}`}
        >
          <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{loadError}</span>
        </div>
      ) : null}

      {loading ? (
        <LoadingSpinner />
      ) : (
        <div className="space-y-6">
          {/* ------------------------------------------------------- bảng giá */}
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-1 font-semibold text-slate-700">{t("Bảng giá")}</h2>
            <p className="mb-4 text-xs text-slate-500">
              <Trans
                k="Sửa một trần ở đây tác động tới {pham_vi} đang ở gói đó. Ô để trống nghĩa là {y_nghia}, không phải &quot;giữ nguyên&quot;."
                vars={{
                  pham_vi: <strong>{t("mọi tổ chức")}</strong>,
                  y_nghia: <strong>{t("không giới hạn")}</strong>,
                }}
              />
            </p>

            <div className="space-y-3">
              {plans.map((plan) => (
                <PlanCard
                  key={plan.plan_code}
                  plan={plan}
                  open={editing === plan.plan_code}
                  busy={busy === `plan-${plan.plan_code}`}
                  onToggle={() =>
                    setEditing((cur) => (cur === plan.plan_code ? null : plan.plan_code))
                  }
                  onSave={(changes) =>
                    withSudo(
                      `plan-${plan.plan_code}`,
                      t('Sửa hạn mức của gói "{ten}"', { ten: plan.display_name }),
                      () => updatePlan(plan.plan_code, changes),
                      t("Đã cập nhật gói"),
                    ).then(() => setEditing(null))
                  }
                />
              ))}
            </div>
          </section>

          {/* --------------------------------------------- mức dùng theo tổ chức */}
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3 flex flex-wrap items-center gap-3">
              <h2 className="font-semibold text-slate-700">{t("Mức dùng theo tổ chức")}</h2>
              <label className="ml-auto flex items-center gap-2 text-sm text-slate-600">
                {t("Khoảng")}
                <select
                  value={days}
                  onChange={(e) => setDays(Number(e.target.value))}
                  className="rounded-md border border-slate-200 px-2 py-1 text-sm"
                >
                  <option value={7}>{t("7 ngày")}</option>
                  <option value={30}>{t("30 ngày")}</option>
                  <option value={90}>{t("90 ngày")}</option>
                </select>
              </label>
            </div>

            {usageRows.length === 0 ? (
              <p className="text-sm text-slate-400">
                <Trans
                  k="Chưa có số đo nào trong khoảng này. Số đo được gộp mỗi ngày bởi tác vụ nền; một bản triển khai vừa dựng có thể cần chạy {lenh}."
                  vars={{
                    lenh: <code className="font-mono text-xs">app.cli.backfill_usage</code>,
                  }}
                />
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                      <th className="py-2 pr-3 font-medium">{t("Tổ chức")}</th>
                      <th className="py-2 px-3 font-medium">{t("Gói")}</th>
                      <th className="py-2 px-3 font-medium">{t("Trạng thái")}</th>
                      <th className="py-2 px-3 text-right font-medium">{t("Mẫu")}</th>
                      <th className="py-2 px-3 text-right font-medium">{t("Lượt huấn luyện")}</th>
                      <th className="py-2 pl-3 text-right font-medium">{t("Dung lượng (MB)")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {usageRows.map((row) => (
                      <TenantRow
                        key={row.tenant_id}
                        row={row}
                        plans={plans}
                        planName={
                          planByCode.get(row.plan_code || "")?.display_name || row.plan_code || "—"
                        }
                        busy={busy === `tenant-${row.tenant_id}`}
                        onPlan={(code) =>
                          withSudo(
                            `tenant-${row.tenant_id}`,
                            t("Đổi gói của \"{display_name}\"", { display_name: row.display_name }),
                            () => changeTenantPlan(row.tenant_id, code),
                            t("Đã đổi gói"),
                          )
                        }
                        onStatus={(status, reason) =>
                          withSudo(
                            `tenant-${row.tenant_id}`,
                            t("Đổi trạng thái của \"{display_name}\"", { display_name: row.display_name }),
                            () => changeTenantStatus(row.tenant_id, status, reason),
                            t("Đã đổi trạng thái"),
                          )
                        }
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

function PlanCard({
  plan,
  open,
  busy,
  onToggle,
  onSave,
}: {
  plan: Plan;
  open: boolean;
  busy: boolean;
  onToggle: () => void;
  onSave: (changes: PlanChanges) => void;
}) {
  const { t } = useI18n();
  // Chuỗi, không phải số: một ô số rỗng trong React cho ra `NaN`, và `NaN` gửi
  // lên máy chủ thành `null` — tức là "không giới hạn", đúng thứ nguy hiểm
  // nhất có thể xảy ra do một ô bị xoá nhầm.
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [price, setPrice] = useState(String(plan.price_cents));

  useEffect(() => {
    if (!open) return;
    const next: Record<string, string> = {};
    for (const f of LIMIT_FIELDS) {
      const v = plan[f.key as keyof Plan] as number | null | undefined;
      next[f.key as string] = v === null || v === undefined ? "" : String(v);
    }
    setDraft(next);
    setPrice(String(plan.price_cents));
  }, [open, plan]);

  const build = (): PlanChanges | null => {
    const changes: PlanChanges = {};
    for (const f of LIMIT_FIELDS) {
      const raw = (draft[f.key as string] ?? "").trim();
      const before = plan[f.key as keyof Plan] as number | null | undefined;
      if (raw === "") {
        if (!f.nullable) return null; // máy chủ sẽ từ chối; chặn trước cho rõ
        if (before !== null) (changes as Record<string, unknown>)[f.key as string] = null;
        continue;
      }
      const n = Number(raw);
      if (!Number.isFinite(n) || n < 0) return null;
      if (n !== before) (changes as Record<string, unknown>)[f.key as string] = n;
    }
    const p = Number(price);
    if (!Number.isFinite(p) || p < 0) return null;
    if (p !== plan.price_cents) changes.price_cents = p;
    return changes;
  };

  const changes = open ? build() : null;
  const invalid = open && changes === null;
  const nothingToDo = changes !== null && Object.keys(changes).length === 0;

  return (
    <div className="rounded-lg border border-slate-200">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <span className="font-semibold text-slate-800">{plan.display_name}</span>
        <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-500">
          {plan.plan_code}
        </code>
        <span className="text-sm text-slate-600">
          {formatPrice(plan.price_cents, plan.currency)}
        </span>
        {plan.is_self_serve ? <Badge variant="success">{t("Tự đăng ký")}</Badge> : null}
        <button
          type="button"
          onClick={onToggle}
          className={`ml-auto rounded-md border px-3 py-1.5 text-sm font-medium ${toneClasses("neutral", "outline")} ${FOCUS_RING}`}
        >
          {open ? t("Đóng") : t("Sửa hạn mức")}
        </button>
      </div>

      {open && (
        <div className="border-t border-slate-100 px-4 py-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {LIMIT_FIELDS.map((f) => (
              <label key={f.key as string} className="block">
                <span className="mb-1 block text-xs font-medium text-slate-600">
                  {t(f.label)}
                  {f.nullable ? (
                    <span className="ml-1 font-normal text-slate-400">
                      {t("(trống = không giới hạn)")}
                    </span>
                  ) : null}
                </span>
                <input
                  value={draft[f.key as string] ?? ""}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, [f.key as string]: e.target.value }))
                  }
                  inputMode="numeric"
                  placeholder={f.nullable ? t("không giới hạn") : "0"}
                  className="w-full rounded-md border border-slate-200 px-3 py-1.5 text-sm tabular-nums"
                />
              </label>
            ))}
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-slate-600">
                {t("Giá ({tien} / {ky})", { tien: plan.currency, ky: plan.billing_period })}
              </span>
              <input
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                inputMode="numeric"
                className="w-full rounded-md border border-slate-200 px-3 py-1.5 text-sm tabular-nums"
              />
            </label>
          </div>

          {invalid ? (
            <p className="mt-3 text-sm text-red-700">
              {t("Có ô chưa hợp lệ: chỉ nhận số không âm, và những trần không cho phép &quot;không giới hạn&quot; thì không được để trống.")}
            </p>
          ) : null}

          <button
            type="button"
            disabled={busy || invalid || nothingToDo}
            onClick={() => changes && onSave(changes)}
            className={`mt-4 rounded-md border px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50 ${toneClasses("success", "solid")} ${FOCUS_RING}`}
          >
            {busy ? t("Đang lưu…") : nothingToDo ? t("Chưa có thay đổi") : t("Lưu thay đổi")}
          </button>
        </div>
      )}
    </div>
  );
}

function TenantRow({
  row,
  plans,
  planName,
  busy,
  onPlan,
  onStatus,
}: {
  row: PlatformUsageRow;
  plans: Plan[];
  planName: string;
  busy: boolean;
  onPlan: (planCode: string) => void;
  onStatus: (status: BillingStatus, reason: string) => void;
}) {
  const { t } = useI18n();
  const status = (row.billing_status || "") as BillingStatus;

  return (
    <tr className="border-b border-slate-100 align-top">
      <td className="py-2.5 pr-3">
        <div className="font-medium text-slate-800">{row.display_name}</div>
        <code className="font-mono text-xs text-slate-400">{row.tenant_id}</code>
      </td>

      <td className="py-2.5 px-3">
        <select
          value={row.plan_code || ""}
          disabled={busy}
          aria-label={t("Gói của {display_name}", { display_name: row.display_name })}
          onChange={(e) => e.target.value && onPlan(e.target.value)}
          className="rounded-md border border-slate-200 px-2 py-1 text-sm disabled:opacity-50"
        >
          <option value="">{planName}</option>
          {plans.map((p) => (
            <option key={p.plan_code} value={p.plan_code}>
              {p.display_name}
            </option>
          ))}
        </select>
      </td>

      <td className="py-2.5 px-3">
        <div className="flex flex-col gap-1.5">
          <Badge variant={toneForStatus(status === "active" ? "active" : status)}>
            {t(BILLING_STATUS_LABEL[status]) ?? status ?? "—"}
          </Badge>
          <select
            value=""
            disabled={busy}
            aria-label={t("Đổi trạng thái của {display_name}", { display_name: row.display_name })}
            onChange={(e) => {
              const next = e.target.value as BillingStatus;
              if (!next) return;
              // Lý do là BẮT BUỘC khi treo: nó đi vào nhật ký kiểm toán và là
              // thứ duy nhất trả lời được "vì sao trường này bị khoá" ba tháng
              // sau. Với các trạng thái khác thì không cần.
              const needsReason = next === "suspended" || next === "cancelled";
              const reason = needsReason
                ? window.prompt(t("Lý do {p1}:", { p1: t(BILLING_STATUS_LABEL[next]).toLowerCase() })) || ""
                : "";
              e.target.value = "";
              if (needsReason && !reason.trim()) return;
              onStatus(next, reason);
            }}
            className="rounded-md border border-slate-200 px-2 py-1 text-xs disabled:opacity-50"
          >
            <option value="">{t("Đổi trạng thái…")}</option>
            {BILLING_STATUSES.filter((s) => s !== status).map((s) => (
              <option key={s} value={s}>
                {t(BILLING_STATUS_LABEL[s])}
              </option>
            ))}
          </select>
        </div>
      </td>

      <td className="py-2.5 px-3 text-right tabular-nums">{row.samples.toLocaleString("vi-VN")}</td>
      <td className="py-2.5 px-3 text-right tabular-nums">
        {row.training_jobs.toLocaleString("vi-VN")}
      </td>
      <td className="py-2.5 pl-3 text-right tabular-nums">
        {row.storage_mb.toLocaleString("vi-VN")}
      </td>
    </tr>
  );
}
