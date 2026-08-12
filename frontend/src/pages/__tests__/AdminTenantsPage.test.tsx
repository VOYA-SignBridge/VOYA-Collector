import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';

/**
 * Trang Quản trị tổ chức.
 *
 * Trang này là mặt giao diện đầu tiên cho 20 endpoint ở `routers/tenants.py`,
 * và nó chứa thao tác **không hồi được duy nhất** của hệ thống: xoá vĩnh viễn
 * một tổ chức. Nên phần lớn test ở đây canh chính cái nút đó, chứ không canh
 * việc danh sách hiện đúng chữ.
 *
 * Ba ràng buộc được ghim:
 *
 *   1. Con số trước câu hỏi — số dòng sẽ mất hiện ra TRƯỚC ô xác nhận.
 *   2. Máy chủ nói vì sao chưa xoá được, giao diện nhắc lại nguyên văn và
 *      KHÔNG hiện ô xác nhận. Hai bộ quy tắc song song sẽ lệch nhau.
 *   3. Một lỗi 403 dự kiến ở `purge-preview` (quản trị viên tổ chức không có
 *      quyền đó) không được làm hỏng ba mục còn lại của trang — đây là lý do
 *      `loadDetail` dùng `Promise.allSettled` chứ không phải `Promise.all`.
 */

/**
 * Chỉ giả lập các HÀM GỌI MẠNG; hằng số lấy nguyên bản thật.
 *
 * Bản trước liệt kê đầy đủ mọi export, kể cả `ROLE_LABEL`. Nghĩa là mỗi lần
 * `api/tenants.ts` thêm một export là tệp này vỡ với "No X export is defined on
 * the mock" — một lỗi nói về chính bản giả lập chứ không nói gì về trang. Tệ
 * hơn: bảng nhãn giả có thể mang những vai KHÔNG tồn tại ở máy chủ và test vẫn
 * xanh. Nó đã như vậy — `owner`/`member` sống trong bản giả này trong khi máy
 * chủ chỉ nhận `admin|editor` (và "không vai").
 *
 * `importOriginal` giữ hằng số thật, nên trang được kiểm với đúng tập vai mà
 * máy chủ chấp nhận.
 */
vi.mock('../../api/tenants', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../api/tenants')>()),
  fetchTenants: vi.fn(),
  createTenant: vi.fn(),
  updateTenant: vi.fn(),
  deleteTenant: vi.fn(),
  fetchMembers: vi.fn(),
  addMember: vi.fn(),
  updateMemberRole: vi.fn(),
  removeMember: vi.fn(),
  fetchInvitations: vi.fn(),
  createInvitation: vi.fn(),
  revokeInvitation: vi.fn(),
  fetchExports: vi.fn(),
  requestExport: vi.fn(),
  exportDownloadUrl: (t: string, e: string) => `/api/v1/tenants/${t}/exports/${e}/download`,
  fetchPurgePreview: vi.fn(),
  purgeTenant: vi.fn(),
  inspectInvitation: vi.fn(),
}));

vi.mock('../../hooks/useToast', () => ({
  useToast: () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }),
}));

import AdminTenantsPage from '../AdminTenantsPage';
import {
  createInvitation,
  fetchExports,
  fetchInvitations,
  fetchMembers,
  fetchPurgePreview,
  fetchTenants,
  purgeTenant,
} from '../../api/tenants';

const TENANT = {
  tenant_id: 'truong-b',
  display_name: 'Trường B',
  slug: 'truong-b',
  is_active: true,
  created_at: '2026-01-05T00:00:00Z',
  created_by: null,
  deleted_at: '2026-07-01T00:00:00Z',
  member_count: 4,
};

const MEMBER = {
  tenant_id: 'truong-b',
  user_id: 'u-1',
  username: 'giaovien',
  email: 'gv@truongb.vn',
  role: 'admin' as const,
  is_active: true,
  created_at: '2026-01-06T00:00:00Z',
};

const PREVIEW_READY = {
  tenant_id: 'truong-b',
  display_name: 'Trường B',
  deleted_at: '2026-07-01T00:00:00Z',
  row_counts: { samples: 3860, classes: 63, users: 10, webhook_deliveries: 0 },
  total_rows: 3933,
  has_ready_export: true,
  blockers: [],
  can_purge: true,
};

const openTenant = async () => {
  fireEvent.click(await screen.findByRole('button', { name: 'Quản lý' }));
};

beforeEach(() => {
  vi.clearAllMocks();
  (fetchTenants as any).mockResolvedValue([TENANT]);
  (fetchMembers as any).mockResolvedValue([MEMBER]);
  (fetchInvitations as any).mockResolvedValue([]);
  (fetchExports as any).mockResolvedValue([]);
  (fetchPurgePreview as any).mockResolvedValue(PREVIEW_READY);
});

describe('Xoá vĩnh viễn một tổ chức', () => {
  it('hiện số dòng sẽ mất trước khi hỏi xác nhận', async () => {
    render(<AdminTenantsPage />);
    await openTenant();

    expect(await screen.findByText(/3.933/)).toBeInTheDocument();
    expect(screen.getByText(/samples/)).toBeInTheDocument();
    expect(screen.getByText('3860')).toBeInTheDocument();
  });

  it('bỏ qua bảng có 0 dòng để không lấp con số thật', async () => {
    render(<AdminTenantsPage />);
    await openTenant();

    await screen.findByText(/samples/);
    expect(screen.queryByText(/webhook_deliveries/)).not.toBeInTheDocument();
  });

  it('nút xoá bị khoá cho tới khi gõ đúng mã tổ chức', async () => {
    render(<AdminTenantsPage />);
    await openTenant();

    const button = await screen.findByRole('button', { name: 'Xoá vĩnh viễn' });
    expect(button).toBeDisabled();

    const input = screen.getByLabelText('Gõ lại mã tổ chức để xác nhận');
    fireEvent.change(input, { target: { value: 'truong-' } });
    expect(button).toBeDisabled();

    fireEvent.change(input, { target: { value: 'truong-b' } });
    expect(button).toBeEnabled();
  });

  it('gửi đúng mã tổ chức làm chuỗi xác nhận', async () => {
    (purgeTenant as any).mockResolvedValue({});
    render(<AdminTenantsPage />);
    await openTenant();

    fireEvent.change(await screen.findByLabelText('Gõ lại mã tổ chức để xác nhận'),
                     { target: { value: 'truong-b' } });
    fireEvent.click(screen.getByRole('button', { name: 'Xoá vĩnh viễn' }));

    await waitFor(() => expect(purgeTenant).toHaveBeenCalledWith('truong-b', 'truong-b'));
  });

  it('máy chủ chặn thì nhắc lại nguyên văn và KHÔNG hiện ô xác nhận', async () => {
    (fetchPurgePreview as any).mockResolvedValue({
      ...PREVIEW_READY,
      deleted_at: null,
      blockers: ['Tổ chức chưa bị xoá mềm. Hãy xoá mềm trước.'],
      can_purge: false,
    });
    render(<AdminTenantsPage />);
    await openTenant();

    expect(await screen.findByText(/Tổ chức chưa bị xoá mềm/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Xoá vĩnh viễn' })).not.toBeInTheDocument();
  });

  it('vẫn cảnh báo khi chưa có bản xuất nào sẵn sàng', async () => {
    (fetchPurgePreview as any).mockResolvedValue({ ...PREVIEW_READY, has_ready_export: false });
    render(<AdminTenantsPage />);
    await openTenant();

    expect(await screen.findByText(/nên xuất dữ liệu trước khi xoá/)).toBeInTheDocument();
  });
});

describe('Một phần bị từ chối không làm hỏng cả trang', () => {
  it('403 ở xem-trước-xoá vẫn giữ nguyên danh sách thành viên', async () => {
    /** Quản trị viên TỔ CHỨC đọc được thành viên nhưng không đọc được
     * `purge-preview` (vòng nền tảng). Với `Promise.all`, lỗi 403 dự kiến đó
     * sẽ xoá sạch cả ba mục kia và trang trông như rỗng. */
    (fetchPurgePreview as any).mockRejectedValue({ response: { status: 403 } });
    render(<AdminTenantsPage />);
    await openTenant();

    expect(await screen.findByText('giaovien')).toBeInTheDocument();
    expect(screen.getByText(/dành cho quản trị\s+viên nền tảng/)).toBeInTheDocument();
  });
});

describe('Tranh chấp khi đổi tổ chức nhanh', () => {
  it('phản hồi của tổ chức cũ về muộn KHÔNG ghi đè tổ chức đang chọn', async () => {
    /** Bốn request song song không có thứ tự đảm bảo. Chọn A rồi đổi ngay sang
     * B: nếu `fetchMembers(A)` về sau `fetchMembers(B)` mà không ai canh, màn
     * hình hiện thành viên của A dưới tiêu đề của B. Trên một trang có nút
     * "Xoá vĩnh viễn", nhầm lẫn đó không dừng ở thẩm mỹ.
     *
     * Ở đây A trả về CHẬM và B trả về NGAY, tức đúng thứ tự gây lỗi. */
    (fetchTenants as any).mockResolvedValue([
      { ...TENANT, tenant_id: 'to-chuc-a', display_name: 'A', deleted_at: null },
      { ...TENANT, tenant_id: 'to-chuc-b', display_name: 'B', deleted_at: null },
    ]);

    let releaseA: (v: any) => void = () => {};
    (fetchMembers as any).mockImplementation((id: string) => {
      if (id === 'to-chuc-a') {
        return new Promise((resolve) => { releaseA = resolve; });
      }
      return Promise.resolve([{ ...MEMBER, user_id: 'u-b', username: 'nguoi-cua-B' }]);
    });

    render(<AdminTenantsPage />);
    const buttons = await screen.findAllByRole('button', { name: 'Quản lý' });

    fireEvent.click(buttons[0]);                       // chọn A — treo
    fireEvent.click(await screen.findByRole('button', { name: 'Đóng' }));
    fireEvent.click((await screen.findAllByRole('button', { name: 'Quản lý' }))[1]); // chọn B

    expect(await screen.findByText('nguoi-cua-B')).toBeInTheDocument();

    releaseA([{ ...MEMBER, user_id: 'u-a', username: 'nguoi-cua-A' }]);

    await waitFor(() => expect(screen.getByText('nguoi-cua-B')).toBeInTheDocument());
    expect(screen.queryByText('nguoi-cua-A')).not.toBeInTheDocument();
  });
});

describe('Lời mời', () => {
  const ACCEPT_URL = 'https://voya.example.edu/invitation#token=ma-moi-rat-bi-mat';

  const invite = async (over: Record<string, unknown> = {}) => {
    (createInvitation as any).mockResolvedValue({
      invitation_id: 'i-1', tenant_id: 'truong-b', email: 'moi@truongb.vn',
      role: null, created_at: '2026-08-08T00:00:00Z', expires_at: null,
      accepted_at: null, revoked_at: null, token: 'ma-moi-rat-bi-mat',
      accept_url: ACCEPT_URL, email_sent: false, ...over,
    });
    render(<AdminTenantsPage />);
    await openTenant();
    fireEvent.change(await screen.findByLabelText('Email được mời'),
                     { target: { value: 'moi@truongb.vn' } });
    fireEvent.click(screen.getByRole('button', { name: 'Mời' }));
  };

  it('hiện một lần và chỉ người dùng mới đóng được', async () => {
    await invite();
    expect(await screen.findByText(/ma-moi-rat-bi-mat/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Tôi đã lưu liên kết này' }));
    await waitFor(() =>
      expect(screen.queryByText(/ma-moi-rat-bi-mat/)).not.toBeInTheDocument());
  });

  it('hiện nguyên văn liên kết máy chủ trả về, không tự ghép lại', async () => {
    /** Trang từng tự dựng liên kết từ `window.location.origin` + `/invitation`,
     * nghĩa là tên tuyến sống ở hai kho mã cùng lúc. Ghim vào `accept_url` để
     * một lần đổi tên tuyến ở máy chủ là đủ. */
    await invite();

    const link = (await screen.findByText(/ma-moi-rat-bi-mat/)).textContent ?? '';
    expect(link).toBe(ACCEPT_URL);
    // Fragment không được trình duyệt gửi lên máy chủ. Trượt về `?token=…` là
    // mọi mã mời đọng lại trong nhật ký truy cập của nginx và trong `Referer`.
    expect(link).not.toContain('?token=');
  });

  it('nói THẬT về việc thư đã gửi được hay chưa', async () => {
    /** Chưa cấu hình SMTP là trạng thái bình thường của bản chạy cục bộ. Nói
     * "đã gửi" khi không gửi được là để người được mời ngồi đợi một lá thư
     * không tồn tại, còn quản trị viên thì không biết mình phải gửi tay. */
    await invite({ email_sent: false });
    expect(await screen.findByText(/chưa gửi được thư/i)).toBeInTheDocument();
  });

  it('gửi được thì nói đã gửi', async () => {
    await invite({ email_sent: true });
    expect(await screen.findByText(/Đã gửi thư mời tới moi@truongb.vn/))
      .toBeInTheDocument();
  });

  it('vai hiện bằng tiếng Việt, không phải mã nội bộ', async () => {
    (fetchInvitations as any).mockResolvedValue([{
      invitation_id: 'i-2', tenant_id: 'truong-b', email: 'cho@truongb.vn',
      role: 'admin', created_at: '2026-08-08T00:00:00Z', expires_at: null,
      accepted_at: null, revoked_at: null,
    }]);
    render(<AdminTenantsPage />);
    await openTenant();

    // Tìm trong đúng dòng lời mời: chuỗi "Quản trị viên" cũng nằm trong các ô
    // chọn vai, nên một phép tìm toàn trang sẽ đúng ngay cả khi dòng này vẫn
    // in ra "admin".
    const row = (await screen.findByText('cho@truongb.vn')).parentElement!;
    expect(row).toHaveTextContent('Quản trị viên');
    expect(row).not.toHaveTextContent(/\badmin\b/);
  });
});
