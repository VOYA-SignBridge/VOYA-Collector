import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, beforeEach, vi } from 'vitest';

/**
 * Trang "Tài khoản của tôi" — hồ sơ: ảnh đại diện, tên đăng nhập (chỉ đọc) và email.
 *
 * Phần đồng thuận pháp lý đã chuyển sang `/settings/consents` ngày 16/08/2026;
 * bài kiểm của nó nằm ở `pages/settings/__tests__/ConsentsPage.test.tsx`.
 *
 * Hai chỗ mà một trang "trông đúng" vẫn nói dối, và là lý do các khẳng định
 * dưới đây tồn tại:
 *
 *  1. Chọn ảnh đại diện xong mà đầu trang vẫn giữ ảnh cũ — người dùng kết luận
 *     rằng lượt chọn thất bại, rồi chọn lại. Và tên đăng nhập KHÔNG được có ô sửa.
 *  2. Đổi email chỉ bằng một phiên đang mở. Email là khoá khôi phục tài khoản,
 *     nên nếu một cửa sổ bỏ quên đủ để trỏ nó sang hộp thư khác thì mất tài
 *     khoản là chuyện một lần bấm. Mật khẩu phải được hỏi ở CẢ HAI bước, và mã
 *     phải đi tới địa chỉ MỚI.
 */

vi.mock('../../api/auth', () => ({
  setAvatar: vi.fn(),
  uploadAvatar: vi.fn(),
  AVATAR_MAX_BYTES: 2 * 1024 * 1024,
  uploadedAvatarUrl: (id: string, key: string) => `/api/v1/auth/avatar/${id}?v=${key}`,
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
import { confirmEmailChange, setAvatar, startEmailChange, uploadAvatar } from '../../api/auth';
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
  vi.mocked(setAvatar).mockResolvedValue(undefined);
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

describe('Hồ sơ: tên đăng nhập chỉ đọc, ảnh đại diện chọn từ bộ mẫu', () => {
  it('tên đăng nhập chỉ hiện ra, KHÔNG có ô nào để sửa nó', async () => {
    renderPage();
    expect(await screen.findByRole('heading', { name: 'nguoidung' })).toBeInTheDocument();
    expect(screen.queryByDisplayValue('nguoidung')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Lưu tên mới' })).not.toBeInTheDocument();
    expect(screen.getByText(/Tên đăng nhập không đổi được/)).toBeInTheDocument();
  });

  it('chọn một mẫu thì lưu ngay và báo cho AuthProvider để đầu trang đổi theo', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('radio', { name: 'Ảnh đại diện 2' }));

    await waitFor(() => expect(setAvatar).toHaveBeenCalledWith('heart'));
    expect(notifyAuthChange).toHaveBeenCalled();
    expect(toast.success).toHaveBeenCalled();
  });

  it('chưa chọn mẫu nào thì không có nút nào đang được chọn, và nút "chữ cái đầu" khoá', async () => {
    renderPage();
    await screen.findByRole('radiogroup', { name: 'Chọn ảnh đại diện' });
    for (const r of screen.getAllByRole('radio')) expect(r).toHaveAttribute('aria-checked', 'false');
    expect(screen.getByRole('button', { name: 'Dùng chữ cái đầu của tên' })).toBeDisabled();
  });

  it('tải ảnh lên: gửi đúng tệp rồi báo cho AuthProvider để đầu trang đổi theo', async () => {
    vi.mocked(uploadAvatar).mockResolvedValue('u-1700000000');
    renderPage();
    const file = new File(['x'], 'toi.png', { type: 'image/png' });
    fireEvent.change(await screen.findByLabelText('Chọn ảnh từ máy'), { target: { files: [file] } });

    await waitFor(() => expect(uploadAvatar).toHaveBeenCalledWith(file));
    expect(notifyAuthChange).toHaveBeenCalled();
    expect(toast.success).toHaveBeenCalled();
  });

  it('ảnh quá 2 MB bị chặn ngay ở trình duyệt, không gửi lên', async () => {
    renderPage();
    const big = new File([new Uint8Array(2 * 1024 * 1024 + 1)], 'lon.png', { type: 'image/png' });
    fireEvent.change(await screen.findByLabelText('Chọn ảnh từ máy'), { target: { files: [big] } });

    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(uploadAvatar).not.toHaveBeenCalled();
  });

  it('máy chủ từ chối ảnh thì báo lỗi và KHÔNG phát sự kiện đổi hồ sơ', async () => {
    vi.mocked(uploadAvatar).mockRejectedValue(new Error('415'));
    renderPage();
    const file = new File(['x'], 'toi.gif', { type: 'image/gif' });
    fireEvent.change(await screen.findByLabelText('Chọn ảnh từ máy'), { target: { files: [file] } });

    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(notifyAuthChange).not.toHaveBeenCalled();
  });

  it('lưu thất bại thì báo lỗi và KHÔNG phát sự kiện đổi hồ sơ', async () => {
    vi.mocked(setAvatar).mockRejectedValue(new Error('boom'));
    renderPage();
    fireEvent.click(await screen.findByRole('radio', { name: 'Ảnh đại diện 1' }));

    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(notifyAuthChange).not.toHaveBeenCalled();
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
    await screen.findByRole('heading', { name: 'nguoidung' });
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
