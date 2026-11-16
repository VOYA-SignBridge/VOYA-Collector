import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, beforeEach, vi } from 'vitest';

/**
 * Đăng nhập với "Ghi nhớ đăng nhập trên thiết bị này".
 *
 * Canh ba thứ mà lỗi ở đây gây hại thật: lựa chọn có tới máy chủ không (và KHÔNG
 * tới khi người dùng chưa xác nhận), có đi tiếp qua bước hai không, và tên đăng
 * nhập chỉ được nhớ khi người dùng đã chọn nhớ.
 */
const login = vi.fn();
const loginTwoFactor = vi.fn();
vi.mock('../../api/auth', () => ({
  login: (...a: unknown[]) => login(...a),
  loginTwoFactor: (...a: unknown[]) => loginTwoFactor(...a),
}));
vi.mock('../../api/axiosClient', () => ({ notifyAuthChange: vi.fn() }));
vi.mock('../UploadPage', () => ({ default: () => null }));

import LoginPage from '../LoginPage';

const KEY = 'voya:remembered-login';
const view = () =>
  render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );

const fill = (identifier = 'kha', password = 'mat-khau-dai') => {
  fireEvent.change(screen.getByLabelText('Tên đăng nhập hoặc email'), { target: { value: identifier } });
  fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: password } });
};
const tickAndConfirm = () => {
  fireEvent.click(screen.getByLabelText('Ghi nhớ đăng nhập trên thiết bị này'));
  fireEvent.click(screen.getByRole('button', { name: 'Đây là thiết bị của tôi' }));
};
const submit = () => fireEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }));

describe('LoginPage — ghi nhớ đăng nhập', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    login.mockResolvedValue({ kind: 'session', user: { id: 'u1' } });
  });

  it('mặc định KHÔNG ghi nhớ', async () => {
    view();
    fill();
    submit();
    await waitFor(() => expect(login).toHaveBeenCalled());
    expect(login).toHaveBeenCalledWith({ identifier: 'kha', password: 'mat-khau-dai', remember: false });
  });

  it('đã tick và xác nhận thì gửi remember: true và nhớ tên đăng nhập', async () => {
    view();
    fill();
    tickAndConfirm();
    submit();
    await waitFor(() => expect(login).toHaveBeenCalled());
    expect(login).toHaveBeenCalledWith({ identifier: 'kha', password: 'mat-khau-dai', remember: true });
    await waitFor(() => expect(localStorage.getItem(KEY)).toBe('kha'));
  });

  it('không tick thì quên tên đã nhớ từ lần trước', async () => {
    localStorage.setItem(KEY, 'cu');
    view();
    fill('moi');
    submit();
    await waitFor(() => expect(login).toHaveBeenCalled());
    await waitFor(() => expect(localStorage.getItem(KEY)).toBeNull());
  });

  it('điền sẵn tên đăng nhập đã nhớ, nhưng KHÔNG tự tick ghi nhớ', () => {
    localStorage.setItem(KEY, 'kha');
    view();
    expect(screen.getByLabelText('Tên đăng nhập hoặc email')).toHaveValue('kha');
    expect(screen.getByLabelText('Ghi nhớ đăng nhập trên thiết bị này')).not.toBeChecked();
  });

  it('tài khoản có 2FA: lựa chọn đi tiếp sang bước hai', async () => {
    login.mockResolvedValue({ kind: 'two_factor', challenge: 've-buoc-hai' });
    loginTwoFactor.mockResolvedValue({ id: 'u1' });
    view();
    fill();
    tickAndConfirm();
    submit();

    fireEvent.change(await screen.findByLabelText('Mã xác thực'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận' }));

    await waitFor(() => expect(loginTwoFactor).toHaveBeenCalledWith('ve-buoc-hai', '123456', true));
  });
});
