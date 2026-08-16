/**
 * Gói dịch vụ, hạn mức và mức dùng.
 *
 * Backend là nguồn sự thật cho MỌI con số ở đây — kể cả trần của gói. Trước
 * đây frontend từng giữ những bản đồ chép tay song song với cơ sở dữ liệu và
 * chúng đã trôi ra khỏi nhau (xem chú thích đầu `vocabulary.ts`); bảng giá là
 * đúng loại dữ liệu sẽ lặp lại chuyện đó, vì nó đổi vì lý do thương mại chứ
 * không vì lý do kỹ thuật.
 *
 * `null` trong mọi trường trần nghĩa là KHÔNG GIỚI HẠN, không phải "chưa
 * biết". Cùng quy ước với bảng `plans` phía backend.
 *
 * @i18n-key-table — `BILLING_STATUS_LABEL` là bảng KHOÁ, dịch tại chỗ đọc.
 */

import axiosClient from "./axiosClient";
import { tr } from "../i18n";

const API_PREFIX = "/api/v1/billing";

export interface Plan {
  plan_code: string;
  display_name: string;
  description: string;
  max_seats: number | null;
  max_samples: number | null;
  max_storage_mb: number | null;
  max_classes: number | null;
  max_training_jobs_per_month: number | null;
  max_concurrent_training_jobs: number;
  max_queued_training_jobs: number;
  max_api_keys: number;
  max_webhook_endpoints: number;
  price_cents: number;
  currency: string;
  billing_period: string;
  is_self_serve: boolean;
  trial_days: number;
}

export interface QuotaLine {
  label: string;
  used: number;
  limit: number | null;
  unlimited: boolean;
  /** null khi không có trần — giao diện dùng nó để quyết định có vẽ thanh không. */
  percent: number | null;
}

export interface BillingSummary {
  tenant: {
    tenant_id: string;
    display_name: string | null;
    plan_code: string;
    billing_status: string;
    trial_ends_at: string | null;
    is_self_serve: boolean;
  };
  plan: Plan;
  /** Khoá `_plan` cũng có mặt nhưng không phải một dòng hạn mức. */
  usage: Record<string, QuotaLine | { plan_code: string; display_name: string }>;
}

export interface UsagePoint {
  date: string;
  value: number;
}

export interface UsageResponse {
  tenant_id: string;
  days: number;
  totals: Record<string, number>;
  series: Record<string, UsagePoint[]>;
}

/** Bảng giá công khai — gọi được cả khi chưa đăng nhập. */
export async function fetchPlans(): Promise<Plan[]> {
  const res = await axiosClient.get(`${API_PREFIX}/plans`);
  return res.data;
}

export async function fetchBillingSummary(): Promise<BillingSummary> {
  const res = await axiosClient.get(`${API_PREFIX}/me`);
  return res.data;
}

export async function fetchUsage(days = 30): Promise<UsageResponse> {
  const res = await axiosClient.get(`${API_PREFIX}/usage`, { params: { days } });
  return res.data;
}

/**
 * Tách các dòng hạn mức thật ra khỏi khoá `_plan` đi kèm.
 *
 * Backend gộp cả hai vào một đối tượng để giao diện chỉ phải gọi một lượt. Việc
 * tách ra nằm ở đây, một chỗ, thay vì mỗi component tự lọc `_plan` — bỏ sót
 * một lần là một dòng "undefined NaN%" hiện ra giữa bảng.
 */
export function quotaLines(summary: BillingSummary): Array<QuotaLine & { key: string }> {
  return Object.entries(summary.usage)
    .filter(([key, value]) => key !== "_plan" && "used" in (value as QuotaLine))
    .map(([key, value]) => ({ key, ...(value as QuotaLine) }));
}

/**
 * Định dạng tiền theo đơn vị nhỏ nhất mà backend lưu.
 *
 * VND không có đơn vị lẻ nên `price_cents` với tiền Việt thực chất là số đồng;
 * chia 100 sẽ hiện sai gấp trăm lần. Đây là lý do hàm này nhìn vào `currency`
 * thay vì chia cứng.
 */
export function formatPrice(cents: number, currency: string): string {
  if (cents === 0) return tr("Miễn phí");
  const amount = currency === "VND" ? cents : cents / 100;
  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(amount);
}

// ------------------------------------------------ vòng quản trị nền tảng
//
// Ba thao tác dưới đây đòi **chế độ sudo** ở máy chủ (`require_sudo`), không
// chỉ quyền quản trị. Giao diện không tự đoán được phiên sudo còn hạn hay
// không, nên cách dùng đúng là GỌI THẲNG rồi bắt `sudo_required` — xem
// `hooks/useSudo.ts`. Hỏi mật khẩu trước mỗi lượt bấm là bắt người vận hành gõ
// lại cả khi phiên vẫn còn hiệu lực.

/** Mỗi tenant một dòng, đã cộng sẵn ở máy chủ (không phải N+1 từ giao diện). */
export interface PlatformUsageRow {
  tenant_id: string;
  display_name: string;
  plan_code: string | null;
  billing_status: string | null;
  samples: number;
  training_seconds: number;
  training_jobs: number;
  storage_mb: number;
}

/** Vòng nền tảng. Chỉ ĐỌC — không cần sudo. */
export async function fetchPlatformUsage(days = 30): Promise<PlatformUsageRow[]> {
  const res = await axiosClient.get<PlatformUsageRow[]>(`${API_PREFIX}/platform-usage`, {
    params: { days },
  });
  return res.data;
}

/**
 * Những cột của một gói mà máy chủ cho sửa.
 *
 * Danh sách này phải khớp `plans.EDITABLE_PLAN_FIELDS`; gửi tên khác sẽ bị từ
 * chối 422 với tên cột nêu đích danh.
 *
 * `null` ở các trần nghĩa là **KHÔNG GIỚI HẠN**, không phải "để nguyên". Đó là
 * lý do thân thư là một đối tượng thưa — chỉ những trường muốn đổi — chứ không
 * phải một model có mọi trường optional: với model đó không phân biệt được
 * "không nêu" và "đặt về không giới hạn".
 */
export interface PlanChanges {
  display_name?: string;
  description?: string;
  max_seats?: number | null;
  max_samples?: number | null;
  max_storage_mb?: number | null;
  max_classes?: number | null;
  max_training_jobs_per_month?: number | null;
  max_concurrent_training_jobs?: number;
  max_queued_training_jobs?: number;
  max_api_keys?: number;
  max_webhook_endpoints?: number;
  price_cents?: number;
  is_self_serve?: boolean;
  is_listed?: boolean;
  trial_days?: number;
}

/** Vòng nền tảng + **sudo**. Tác động tới MỌI tenant đang ở gói này. */
export async function updatePlan(planCode: string, changes: PlanChanges): Promise<Plan> {
  const res = await axiosClient.patch<Plan>(`${API_PREFIX}/plans/${planCode}`, changes);
  return res.data;
}

/** Vòng nền tảng + **sudo**. Ghi kiểm toán: tranh chấp hoá đơn sẽ hỏi ai đổi. */
export async function changeTenantPlan(
  tenantId: string,
  planCode: string,
  note = "",
): Promise<Record<string, unknown>> {
  const res = await axiosClient.patch(`${API_PREFIX}/tenants/${tenantId}/plan`, {
    plan_code: planCode,
    note,
  });
  return res.data;
}

/** Đúng năm giá trị máy chủ nhận. Xem `tenant_admin.set_billing_status`. */
export const BILLING_STATUSES = [
  "trialing",
  "active",
  "past_due",
  "suspended",
  "cancelled",
] as const;
export type BillingStatus = (typeof BILLING_STATUSES)[number];

export const BILLING_STATUS_LABEL: Record<BillingStatus, string> = {
  trialing: "Đang dùng thử",
  active: "Đang hoạt động",
  past_due: "Quá hạn thanh toán",
  suspended: "Tạm treo",
  cancelled: "Đã huỷ",
};

/**
 * Vòng nền tảng + **sudo**. Treo hoặc mở lại một tổ chức.
 *
 * Tenant gốc không treo được — máy chủ trả 409. Đó là chủ ý: treo nó là tự
 * khoá mình ra khỏi chính API vừa dùng để treo.
 */
export async function changeTenantStatus(
  tenantId: string,
  status: BillingStatus,
  reason = "",
): Promise<Record<string, unknown>> {
  const res = await axiosClient.patch(`${API_PREFIX}/tenants/${tenantId}/status`, {
    billing_status: status,
    reason,
  });
  return res.data;
}
