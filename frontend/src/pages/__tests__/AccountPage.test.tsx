import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, beforeEach, vi } from 'vitest';

/**
 * Trang "Tài khoản của tôi" — hồ sơ: tên đăng nhập và email.
 *
 * Phần đồng thuận pháp lý đã chuyển sang `/settings/consents` ngày 16/08/2026;
 * bài kiểm của nó nằm ở `pages/settings/__tests__/ConsentsPage.test.tsx`.
 *
 * Hai chỗ mà một trang "trông đúng" vẫn nói dối, và là lý do các khẳng định
 * dưới đây tồn tại:
 *
 *  1. Đổi tên xong mà thanh bên vẫn giữ tên cũ — người dùng kết luận rằng việc
 *     đổi thất bại, rồi đổi lại lần nữa.
 *  2. Đổi email chỉ bằng một phiên đang mở. Email là khoá khôi phục tài khoản,
 *     nên nếu một cửa sổ bỏ quên đủ để trỏ nó sang hộp thư khác thì mất tài
 *     khoản là chuyện một lần bấm. Mật khẩu phải được hỏi ở CẢ HAI bước, và mã
 *     phải đi tới địa chỉ MỚI.
 */

vi.mock('../../api/auth', () => ({
  updateUsername: vi.fn(),
  startEmailChange: vi.fn(),
  confirmEmailChange: vi.fn(),
}));

vi.mock('../../api/verification', () => ({
  fetchVerificationStatus: vi.fn(),
}));

vi.mock('../../api/axiosClient', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
  notifyAuthChange: vi.fn(),
}));

const toast = { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() };
vi.mock('../../hooks/useToast', () => ({ useToast: () => ({ toast }) }));

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'u1', username: 'nguoidung', email: 'a@b.test' },
    loading: false,
    isAuthenticated: true,
    isAdmin: false,
  }),
}));

import AccountPage from '../AccountPage';
import { confirmEmailChange, startEmailChange, updateUsername } from '../../api/auth';
import { fetchVerificationStatus } from '../../api/verification';
import { notifyAuthChange } from '../../api/axiosClient';

function renderPage() {
  return render(
    <MemoryRouter>
      <AccountPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(updateUsername).mockResolvedValue({
    changed: true,
    old_username: 'nguoidung',
    new_username: 'tenmoi',
    rows: { 'samples.username': 12 },
  });
  vi.mocked(fetchVerificationStatus).mockResolvedValue({
    email: 'a@b.test',
    email_verified: true,
    phone_number: '',
    phone_verified: false,
    resend_cooldown_seconds: 60,
    code_ttl_minutes: 10,
    sms_available: false,
  });
});

describe('Đổi tên đăng nhập', () => {
  it('khoá nút khi tên chưa đổi', async () => {
    renderPage();
    const button = await screen.findByRole('button', { name: 'Lưu tên mới' });
    expect(button).toBeDisabled();

    fireEvent.change(screen.getByDisplayValue('nguoidung'), {
      target: { value: 'tenmoi' },
    });
    expect(button).toBeEnabled();
  });

  it('báo cho AuthProvider biết để thanh bên không giữ tên cũ', async () => {
    // Không phát sự kiện thì người dùng thấy tên cũ cho tới lần tải trang sau,
    // và kết luận rằng việc đổi tên thất bại.
    renderPage();
    await screen.findByRole('button', { name: 'Lưu tên mới' });

    fireEvent.change(screen.getByDisplayValue('nguoidung'), {
      target: { value: 'tenmoi' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Lưu tên mới' }));

    await waitFor(() => expect(updateUsername).toHaveBeenCalledWith('tenmoi'));
    expect(notifyAuthChange).toHaveBeenCalled();
  });

  it('hiện số hàng dữ liệu đã đổi theo', async () => {
    // Đổi tên KHÔNG phải một câu `UPDATE users`: nó chạm vào các mẫu đã đóng
    // góp. Người bấm nút xứng đáng thấy điều đó thay vì tin lời.
    renderPage();
    await screen.findByRole('button', { name: 'Lưu tên mới' });

    fireEvent.change(screen.getByDisplayValue('nguoidung'), {
      target: { value: 'tenmoi' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Lưu tên mới' }));

    expect(await screen.findByText('samples.username: 12')).toBeInTheDocument();
  });

  it('không khoe gì khi tên mới trùng tên cũ', async () => {
    vi.mocked(updateUsername).mockResolvedValue({
      changed: false,
      old_username: 'nguoidung',
      new_username: 'nguoidung',
      rows: {},
    });
    renderPage();
    await screen.findByRole('button', { name: 'Lưu tên mới' });

    fireEvent.change(screen.getByDisplayValue('nguoidung'), {
      target: { value: '  nguoidung  ' },
    });
    // Khoảng trắng thừa không phải một cái tên mới — nút phải vẫn khoá.
    expect(screen.getByRole('button', { name: 'Lưu tên mới' })).toBeDisabled();
  });
});

describe('Đổi email', () => {
  it('mã đi tới ĐỊA CHỈ MỚI, và mật khẩu được hỏi ngay bước đầu', async () => {
    vi.mocked(startEmailChange).mockResolvedValue({
      challenge_id: 'c1',
      sent_to: 'moi@b.test',
      expires_in_minutes: 10,
    });
    renderPage();

    const send = await screen.findByRole('button', { name: 'Gửi mã tới địa chỉ mới' });
    // Chưa nhập gì thì không gửi được — nếu không, một ô trống sẽ nổ ở máy chủ.
    expect(send).toBeDisabled();

    fireEvent.change(screen.getByLabelText('Địa chỉ email mới'), {
      target: { value: 'moi@b.test' },
    });
    fireEvent.change(screen.getByLabelText('Mật khẩu hiện tại'), {
      target: { value: 'mat khau cu' },
    });
    fireEvent.click(send);

    await waitFor(() =>
      expect(startEmailChange).toHaveBeenCalledWith({
        currentPassword: 'mat khau cu',
        newEmail: 'moi@b.test',
      }),
    );
  });

  it('địa chỉ không hợp lệ thì nút vẫn khoá', async () => {
    renderPage();
    const send = await screen.findByRole('button', { name: 'Gửi mã tới địa chỉ mới' });

    fireEvent.change(screen.getByLabelText('Địa chỉ email mới'), {
      target: { value: 'khong-phai-email' },
    });
    fireEvent.change(screen.getByLabelText('Mật khẩu hiện tại'), {
      target: { value: 'mat khau cu' },
    });
    expect(send).toBeDisabled();
  });

  it('xác nhận xong thì báo cho AuthProvider', async () => {
    // Header đang giữ địa chỉ cũ. Không phát sự kiện thì người dùng thấy địa chỉ
    // cũ cho tới lần tải trang sau và tưởng việc đổi hỏng — cùng cái bẫy với
    // đổi tên đăng nhập.
    vi.mocked(startEmailChange).mockResolvedValue({
      challenge_id: 'c1',
      sent_to: 'moi@b.test',
      expires_in_minutes: 10,
    });
    vi.mocked(confirmEmailChange).mockResolvedValue({
      email: 'moi@b.test',
      email_verified: true,
    });
    renderPage();

    fireEvent.change(
      await screen.findByLabelText('Địa chỉ email mới'),
      { target: { value: 'moi@b.test' } },
    );
    fireEvent.change(screen.getByLabelText('Mật khẩu hiện tại'), {
      target: { value: 'mat khau cu' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Gửi mã tới địa chỉ mới' }));

    fireEvent.change(await screen.findByLabelText('Mã 6 chữ số vừa gửi'), {
      target: { value: '123456' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận đổi email' }));

    await waitFor(() => expect(confirmEmailChange).toHaveBeenCalled());
    expect(notifyAuthChange).toHaveBeenCalled();
  });
});

describe('Nhắc xác minh', () => {
  it('không chiếm chỗ khi mọi thứ đã xác minh', async () => {
    // Một tấm thẻ xanh ghi "tất cả đã xác minh" chiếm chỗ vĩnh viễn ở đầu trang
    // để nói một điều không đòi hỏi hành động nào.
    renderPage();
    await screen.findByRole('button', { name: 'Lưu tên mới' });
    expect(screen.queryByRole('link', { name: 'Xác minh ngay' })).not.toBeInTheDocument();
  });

  it('chỉ đường sang trang Bảo mật khi còn thứ chưa xác minh', async () => {
    vi.mocked(fetchVerificationStatus).mockResolvedValue({
      email: 'a@b.test',
      email_verified: false,
      phone_number: '',
      phone_verified: false,
      resend_cooldown_seconds: 60,
      code_ttl_minutes: 10,
      sms_available: false,
    });
    renderPage();

    expect(await screen.findByRole('link', { name: 'Xác minh ngay' })).toHaveAttribute(
      'href',
      '/settings/security',
    );
  });
});
