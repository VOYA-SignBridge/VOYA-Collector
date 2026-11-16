import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import PasswordInput from '../PasswordInput';

/**
 * Mỗi ô mật khẩu có con mắt RIÊNG. Bản trước dùng một trạng thái chung cho
 * "Mật khẩu" và "Xác nhận mật khẩu": bấm ở ô này làm lộ luôn ô kia.
 */
const pair = () =>
  render(
    <>
      <PasswordInput label="Mật khẩu" defaultValue="a" />
      <PasswordInput label="Xác nhận mật khẩu" defaultValue="a" />
    </>,
  );

describe('PasswordInput', () => {
  it('mặc định che ký tự và có nút con mắt cho từng ô', () => {
    pair();
    expect(screen.getByLabelText('Mật khẩu')).toHaveAttribute('type', 'password');
    expect(screen.getByLabelText('Xác nhận mật khẩu')).toHaveAttribute('type', 'password');
    expect(screen.getAllByRole('button', { name: 'Hiện mật khẩu' })).toHaveLength(2);
  });

  it('bấm con mắt của ô nào thì chỉ ô đó lộ ra', () => {
    pair();
    fireEvent.click(screen.getAllByRole('button', { name: 'Hiện mật khẩu' })[0]);

    expect(screen.getByLabelText('Mật khẩu')).toHaveAttribute('type', 'text');
    expect(screen.getByLabelText('Xác nhận mật khẩu')).toHaveAttribute('type', 'password');
  });

  it('bấm lần nữa thì che lại, và nút báo trạng thái cho trình đọc màn hình', () => {
    pair();
    fireEvent.click(screen.getAllByRole('button', { name: 'Hiện mật khẩu' })[0]);
    const hide = screen.getByRole('button', { name: 'Ẩn mật khẩu' });
    expect(hide).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(hide);
    expect(screen.getByLabelText('Mật khẩu')).toHaveAttribute('type', 'password');
  });
});
