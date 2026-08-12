import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';

/**
 * Trang Gói dịch vụ.
 *
 * Trọng tâm là những chỗ một lỗi hiển thị sẽ nói SAI về hạn mức — thứ người
 * dùng dựa vào để quyết định có nâng gói hay không:
 *
 *  - "không giới hạn" không được vẽ thành thanh 0% (gợi ý "sắp hết", ngược
 *    hẳn nghĩa thật).
 *  - `_plan` đi kèm trong `usage` không được lọt vào bảng hạn mức thành một
 *    dòng rác.
 *  - Chỉ số backend mới thêm mà giao diện chưa biết vẫn phải hiện, không được
 *    biến mất.
 */

vi.mock('../../api/billing', async () => {
  const actual = await vi.importActual<typeof import('../../api/billing')>(
    '../../api/billing',
  );
  return {
    ...actual,
    fetchBillingSummary: vi.fn(),
    fetchUsage: vi.fn(),
  };
});

import BillingPage from '../BillingPage';
import { fetchBillingSummary, fetchUsage } from '../../api/billing';

const PLAN = {
  plan_code: 'trial',
  display_name: 'Dùng thử',
  description: 'Đủ để đánh giá.',
  max_seats: 3,
  max_samples: 500,
  max_storage_mb: 2048,
  max_classes: 30,
  max_training_jobs_per_month: 5,
  max_concurrent_training_jobs: 1,
  max_queued_training_jobs: 2,
  max_api_keys: 1,
  max_webhook_endpoints: 0,
  price_cents: 0,
  currency: 'VND',
  billing_period: 'none',
  is_self_serve: true,
  trial_days: 30,
};

function summaryWith(usage: Record<string, unknown>) {
  return {
    tenant: {
      tenant_id: 'truong-b-a1b2c3',
      display_name: 'Trường B',
      plan_code: 'trial',
      billing_status: 'trialing',
      trial_ends_at: null,
      is_self_serve: true,
    },
    plan: PLAN,
    usage: { _plan: { plan_code: 'trial', display_name: 'Dùng thử' }, ...usage },
  };
}

const EMPTY_USAGE = { tenant_id: 'truong-b-a1b2c3', days: 30, totals: {}, series: {} };

beforeEach(() => {
  vi.mocked(fetchUsage).mockResolvedValue(EMPTY_USAGE as never);
});

describe('BillingPage', () => {
  it('cappedQuota_rendersAProgressBar', async () => {
    vi.mocked(fetchBillingSummary).mockResolvedValue(
      summaryWith({
        samples: { label: 'số mẫu', used: 250, limit: 500, unlimited: false, percent: 50 },
      }) as never,
    );

    render(<BillingPage />);

    const bar = await screen.findByRole('progressbar', { name: 'số mẫu' });
    expect(bar).toHaveAttribute('aria-valuenow', '50');
  });

  it('unlimitedQuota_rendersNoProgressBar', async () => {
    /**
     * Một thanh 0% cho "không giới hạn" đọc thành "sắp hết" — sai ngược hẳn.
     * Backend gửi `percent: null` chính là để nói "đừng vẽ".
     */
    vi.mocked(fetchBillingSummary).mockResolvedValue(
      summaryWith({
        samples: { label: 'số mẫu', used: 9000, limit: null, unlimited: true, percent: null },
      }) as never,
    );

    render(<BillingPage />);

    expect(await screen.findByText(/không giới hạn/)).toBeInTheDocument();
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });

  it('usagePayload_excludesThePlanKeyFromTheQuotaTable', async () => {
    /**
     * Backend gộp `_plan` vào cùng đối tượng `usage` để giao diện chỉ gọi một
     * lượt. Lọc nó ra nằm ở `quotaLines`, một chỗ — bỏ sót là một dòng
     * "undefined NaN%" hiện giữa bảng.
     */
    vi.mocked(fetchBillingSummary).mockResolvedValue(
      summaryWith({
        samples: { label: 'số mẫu', used: 1, limit: 500, unlimited: false, percent: 0.2 },
      }) as never,
    );

    render(<BillingPage />);

    await screen.findByText('số mẫu');
    expect(screen.getAllByRole('progressbar')).toHaveLength(1);
  });

  it('metricUnknownToTheFrontend_isStillShown', async () => {
    /**
     * Giao diện có một thứ tự hiển thị cố định. Một chỉ số backend thêm sau mà
     * không nằm trong thứ tự đó vẫn phải hiện, ở cuối — nếu không, một hạn mức
     * CÓ THẬT sẽ chặn người dùng mà họ không bao giờ nhìn thấy nó.
     */
    vi.mocked(fetchBillingSummary).mockResolvedValue(
      summaryWith({
        samples: { label: 'số mẫu', used: 1, limit: 500, unlimited: false, percent: 0.2 },
        hạn_mức_mới: {
          label: 'chỉ số chưa biết',
          used: 7,
          limit: 10,
          unlimited: false,
          percent: 70,
        },
      }) as never,
    );

    render(<BillingPage />);

    expect(await screen.findByText('chỉ số chưa biết')).toBeInTheDocument();
  });

  it('suspendedTenant_showsAnExplanationOfWhatStillWorks', async () => {
    const suspended = summaryWith({
      samples: { label: 'số mẫu', used: 1, limit: 500, unlimited: false, percent: 0.2 },
    });
    suspended.tenant.billing_status = 'suspended';
    vi.mocked(fetchBillingSummary).mockResolvedValue(suspended as never);

    render(<BillingPage />);

    // Phải nói rõ ĐỌC vẫn được, GHI thì không — chứ không chỉ "đã bị khoá".
    expect(await screen.findByText(/vẫn xem được dữ liệu/)).toBeInTheDocument();
  });

  it('failedLoad_offersARetryRatherThanABlankPage', async () => {
    vi.mocked(fetchBillingSummary).mockRejectedValue(new Error('mạng hỏng'));

    render(<BillingPage />);

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Thử lại' })).toBeInTheDocument(),
    );
  });
});
