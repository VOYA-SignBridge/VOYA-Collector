import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, beforeEach, vi } from 'vitest';

/**
 * Trang "Tổ chức của tôi".
 *
 * 19 endpoint đã chạy từ v4 và mặt giao diện duy nhất đứng trên chúng gác sau
 * `requireAdmin` — tức quản trị viên NỀN TẢNG. Chủ một tổ chức không có màn hình
 * nào. Trang này là mặt còn lại, và các khẳng định dưới đây canh những chỗ mà
 * một trang quản trị "trông đúng" vẫn làm người dùng lạc:
 *
 *   * ngõ cụt không giải thích (403, chưa có tổ chức)
 *   * nói đã gửi thư trong khi SMTP hỏng
 *   * mời bấm một nút chắc chắn không hoạt động
 *   * doạ mất dữ liệu ở chỗ dữ liệu không mất
 */

vi.mock('../../api/tenants', async () => {
  const actual = await vi.importActual<typeof import('../../api/tenants')>('../../api/tenants');
  return {
    ...actual,
    fetchTenant: vi.fn(),
    fetchMyTenant: vi.fn(),
    fetchMembers: vi.fn(),
    fetchInvitations: vi.fn(),
    fetchExports: vi.fn(),
    fetchSubscription: vi.fn(),
    setAutoRenew: vi.fn(),
    createInvitation: vi.fn(),
    revokeInvitation: vi.fn(),
    updateMemberRole: vi.fn(),
    removeMember: vi.fn(),
    requestExport: vi.fn(),
  };
});

const toast = { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() };
vi.mock('../../hooks/useToast', () => ({ useToast: () => ({ toast }) }));

let mockUser: Record<string, unknown> | null = {
  id: 'u1', username: 'chutochuc', email: 'a@b.test', tenant_id: 'ctu',
};
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: mockUser,
    loading: false,
    isAuthenticated: !!mockUser,
    isAdmin: false,
  }),
}));

import OrganizationPage from '../OrganizationPage';
import {
  createInvitation,
  fetchExports,
  fetchInvitations,
  fetchMembers,
  fetchMyTenant,
  fetchSubscription,
  fetchTenant,
  removeMember,
  requestExport,
  setAutoRenew,
  type SubscriptionInfo,
  type Tenant,
  type TenantExport,
  type TenantMember,
} from '../../api/tenants';

const tenant: Tenant = {
  tenant_id: 'ctu',
  display_name: 'Đại học Cần Thơ',
  slug: 'ctu',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  created_by: null,
  deleted_at: null,
  member_count: 2,
};

function member(over: Partial<TenantMember> = {}): TenantMember {
  return {
    tenant_id: 'ctu',
    user_id: 'u2',
    username: 'thanhvien',
    email: 'tv@ctu.edu.vn',
    role: null,
    is_active: true,
    created_at: '2026-02-02T00:00:00Z',
    ...over,
  };
}

function exportRow(over: Partial<TenantExport> = {}): TenantExport {
  return {
    export_id: 'e1',
    tenant_id: 'ctu',
    status: 'ready',
    scope: 'full',
    size_bytes: 2097152,
    row_counts: null,
    error: null,
    created_at: '2026-08-01T00:00:00Z',
    completed_at: '2026-08-01T01:00:00Z',
    expires_at: null,
    ...over,
  };
}

function subscription(over: Partial<SubscriptionInfo> = {}): SubscriptionInfo {
  return {
    has_subscription: true,
    plan_code: 'school',
    billing_status: 'active',
    auto_renew: true,
    current_period_end: '2026-12-31T00:00:00Z',
    grace_until: null,
    days_left: 42,
    read_only: false,
    ...over,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <OrganizationPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockUser = { id: 'u1', username: 'chutochuc', email: 'a@b.test', tenant_id: 'ctu' };
  vi.mocked(fetchTenant).mockResolvedValue(tenant);
  vi.mocked(fetchMembers).mockResolvedValue([
    member({ user_id: 'u1', username: 'chutochuc', role: 'admin' }),
    member(),
  ]);
  vi.mocked(fetchInvitations).mockResolvedValue([]);
  vi.mocked(fetchExports).mockResolvedValue([]);
  // Cửa dành cho THÀNH VIÊN. Chỉ được gọi khi lượt gác cổng trả 403.
  vi.mocked(fetchMyTenant).mockResolvedValue({
    tenant_id: 'ctu',
    display_name: 'VOYA',
    created_at: null,
    plan_code: 'free',
    member_count: 2,
    admin_count: 1,
    my_role: 'editor',
    is_self_serve: false,
    members: [
      { username: 'chutochuc', role: 'admin', is_me: false },
      { username: 'le', role: 'editor', is_me: true },
    ],
  });
  vi.mocked(fetchSubscription).mockResolvedValue(subscription());
});

describe('Gói dịch vụ', () => {
  it('gói vĩnh viễn KHÔNG hiện "còn 0 ngày"', async () => {
    vi.mocked(fetchSubscription).mockResolvedValue(
      subscription({ days_left: null, current_period_end: null }),
    );
    renderPage();

    expect(await screen.findByText(/Gói không có kỳ hạn/)).toBeInTheDocument();
    expect(screen.queryByText(/Còn/)).not.toBeInTheDocument();
  });

  it('chỉ-đọc nói rõ dữ liệu VẪN CÒN, không chỉ nói cái mất', async () => {
    // Một cảnh báo đỏ chỉ liệt kê cái mất làm người đọc tưởng dữ liệu đã bay.
    vi.mocked(fetchSubscription).mockResolvedValue(
      subscription({ billing_status: 'suspended', read_only: true, auto_renew: false }),
    );
    renderPage();

    expect(await screen.findByText(/vẫn còn nguyên/)).toBeInTheDocument();
    expect(screen.getByText(/vẫn tải về được/)).toBeInTheDocument();
  });

  it('ân hạn nói rõ VẪN ghi được', async () => {
    // `past_due` nằm trong WRITABLE_BILLING_STATUSES — có chủ ý.
    vi.mocked(fetchSubscription).mockResolvedValue(
      subscription({ billing_status: 'past_due', read_only: false, days_left: 0,
                     grace_until: '2026-08-20T00:00:00Z' }),
    );
    renderPage();

    expect(await screen.findByText(/vẫn ghi được/)).toBeInTheDocument();
  });

  it('tắt tự gia hạn phải qua xác nhận, và xác nhận nói kỳ này vẫn chạy hết', async () => {
    // Thiếu câu đó, người dùng tưởng vừa tự khoá tổ chức của mình.
    vi.mocked(setAutoRenew).mockResolvedValue(subscription({ auto_renew: false }));
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Tắt tự gia hạn' }));
    expect(setAutoRenew).not.toHaveBeenCalled();
    expect(screen.getByText(/vẫn chạy hết/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận tắt' }));
    await waitFor(() => expect(setAutoRenew).toHaveBeenCalledWith('ctu', false));
  });

  it('mất khối đăng ký không kéo theo cả trang', async () => {
    vi.mocked(fetchSubscription).mockRejectedValue(new Error('500'));
    renderPage();

    // Thành viên vẫn dựng được.
    expect(await screen.findByText('thanhvien')).toBeInTheDocument();
    expect(screen.getByText(/chưa có đăng ký nào/i)).toBeInTheDocument();
  });
});

describe('Ngõ cụt phải có lối ra', () => {
  it('403 trả lời đúng câu người dùng hỏi: TÔI ĐANG Ở TỔ CHỨC NÀO', async () => {
    // Một thành viên thường nhận 403 từ `require_tenant_admin`. Trước 20/08 chỗ
    // này chỉ hiện một câu từ chối — mà "bạn không phải quản trị viên" là câu
    // trả lời cho một câu hỏi KHÁC HẲN câu người ta vào đây để hỏi.
    //
    // Giờ 403 kích hoạt lượt hỏi thứ hai qua cửa dành cho thành viên
    // (`GET /tenants/me`), và trang hiện tổ chức + vai + danh sách đồng nghiệp.
    vi.mocked(fetchTenant).mockRejectedValue({ response: { status: 403 } });
    renderPage();

    // Thông tin tổ chức, không phải lời từ chối.
    expect(await screen.findByText('VOYA')).toBeInTheDocument();
    // Vẫn trấn an đúng chỗ: họ KHÔNG mất tính năng nào khác.
    expect(screen.getByText(/vẫn dùng được mọi tính năng đóng góp dữ liệu/i)).toBeInTheDocument();
  });

  it('tài khoản chưa thuộc tổ chức nào được chỉ đường', async () => {
    mockUser = { id: 'u1', username: 'le', email: 'a@b.test', tenant_id: null };
    renderPage();

    expect(await screen.findByText(/chưa thuộc tổ chức nào/i)).toBeInTheDocument();
    expect(fetchTenant).not.toHaveBeenCalled();
  });
});

describe('Lời mời', () => {
  it('KHÔNG nói đã gửi thư khi máy chủ báo gửi hỏng', async () => {
    // `email_sent: false` là chuyện bình thường khi chưa cấu hình SMTP. Lời mời
    // vẫn hợp lệ — gộp hai trường hợp lại là để người dùng ngồi chờ một lá thư
    // không bao giờ tới.
    vi.mocked(createInvitation).mockResolvedValue({
      invitation_id: 'i1', tenant_id: 'ctu', email: 'moi@ctu.edu.vn', role: null,
      created_at: '2026-08-10T00:00:00Z', expires_at: null,
      accepted_at: null, revoked_at: null,
      token: 'bimat', accept_url: 'https://x.test/voya/invitation#token=bimat',
      email_sent: false,
    });
    renderPage();

    fireEvent.change(await screen.findByPlaceholderText(/giangvien@ctu.edu.vn/), {
      target: { value: 'moi@ctu.edu.vn' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Gửi lời mời/ }));

    expect(await screen.findByText(/chưa gửi được thư/i)).toBeInTheDocument();
    // Và đưa đúng thứ cần để chữa: liên kết, do MÁY CHỦ dựng.
    expect(
      screen.getByText('https://x.test/voya/invitation#token=bimat'),
    ).toBeInTheDocument();
  });

  it('nhận CẢ email lẫn tên đăng nhập, chặn thứ chắc chắn vô nghĩa', async () => {
    // Đổi 20/08: ô mời không còn chỉ nhận email. Quản trị viên tổ chức thường
    // biết đồng nghiệp qua TÊN TÀI KHOẢN chứ không thuộc địa chỉ thư của họ, và
    // bắt họ đoán địa chỉ là cách chắc chắn để lời mời đi lạc. Máy chủ mới là
    // nơi phân giải tên thành tài khoản; chỗ này chỉ chặn ô trống và chuỗi quá
    // ngắn, để nút không bật lên cho thứ không thể là ai cả.
    renderPage();
    const button = await screen.findByRole('button', { name: /Gửi lời mời/ });
    const box = screen.getByPlaceholderText(/giangvien@ctu.edu.vn/);
    expect(button).toBeDisabled();

    fireEvent.change(box, { target: { value: 'ab' } });
    expect(button).toBeDisabled();

    fireEvent.change(box, { target: { value: 'minh123' } });
    expect(button).toBeEnabled();

    fireEvent.change(box, { target: { value: 'ok@ctu.edu.vn' } });
    expect(button).toBeEnabled();
  });
});

describe('Thành viên', () => {
  it('không cho tự đổi vai của chính mình', async () => {
    // Một tổ chức không còn quản trị viên nào là trạng thái không ai gỡ ra được
    // từ trong giao diện.
    renderPage();
    await screen.findByText('Đại học Cần Thơ');

    // Đúng một ô chọn vai: của thành viên kia, không phải của mình.
    const selects = screen.getAllByRole('combobox').filter((el) =>
      el.getAttribute('aria-label')?.startsWith('Vai của'),
    );
    expect(selects).toHaveLength(1);
    expect(selects[0]).toHaveAttribute('aria-label', 'Vai của thanhvien');
  });

  it('hộp xác nhận gỡ nói rõ dữ liệu KHÔNG mất', async () => {
    // Gỡ thành viên không xoá mẫu họ đã đóng góp. Doạ mất dữ liệu ở chỗ dữ liệu
    // không mất làm người quản trị không dám thao tác.
    renderPage();
    await screen.findByText('Đại học Cần Thơ');

    fireEvent.click(screen.getByRole('button', { name: 'Gỡ' }));

    expect(await screen.findByText(/vẫn ở lại/i)).toBeInTheDocument();
    expect(removeMember).not.toHaveBeenCalled();
  });
});

describe('Mang dữ liệu đi', () => {
  it('chỉ hiện nút Tải về khi bản xuất đã sẵn sàng', async () => {
    // Máy chủ trả 202 lúc nhận việc — một nút Tải về hiện sớm là nút chắc chắn hỏng.
    vi.mocked(fetchExports).mockResolvedValue([
      exportRow({ export_id: 'e1', status: 'ready' }),
      exportRow({ export_id: 'e2', status: 'running', size_bytes: null }),
      exportRow({ export_id: 'e3', status: 'failed', error: 'hết dung lượng', size_bytes: null }),
    ]);
    renderPage();

    const links = await screen.findAllByRole('link', { name: /Tải về/ });
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAttribute('href', '/api/v1/tenants/ctu/exports/e1/download');

    expect(screen.getByText(/Đang xử lý/)).toBeInTheDocument();
    expect(screen.getByText('hết dung lượng')).toBeInTheDocument();
  });

  it('nói đã nhận việc, không nói đã xong', async () => {
    vi.mocked(requestExport).mockResolvedValue(exportRow({ status: 'pending' }));
    renderPage();
    await screen.findByText('Đại học Cần Thơ');

    fireEvent.click(screen.getByRole('button', { name: /Xuất toàn bộ/ }));

    await waitFor(() => expect(requestExport).toHaveBeenCalledWith('ctu', 'full'));
    expect(toast.success).toHaveBeenCalledWith(expect.stringMatching(/Đã nhận yêu cầu/));
  });
});
