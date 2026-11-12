import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';

/**
 * Trang Người dùng của quản trị viên.
 *
 * Hai thứ mà một lỗi ở đây gây hại thật:
 *  - nút hỗ trợ gửi sai hành động (gỡ 2FA thay vì gửi liên kết) mà không ai
 *    thấy, vì cả hai chỉ khác một chuỗi trong thân yêu cầu;
 *  - bị từ chối vì thiếu nâng quyền (sudo) mà trang báo "thất bại" thay vì hỏi
 *    mật khẩu rồi thử lại đúng một lần.
 */

const get = vi.fn();
const post = vi.fn();
vi.mock('../../api/axiosClient', () => ({
  default: { get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a), put: vi.fn() },
}));
vi.mock('../../api/auth', () => ({ me: () => Promise.resolve({ id: 'me', username: 'boss' }) }));
const toast = { success: vi.fn(), error: vi.fn() };
vi.mock('../../hooks/useToast', () => ({ useToast: () => ({ toast }) }));
const ensureSudo = vi.fn();
vi.mock('../../hooks/useSudo', async () => {
  const actual = await vi.importActual<typeof import('../../hooks/useSudo')>('../../hooks/useSudo');
  return { ...actual, useSudo: () => ({ ensureSudo, sudoError: () => '' }) };
});

import AdminUsersPage from '../AdminUsersPage';

const USERS = [
  { id: 'me', username: 'boss', email: 'boss@x.vn', is_active: true, is_admin: true, created_at: '' },
  { id: 'u1', username: 'KinhKha', email: 'kk@cantho.edu.vn', is_active: true, is_admin: false, created_at: '' },
  { id: 'u2', username: 'Locked', email: 'l@x.vn', is_active: true, is_admin: false, created_at: '', locked: true },
];

async function openSupport() {
  render(<AdminUsersPage />);
  await screen.findByText('KinhKha');
  fireEvent.click(screen.getAllByRole('button', { name: /Hỗ trợ/ })[0]);
}

describe('AdminUsersPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    get.mockResolvedValue({ data: USERS });
    post.mockResolvedValue({ data: { status: 'ok' } });
  });

  it('lọc theo ô tìm kiếm và theo nhóm', async () => {
    render(<AdminUsersPage />);
    await screen.findByText('KinhKha');
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'kinh' } });
    expect(screen.queryByText('Locked')).not.toBeInTheDocument();
    expect(screen.getByText('KinhKha')).toBeInTheDocument();
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: /Bị khoá/ }));
    expect(screen.queryByText('KinhKha')).not.toBeInTheDocument();
    expect(screen.getByText('Locked')).toBeInTheDocument();
  });

  it('không có nút hỗ trợ cho chính mình', async () => {
    render(<AdminUsersPage />);
    await screen.findByText('KinhKha');
    // 3 tài khoản, 2 người khác mình
    expect(screen.getAllByRole('button', { name: /^Hỗ trợ$/ })).toHaveLength(2);
  });

  it('gửi liên kết đặt lại mật khẩu kèm lý do', async () => {
    post.mockResolvedValue({ data: { reset_link: 'x', email_sent: true } });
    await openSupport();
    const ok = screen.getByRole('button', { name: 'Xác nhận' });
    expect(ok).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Lý do'), { target: { value: 'Chủ nhờ qua tin nhắn' } });
    fireEvent.click(ok);
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(post).toHaveBeenCalledWith('/api/v1/admin/users/u1/recovery', {
      action: 'reset_link',
      reason: 'Chủ nhờ qua tin nhắn',
    });
    await waitFor(() => expect(toast.success).toHaveBeenCalled());
  });

  it('hiện liên kết để sao chép, không chỉ tin rằng thư đã tới', async () => {
    post.mockResolvedValue({ data: { reset_link: 'https://web.vn/reset-password?token=abc', email_sent: true, expires_minutes: 30 } });
    await openSupport();
    fireEvent.change(screen.getByLabelText('Lý do'), { target: { value: 'Chủ nhờ qua tin nhắn' } });
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận' }));
    const box = await screen.findByLabelText('Liên kết đặt lại mật khẩu');
    expect(box).toHaveValue('https://web.vn/reset-password?token=abc');
    expect(screen.getByRole('button', { name: 'Sao chép' })).toBeInTheDocument();
    expect(screen.getByText(/hết hạn sau 30 phút/)).toBeInTheDocument();
  });

  it('tài khoản không có email: vẫn có liên kết, nói rõ thư không đi', async () => {
    post.mockResolvedValue({ data: { reset_link: 'https://web.vn/reset-password?token=abc', email_sent: false, expires_minutes: 30 } });
    await openSupport();
    fireEvent.change(screen.getByLabelText('Lý do'), { target: { value: 'Chủ nhờ qua tin nhắn' } });
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận' }));
    await screen.findByLabelText('Liên kết đặt lại mật khẩu');
    expect(screen.getByText(/không có email nên không gửi thư được/)).toBeInTheDocument();
    expect(toast.success).not.toHaveBeenCalled();
  });

  it('gỡ xác thực hai bước gửi đúng hành động', async () => {
    await openSupport();
    fireEvent.click(screen.getByRole('radio', { name: /Gỡ xác thực hai bước/ }));
    fireEvent.change(screen.getByLabelText('Lý do'), { target: { value: 'Mất điện thoại' } });
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận' }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1]).toEqual({ action: 'clear_2fa', reason: 'Mất điện thoại' });
  });

  it('hỏi mật khẩu rồi thử lại đúng một lần khi bị đòi nâng quyền', async () => {
    post.mockRejectedValueOnce({ response: { data: { code: 'sudo_required' } } }).mockResolvedValueOnce({ data: { reset_link: 'x', email_sent: true } });
    ensureSudo.mockResolvedValue(true);
    await openSupport();
    fireEvent.change(screen.getByLabelText('Lý do'), { target: { value: 'Chủ nhờ qua tin nhắn' } });
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận' }));
    await waitFor(() => expect(post).toHaveBeenCalledTimes(2));
    expect(ensureSudo).toHaveBeenCalledTimes(1);
    expect(toast.success).toHaveBeenCalled();
  });

  it('huỷ nhập mật khẩu thì không gửi lại và báo đã huỷ', async () => {
    post.mockRejectedValueOnce({ response: { data: { code: 'sudo_required' } } });
    ensureSudo.mockResolvedValue(false);
    await openSupport();
    fireEvent.change(screen.getByLabelText('Lý do'), { target: { value: 'Chủ nhờ qua tin nhắn' } });
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận' }));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(post).toHaveBeenCalledTimes(1);
    expect(toast.success).not.toHaveBeenCalled();
  });
});
