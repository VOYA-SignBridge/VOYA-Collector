import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, beforeEach, vi } from 'vitest';

/**
 * Trang xác minh email và số điện thoại.
 *
 * Điều quan trọng nhất được ghim ở đây: **mỗi lần chỉ một luồng mở**.
 *
 * `/verify/confirm` không hỏi mã này trả lời cho kênh nào — nó thử
 * `verify_phone` trước rồi mới tới `verify_email`. Nếu cả hai thử thách cùng
 * sống, mỗi lần nộp mã email đúng vẫn tiêu một lượt thử của thử thách điện
 * thoại; năm lần là thử thách điện thoại chết vì "nhập sai quá số lần" dù
 * người dùng chưa gõ sai chữ nào. Giao diện là chỗ duy nhất chặn được chuyện
 * đó, nên nó phải được test.
 */

vi.mock('../../api/verification', () => ({
  fetchVerificationStatus: vi.fn(),
  sendVerificationCode: vi.fn(),
  confirmVerificationCode: vi.fn(),
}));

const toastSuccess = vi.fn();
vi.mock('../../hooks/useToast', () => ({
  useToast: () => ({ toast: { success: toastSuccess, error: vi.fn(), info: vi.fn() } }),
}));

import VerifyContactPage from '../VerifyContactPage';
import {
  confirmVerificationCode,
  fetchVerificationStatus,
  sendVerificationCode,
} from '../../api/verification';

const STATUS = {
  email: 'minh@ctu.edu.vn',
  email_verified: false,
  phone_number: '',
  phone_verified: false,
  resend_cooldown_seconds: 60,
  code_ttl_minutes: 10,
  sms_available: true,
};

const view = () =>
  render(
    <MemoryRouter>
      <VerifyContactPage />
    </MemoryRouter>,
  );

beforeEach(() => {
  vi.clearAllMocks();
  (fetchVerificationStatus as any).mockResolvedValue(STATUS);
  (sendVerificationCode as any).mockResolvedValue({
    challenge_id: 'c-1', purpose: 'verify_email', channel: 'email', expires_in_minutes: 10,
  });
});

describe('Chỉ một luồng mở tại một thời điểm', () => {
  it('mở luồng email thì luồng SMS không còn ô nhập mã', async () => {
    view();
    fireEvent.click(await screen.findByRole('button', { name: 'Gửi mã tới email này' }));

    // Đúng MỘT ô nhập mã trên toàn trang. Hai ô nghĩa là hai thử thách cùng
    // sống, và mỗi lần nộp mã sẽ ăn mất một lượt thử của thử thách kia.
    await waitFor(() => expect(screen.getAllByLabelText('Nhập mã sáu chữ số')).toHaveLength(1));
    expect(screen.queryByRole('button', { name: 'Gửi mã qua tin nhắn' })).toBeInTheDocument();
  });

  it('nút Huỷ đóng luồng đang mở lại', async () => {
    view();
    fireEvent.click(await screen.findByRole('button', { name: 'Gửi mã tới email này' }));
    await screen.findByLabelText('Nhập mã sáu chữ số');

    fireEvent.click(screen.getByRole('button', { name: 'Huỷ' }));
    await waitFor(() =>
      expect(screen.queryByLabelText('Nhập mã sáu chữ số')).not.toBeInTheDocument());
  });
});

describe('Kênh tin nhắn khi hệ thống chưa bật SMS', () => {
  it('nói ra thay vì để người dùng bấm rồi nhận lỗi', async () => {
    /** Một lượt gửi hỏng vì 503 vẫn đốt thời gian chờ, khiến người dùng không
     * xin lại mã qua email được trong một phút. Chặn ở đây rẻ hơn nhiều. */
    (fetchVerificationStatus as any).mockResolvedValue({ ...STATUS, sms_available: false });
    view();

    expect(await screen.findByText(/chưa bật kênh tin nhắn/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Gửi mã qua tin nhắn' })).not.toBeInTheDocument();
  });
});

describe('Số điện thoại phải đúng dạng trước khi gửi', () => {
  it('khoá nút cho tới khi có mã quốc gia', async () => {
    /** Máy chủ đòi E.164 và từ chối phần còn lại. Kiểm ở đây để lời từ chối
     * không tới sau khi họ đã ngồi đợi một tin nhắn. */
    view();
    await screen.findByRole('button', { name: 'Gửi mã qua tin nhắn' });

    const input = screen.getByLabelText('Số điện thoại nhận mã');
    const button = screen.getByRole('button', { name: 'Gửi mã qua tin nhắn' });

    fireEvent.change(input, { target: { value: '0901234567' } });
    expect(button).toBeDisabled();

    fireEvent.change(input, { target: { value: '+84901234567' } });
    expect(button).toBeEnabled();
  });
});

describe('Trạng thái đã xác minh', () => {
  it('đổi nhãn và đổi lời mời hành động', async () => {
    (fetchVerificationStatus as any).mockResolvedValue({ ...STATUS, email_verified: true });
    view();

    expect(await screen.findByText('Đã xác minh')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Xác minh lại' })).toBeInTheDocument();
  });

  it('nạp lại trạng thái sau khi xác minh xong', async () => {
    /** Không nạp lại thì nhãn "Chưa xác minh" vẫn nằm đó sau một lượt thành
     * công, và người dùng sẽ làm lại từ đầu. */
    (confirmVerificationCode as any).mockResolvedValue({
      verified: true, purpose: 'verify_email', channel: 'email',
    });
    view();
    fireEvent.click(await screen.findByRole('button', { name: 'Gửi mã tới email này' }));
    fireEvent.change(await screen.findByLabelText('Nhập mã sáu chữ số'), {
      target: { value: '123456' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận' }));

    await waitFor(() => expect(fetchVerificationStatus).toHaveBeenCalledTimes(2));
    expect(toastSuccess).toHaveBeenCalledWith('Đã xác minh email.');
  });
});

describe('Máy chủ báo còn phải đợi', () => {
  it('mở ô nhập mã ra vì mã cũ vẫn còn sống', async () => {
    /** 429 kèm số giây nghĩa là một thử thách đang sống — mã đã nằm trong hộp
     * thư của họ. Giữ nguyên màn hình cũ là bắt họ đứng trước một nút không
     * bấm được, cạnh một mã họ dùng được ngay. */
    (sendVerificationCode as any).mockRejectedValue({
      response: { status: 429, data: { detail: 'vui lòng đợi 42 giây trước khi yêu cầu mã mới' } },
    });
    view();
    fireEvent.click(await screen.findByRole('button', { name: 'Gửi mã tới email này' }));

    expect(await screen.findByLabelText('Nhập mã sáu chữ số')).toBeInTheDocument();
    expect(
      await screen.findByRole('button', { name: /Gửi lại sau 4[0-2] giây/ }),
    ).toBeDisabled();
  });
});

describe('Một lượt gửi hỏng phải nhìn thấy được', () => {
  it('hiện lỗi ngay cả khi không có luồng nào mở ra', async () => {
    /** Không có khối lỗi ở mức trang thì một lượt gửi hỏng (503, mạng đứt)
     * KHÔNG hiện gì cả: nút bật lại như cũ, và người dùng ngồi đợi một mã
     * không tồn tại. `OtpCodeInput` chỉ hiện lỗi khi luồng ĐÃ mở. */
    (sendVerificationCode as any).mockRejectedValue({
      response: { status: 503, data: { detail: 'SMTP host smtp.gmail.com:587 chưa cấu hình' } },
    });
    view();
    fireEvent.click(await screen.findByRole('button', { name: 'Gửi mã tới email này' }));

    const alert = await screen.findByRole('alert');
    expect(alert).toBeInTheDocument();
    expect(screen.queryByLabelText('Nhập mã sáu chữ số')).not.toBeInTheDocument();

    // Và nhóm 5xx KHÔNG cho `detail` đi qua: tên máy chủ thư, cổng, cấu hình —
    // không chữ nào trong số đó được lên màn hình. Xem `lib/errors.ts`.
    expect(alert).not.toHaveTextContent(/smtp\.gmail\.com/);
    expect(alert).toHaveTextContent(/bảo trì hoặc quá tải/);
  });
});

describe('Nói rõ mã trả lời cho thử thách nào', () => {
  /**
   * `/verify/confirm` nhận `purpose` không bắt buộc. Bỏ trống thì máy chủ dò
   * `verify_phone` trước rồi `verify_email` — và mỗi lần dò trượt đều **trừ
   * lượt** của thử thách nó chạm vào. Trang này chỉ mở một luồng nên đã tránh
   * được, nhưng gửi kèm `purpose` đưa điều bảo đảm vào chính yêu cầu thay vì
   * để nó phụ thuộc máy trạng thái của màn hình.
   */
  const confirmWith = async (open: 'email' | 'sms') => {
    (confirmVerificationCode as any).mockResolvedValue({
      verified: true, purpose: 'verify_email', channel: 'email',
    });
    view();
    if (open === 'email') {
      fireEvent.click(await screen.findByRole('button', { name: 'Gửi mã tới email này' }));
    } else {
      fireEvent.change(await screen.findByLabelText('Số điện thoại nhận mã'), {
        target: { value: '+84901234567' },
      });
      fireEvent.click(screen.getByRole('button', { name: 'Gửi mã qua tin nhắn' }));
    }
    fireEvent.change(await screen.findByLabelText('Nhập mã sáu chữ số'), {
      target: { value: '123456' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận' }));
  };

  it('luồng email gửi kèm verify_email', async () => {
    await confirmWith('email');
    await waitFor(() =>
      expect(confirmVerificationCode).toHaveBeenCalledWith('123456', 'verify_email'));
  });

  it('luồng tin nhắn gửi kèm verify_phone', async () => {
    await confirmWith('sms');
    await waitFor(() =>
      expect(confirmVerificationCode).toHaveBeenCalledWith('123456', 'verify_phone'));
  });
});
