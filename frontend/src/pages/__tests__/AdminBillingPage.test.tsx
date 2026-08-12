import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

/**
 * Quản trị gói dịch vụ.
 *
 * Ba thứ được ghim, và cả ba đều là thứ hỏng thì tốn tiền thật:
 *
 *   1. **Ô trống = KHÔNG GIỚI HẠN.** Không phải "giữ nguyên". Một ô bị xoá
 *      nhầm rồi gửi đi sẽ gỡ trần của MỌI tổ chức đang ở gói đó. Với những
 *      trần máy chủ không cho phép null, ô trống phải chặn nút Lưu chứ không
 *      được gửi lên rồi nhận 422.
 *   2. **Chỉ gửi những trường ĐÃ ĐỔI.** Gửi cả bảng là ghi đè những cột người
 *      khác vừa sửa ở tab bên cạnh.
 *   3. **Hỏi sudo sau khi bị từ chối, và thử lại đúng MỘT lần.** Vòng lặp ở
 *      đây sẽ khoá tài khoản của chính người vận hành.
 */

vi.mock('../../api/billing', async () => {
  const actual = await vi.importActual<typeof import('../../api/billing')>('../../api/billing');
  return {
    ...actual,
    fetchPlans: vi.fn(),
    fetchPlatformUsage: vi.fn(),
    updatePlan: vi.fn(),
    changeTenantPlan: vi.fn(),
    changeTenantStatus: vi.fn(),
  };
});

const ensureSudo = vi.fn();
vi.mock('../../hooks/useSudo', async () => {
  const actual = await vi.importActual<typeof import('../../hooks/useSudo')>('../../hooks/useSudo');
  return { ...actual, useSudo: () => ({ ensureSudo, sudoError: () => 'sai mật khẩu' }) };
});

const toastError = vi.fn();
const toastSuccess = vi.fn();
vi.mock('../../hooks/useToast', () => ({
  useToast: () => ({ toast: { success: toastSuccess, error: toastError, info: vi.fn() } }),
}));

import AdminBillingPage from '../AdminBillingPage';
import {
  changeTenantStatus,
  fetchPlans,
  fetchPlatformUsage,
  updatePlan,
} from '../../api/billing';

const PLAN = {
  plan_code: 'growth',
  display_name: 'Gói Phát triển',
  description: '',
  max_seats: 20,
  max_samples: 5000,
  max_storage_mb: 2048,
  max_classes: 200,
  max_training_jobs_per_month: 30,
  max_concurrent_training_jobs: 1,
  max_queued_training_jobs: 3,
  max_api_keys: 5,
  max_webhook_endpoints: 3,
  price_cents: 500000,
  currency: 'VND',
  billing_period: 'month',
  is_self_serve: true,
  trial_days: 14,
};

const USAGE = {
  tenant_id: 'truong-b',
  display_name: 'Trường B',
  plan_code: 'growth',
  billing_status: 'active',
  samples: 1200,
  training_seconds: 900,
  training_jobs: 4,
  storage_mb: 300,
};

const view = () =>
  render(
    <MemoryRouter>
      <AdminBillingPage />
    </MemoryRouter>,
  );

const openEditor = async () => {
  fireEvent.click(await screen.findByRole('button', { name: 'Sửa hạn mức' }));
  return screen.findByLabelText(/Số mẫu/);
};

beforeEach(() => {
  vi.clearAllMocks();
  (fetchPlans as any).mockResolvedValue([PLAN]);
  (fetchPlatformUsage as any).mockResolvedValue([USAGE]);
  (updatePlan as any).mockResolvedValue(PLAN);
  ensureSudo.mockResolvedValue(true);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('Sửa hạn mức của một gói', () => {
  it('chỉ gửi những trường đã đổi', async () => {
    view();
    const samples = await openEditor();

    fireEvent.change(samples, { target: { value: '9000' } });
    fireEvent.click(screen.getByRole('button', { name: 'Lưu thay đổi' }));

    await waitFor(() => expect(updatePlan).toHaveBeenCalledWith('growth', { max_samples: 9000 }));
  });

  it('ô trống ở một trần cho phép null gửi lên NULL, nghĩa là không giới hạn', async () => {
    view();
    const samples = await openEditor();

    fireEvent.change(samples, { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: 'Lưu thay đổi' }));

    await waitFor(() =>
      expect(updatePlan).toHaveBeenCalledWith('growth', { max_samples: null }),
    );
  });

  it('ô trống ở một trần KHÔNG cho phép null thì chặn nút Lưu', async () => {
    /** Máy chủ sẽ từ chối 422; chặn ở đây để lời từ chối không tới sau khi
     * người vận hành đã điền xong cả biểu mẫu. */
    view();
    await openEditor();

    fireEvent.change(screen.getByLabelText(/Số khoá API/), { target: { value: '' } });

    expect(screen.getByRole('button', { name: 'Lưu thay đổi' })).toBeDisabled();
    expect(screen.getByText(/không được để trống/)).toBeInTheDocument();
  });

  it('không có gì đổi thì nút nói ra điều đó thay vì gửi một yêu cầu rỗng', async () => {
    view();
    await openEditor();

    expect(screen.getByRole('button', { name: 'Chưa có thay đổi' })).toBeDisabled();
    expect(updatePlan).not.toHaveBeenCalled();
  });

  it('số âm bị chặn', async () => {
    view();
    const samples = await openEditor();

    fireEvent.change(samples, { target: { value: '-5' } });
    expect(screen.getByRole('button', { name: 'Lưu thay đổi' })).toBeDisabled();
  });
});

describe('Nâng quyền', () => {
  it('bị đòi sudo thì hỏi rồi thử lại ĐÚNG một lần', async () => {
    (updatePlan as any)
      .mockRejectedValueOnce({ response: { status: 403, data: { code: 'sudo_required' } } })
      .mockResolvedValueOnce(PLAN);

    view();
    const samples = await openEditor();
    fireEvent.change(samples, { target: { value: '9000' } });
    fireEvent.click(screen.getByRole('button', { name: 'Lưu thay đổi' }));

    await waitFor(() => expect(updatePlan).toHaveBeenCalledTimes(2));
    expect(ensureSudo).toHaveBeenCalledTimes(1);
    expect(toastSuccess).toHaveBeenCalledWith('Đã cập nhật gói');
  });

  it('huỷ ở ô mật khẩu thì KHÔNG gọi lại lần nữa', async () => {
    (updatePlan as any).mockRejectedValue({
      response: { status: 403, data: { code: 'sudo_required' } },
    });
    ensureSudo.mockResolvedValue(false);

    view();
    const samples = await openEditor();
    fireEvent.change(samples, { target: { value: '9000' } });
    fireEvent.click(screen.getByRole('button', { name: 'Lưu thay đổi' }));

    await waitFor(() => expect(toastError).toHaveBeenCalled());
    expect(updatePlan).toHaveBeenCalledTimes(1);
  });
});

describe('Treo một tổ chức', () => {
  it('không có lý do thì không treo', async () => {
    /** Lý do đi vào nhật ký kiểm toán và là thứ duy nhất trả lời được "vì sao
     * trường này bị khoá" ba tháng sau. */
    const prompt = vi.spyOn(window, 'prompt').mockReturnValue('   ');
    view();

    fireEvent.change(await screen.findByLabelText('Đổi trạng thái của Trường B'), {
      target: { value: 'suspended' },
    });

    expect(prompt).toHaveBeenCalled();
    await waitFor(() => expect(changeTenantStatus).not.toHaveBeenCalled());
  });

  it('có lý do thì gửi kèm lý do', async () => {
    vi.spyOn(window, 'prompt').mockReturnValue('Quá hạn thanh toán 60 ngày');
    (changeTenantStatus as any).mockResolvedValue({});
    view();

    fireEvent.change(await screen.findByLabelText('Đổi trạng thái của Trường B'), {
      target: { value: 'suspended' },
    });

    await waitFor(() =>
      expect(changeTenantStatus).toHaveBeenCalledWith(
        'truong-b',
        'suspended',
        'Quá hạn thanh toán 60 ngày',
      ),
    );
  });

  it('đổi sang trạng thái không phải treo thì không hỏi lý do', async () => {
    const prompt = vi.spyOn(window, 'prompt');
    (changeTenantStatus as any).mockResolvedValue({});
    view();

    fireEvent.change(await screen.findByLabelText('Đổi trạng thái của Trường B'), {
      target: { value: 'past_due' },
    });

    await waitFor(() =>
      expect(changeTenantStatus).toHaveBeenCalledWith('truong-b', 'past_due', ''),
    );
    expect(prompt).not.toHaveBeenCalled();
  });
});
