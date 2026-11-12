import '@testing-library/jest-dom/vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { askPassword } from '../askPassword';

/**
 * Hộp hỏi mật khẩu quản trị. Sự cố gốc (12/11/2026): `window.prompt` là ô chữ
 * thường, mật khẩu hiện rõ trên màn hình và lọt vào ảnh chụp.
 */
afterEach(() => {
  document.body.innerHTML = '';
});

function open(verify = vi.fn().mockResolvedValue(null)) {
  const result = askPassword({ title: 'Xác nhận lại mật khẩu', message: 'Hỗ trợ tài khoản cần xác thực lại.', verify });
  const input = screen.getByLabelText('Mật khẩu của bạn') as HTMLInputElement;
  return { result, input, verify };
}

describe('askPassword', () => {
  it('ô nhập che ký tự và được focus sẵn', () => {
    const { input } = open();
    expect(input).toHaveAttribute('type', 'password');
    expect(input).toHaveFocus();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('mật khẩu đúng: đóng hộp, trả true, không để lại gì trong DOM', async () => {
    const { result, input, verify } = open();
    fireEvent.change(input, { target: { value: 'bi-mat' } });
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận' }));
    await expect(result).resolves.toBe(true);
    expect(verify).toHaveBeenCalledWith('bi-mat');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('mật khẩu sai: báo ngay trong hộp, xoá ô, cho gõ lại', async () => {
    const verify = vi.fn().mockResolvedValueOnce('Sai mật khẩu').mockResolvedValueOnce(null);
    const { result, input } = open(verify);
    fireEvent.change(input, { target: { value: 'sai' } });
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận' }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Sai mật khẩu'));
    expect(input.value).toBe('');
    fireEvent.change(input, { target: { value: 'dung' } });
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận' }));
    await expect(result).resolves.toBe(true);
    expect(verify).toHaveBeenCalledTimes(2);
  });

  it('Huỷ hoặc Esc: trả false, không gọi máy chủ', async () => {
    const { result, verify } = open();
    fireEvent.keyDown(document, { key: 'Escape' });
    await expect(result).resolves.toBe(false);
    expect(verify).not.toHaveBeenCalled();

    const second = open();
    fireEvent.click(screen.getByRole('button', { name: 'Huỷ' }));
    await expect(second.result).resolves.toBe(false);
  });
});
