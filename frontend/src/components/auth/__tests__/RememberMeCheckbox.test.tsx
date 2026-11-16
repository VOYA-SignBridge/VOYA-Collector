import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import RememberMeCheckbox from '../RememberMeCheckbox';

/**
 * Tick "Ghi nhớ" phải HỎI trước: máy ở trường, quán net là chuyện thường, và giữ
 * đăng nhập nhiều ngày trên máy dùng chung là đưa tài khoản cho người dùng sau.
 */
const BOX = 'Ghi nhớ đăng nhập trên thiết bị này';
const WARNING = /đừng chọn trên máy dùng chung/;

describe('RememberMeCheckbox', () => {
  it('tick thì hỏi, chưa bật cho tới khi người dùng xác nhận', () => {
    const onChange = vi.fn();
    render(<RememberMeCheckbox checked={false} onChange={onChange} />);

    fireEvent.click(screen.getByLabelText(BOX));

    expect(screen.getByText(WARNING)).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });

  it('xác nhận "Đây là thiết bị của tôi" thì mới bật', () => {
    const onChange = vi.fn();
    render(<RememberMeCheckbox checked={false} onChange={onChange} />);

    fireEvent.click(screen.getByLabelText(BOX));
    fireEvent.click(screen.getByRole('button', { name: 'Đây là thiết bị của tôi' }));

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith(true);
    expect(screen.queryByText(WARNING)).not.toBeInTheDocument();
  });

  it('chọn "Không ghi nhớ" thì không bật gì', () => {
    const onChange = vi.fn();
    render(<RememberMeCheckbox checked={false} onChange={onChange} />);

    fireEvent.click(screen.getByLabelText(BOX));
    fireEvent.click(screen.getByRole('button', { name: 'Không ghi nhớ' }));

    expect(onChange).not.toHaveBeenCalled();
    expect(screen.queryByText(WARNING)).not.toBeInTheDocument();
  });

  it('bỏ tick thì tắt ngay, không hỏi', () => {
    const onChange = vi.fn();
    render(<RememberMeCheckbox checked onChange={onChange} />);

    fireEvent.click(screen.getByLabelText(BOX));

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith(false);
    expect(screen.queryByText(WARNING)).not.toBeInTheDocument();
  });
});
