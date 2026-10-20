import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, beforeEach, vi } from 'vitest';

/**
 * Quên mật khẩu — một cửa, ba bước.
 *
 * Test ở đây canh hai thứ, và cố ý KHÔNG canh bố cục:
 *
 * 1. **Điều màn hình không được nói.** Máy chủ trả cùng một câu cho mọi kết cục
 *    của `/recover/start` — gửi được, tài khoản không tồn tại, gửi thất bại. Đó
 *    là chủ ý: khác nhau thì endpoint này thành công cụ dò xem ai có tài khoản.
 *    Cái dễ hỏng là ở giao diện — một dấu tích xanh hay một câu "đã gửi mã tới
 *    bạn" sẽ hoàn tác toàn bộ công sức đó ở tầng dưới, một cách im lặng.
 *
 * 2. **Ranh giới giữa các bước.** Bản trước hỏi tên đăng nhập, mã và hai ô mật
 *    khẩu cùng một lúc, cộng thêm một nút "Tôi đã có mã rồi" cho một tình huống
 *    không tồn tại. Những dòng dưới đây ghim từng thứ đã bỏ đi — vì cách chúng
 *    quay lại là ai đó "tiện tay" thêm một ô vào bước đang mở.
 */

vi.mock('../../api/verification', () => ({
  startRecovery: vi.fn(),
  verifyRecoveryCode: vi.fn(),
  resetPasswordWithTicket: vi.fn(),
}));

import ForgotPasswordPage from '../ForgotPasswordPage';
import {
  resetPasswordWithTicket,
  startRecovery,
  verifyRecoveryCode,
} from '../../api/verification';

const GENERIC =
  'Nếu tài khoản tồn tại, chúng tôi đã gửi mã xác minh. Mã có hiệu lực trong ít phút.';

const view = () =>
  render(
    <MemoryRouter>
      <ForgotPasswordPage />
    </MemoryRouter>,
  );

/** Bước 1 → 2. */
const askForCode = async (identifier = 'minh123') => {
  fireEvent.change(screen.getByLabelText('Tên đăng nhập hoặc email'), {
    target: { value: identifier },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Tiếp tục' }));
  await screen.findByLabelText('Mã xác minh');
};

/** Bước 2 → 3. */
const enterCode = async (code = '123456') => {
  fireEvent.change(screen.getByLabelText('Mã xác minh'), { target: { value: code } });
  fireEvent.click(screen.getByRole('button', { name: 'Xác nhận' }));
  await screen.findByLabelText('Mật khẩu mới');
};

const fillPasswords = (value = 'MatKhau123') => {
  fireEvent.change(screen.getByLabelText('Mật khẩu mới'), { target: { value } });
  fireEvent.change(screen.getByLabelText('Xác nhận mật khẩu mới'), { target: { value } });
};

beforeEach(() => {
  vi.clearAllMocks();
  (startRecovery as any).mockResolvedValue({ message: GENERIC });
  (verifyRecoveryCode as any).mockResolvedValue({
    reset_ticket: 've-gia',
    expires_in_minutes: 5,
  });
  (resetPasswordWithTicket as any).mockResolvedValue({ message: 'ok' });
});

describe('Không tiết lộ tài khoản có tồn tại hay không', () => {
  it('hiện nguyên văn câu chung của máy chủ', async () => {
    view();
    await askForCode();

    expect(screen.getByText(GENERIC)).toBeInTheDocument();
  });

  it('KHÔNG khẳng định đã gửi tới đúng người', async () => {
    view();
    await askForCode('khong-ton-tai@vidu.vn');

    // Những câu này đều là lời khẳng định tài khoản tồn tại. Không câu nào
    // được xuất hiện, kể cả khi máy chủ thật sự đã gửi.
    expect(screen.queryByText(/đã gửi mã tới bạn/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/kiểm tra hộp thư của bạn/i)).not.toBeInTheDocument();

    // Câu duy nhất nói về việc gửi phải là câu có điều kiện của máy chủ. Nếu
    // một ngày nào đó ai đó thay nó bằng câu khẳng định, dòng này đổ.
    expect(screen.getByText(GENERIC)).toHaveTextContent(/^Nếu tài khoản tồn tại,/);
  });
});

describe('Ba bước, và ranh giới giữa chúng', () => {
  it('không có lối tắt "Tôi đã có mã rồi"', () => {
    /** Mã chỉ ra đời khi ai đó bấm xin. Một cửa để tự khai là mình có mã sẵn
     * mô tả một tình huống không tồn tại; người chưa thấy mã cần nút Gửi lại. */
    view();
    expect(screen.queryByRole('button', { name: /đã có mã/i })).not.toBeInTheDocument();
  });

  it('bước nhập mã KHÔNG hỏi lại tên đăng nhập', async () => {
    /** Bản trước dựng lại nguyên ô nhập ở bước hai, nên người dùng vừa gõ xong
     * đã bị hỏi lại đúng câu đó. Giờ tên đăng nhập là ngữ cảnh chỉ-đọc. */
    view();
    await askForCode('minh123');

    expect(screen.queryByLabelText('Tên đăng nhập hoặc email')).not.toBeInTheDocument();
    expect(screen.getByText('minh123')).toBeInTheDocument();
  });

  it('bước nhập mã KHÔNG hỏi mật khẩu', async () => {
    /** Đây là lý do tách bước: gõ nhầm một chữ số của mã không được làm mất cả
     * một mật khẩu vừa nghĩ ra. */
    view();
    await askForCode();

    expect(screen.queryByLabelText('Mật khẩu mới')).not.toBeInTheDocument();
  });

  it('bước đặt mật khẩu KHÔNG còn ô mã', async () => {
    view();
    await askForCode();
    await enterCode();

    expect(screen.queryByLabelText('Mã xác minh')).not.toBeInTheDocument();
  });

  it('nút "Đổi" đưa về bước một, giữ nguyên tên đã gõ', async () => {
    view();
    await askForCode('minh123');

    fireEvent.click(screen.getByRole('button', { name: 'Đổi' }));

    const input = (await screen.findByLabelText(
      'Tên đăng nhập hoặc email',
    )) as HTMLInputElement;
    expect(input.value).toBe('minh123');
  });
});

describe('Nhập mã', () => {
  it('lọc ký tự không phải chữ số ngay lúc gõ', async () => {
    /** Người dùng chép mã từ email thường kéo theo khoảng trắng hoặc gạch nối.
     * Để nguyên thì máy chủ từ chối một mã vốn đúng, và họ không hiểu vì sao. */
    view();
    await askForCode();

    const input = screen.getByLabelText('Mã xác minh') as HTMLInputElement;
    fireEvent.change(input, { target: { value: ' 12 34-56 ' } });
    expect(input.value).toBe('123456');
  });

  it('chỉ mở nút xác nhận khi đủ sáu chữ số', async () => {
    view();
    await askForCode();

    const submit = screen.getByRole('button', { name: 'Xác nhận' });
    expect(submit).toBeDisabled();

    fireEvent.change(screen.getByLabelText('Mã xác minh'), { target: { value: '12345' } });
    expect(submit).toBeDisabled();

    fireEvent.change(screen.getByLabelText('Mã xác minh'), { target: { value: '123456' } });
    expect(submit).toBeEnabled();
  });

  it('mã sai thì xoá ô mã và Ở LẠI bước hai', async () => {
    /** Giữ lại mã sai trên màn hình mời người dùng bấm gửi lần nữa với đúng
     * chuỗi vừa hỏng — mà mỗi lần như vậy tiêu một trong năm lượt thử. */
    (verifyRecoveryCode as any).mockRejectedValue({
      response: { status: 400, data: { detail: 'Mã xác minh không đúng hoặc đã hết hạn.' } },
    });
    view();
    await askForCode();

    fireEvent.change(screen.getByLabelText('Mã xác minh'), { target: { value: '000000' } });
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/không đúng hoặc đã hết hạn/);
    expect((screen.getByLabelText('Mã xác minh') as HTMLInputElement).value).toBe('');
    expect(screen.queryByLabelText('Mật khẩu mới')).not.toBeInTheDocument();
  });

  it('hết lượt thử thì mở khoá nút gửi lại NGAY, không bắt đợi hết đồng hồ', async () => {
    /** 429 ở bước xác nhận nghĩa là thử thách đã chết vì nhập sai quá số lần.
     * Đồng hồ chờ đang đếm cho một mã không còn tồn tại; bắt họ ngồi hết nó là
     * bắt chờ một thứ đã mất. */
    (verifyRecoveryCode as any).mockRejectedValue({
      response: { status: 429, data: { detail: 'đã nhập sai quá số lần cho phép' } },
    });
    view();
    await askForCode();

    fireEvent.change(screen.getByLabelText('Mã xác minh'), { target: { value: '000000' } });
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận' }));

    expect(await screen.findByRole('button', { name: 'Gửi lại mã' })).toBeEnabled();
  });
});

describe('Đặt mật khẩu mới', () => {
  it('chỉ mở nút khi hai mật khẩu khớp nhau', async () => {
    view();
    await askForCode();
    await enterCode();

    const submit = screen.getByRole('button', { name: 'Lưu mật khẩu mới' });
    expect(submit).toBeDisabled();

    fireEvent.change(screen.getByLabelText('Mật khẩu mới'), { target: { value: 'MatKhau123' } });
    expect(submit).toBeDisabled(); // chưa xác nhận

    fireEvent.change(screen.getByLabelText('Xác nhận mật khẩu mới'), {
      target: { value: 'MatKhauKhac' },
    });
    expect(submit).toBeDisabled(); // lệch nhau

    fireEvent.change(screen.getByLabelText('Xác nhận mật khẩu mới'), {
      target: { value: 'MatKhau123' },
    });
    expect(submit).toBeEnabled();
  });

  it('gửi VÉ chứ không gửi lại mã', async () => {
    /** Mã đã bị tiêu ở bước hai. Gửi lại nó là gửi một thứ máy chủ chắc chắn
     * từ chối, và người dùng sẽ thấy "mã sai" ngay sau khi vừa nhập đúng. */
    view();
    await askForCode();
    await enterCode();
    fillPasswords();
    fireEvent.click(screen.getByRole('button', { name: 'Lưu mật khẩu mới' }));

    await waitFor(() =>
      expect(resetPasswordWithTicket).toHaveBeenCalledWith('ve-gia', 'MatKhau123'),
    );
  });

  it('nói rõ mọi phiên cũ đã bị thu hồi sau khi đổi xong', async () => {
    /** Đây là điều người vừa bị chiếm tài khoản cần biết nhất, và máy chủ có
     * làm thật (`set_password_and_revoke_sessions`). Không nói ra thì họ vẫn
     * lo kẻ kia còn đăng nhập được. */
    view();
    await askForCode();
    await enterCode();
    fillPasswords();
    fireEvent.click(screen.getByRole('button', { name: 'Lưu mật khẩu mới' }));

    expect(await screen.findByText(/thu hồi/i)).toBeInTheDocument();
  });

  it('vé hết hạn thì quay về bước một, KHÔNG quay về bước nhập mã', async () => {
    /** Mã đã tiêu, nên bước hai là ngõ cụt — không có gì để họ nhập ở đó nữa.
     * Tên đăng nhập giữ nguyên để chỉ cần bấm một lần là có mã mới. */
    (resetPasswordWithTicket as any).mockRejectedValue({
      response: { status: 400, data: { detail: 'Phiên đặt lại mật khẩu đã hết hạn. Hãy xin mã mới.' } },
    });
    view();
    await askForCode('minh123');
    await enterCode();
    fillPasswords();
    fireEvent.click(screen.getByRole('button', { name: 'Lưu mật khẩu mới' }));

    const input = (await screen.findByLabelText(
      'Tên đăng nhập hoặc email',
    )) as HTMLInputElement;
    expect(input.value).toBe('minh123');
    expect(screen.queryByLabelText('Mã xác minh')).not.toBeInTheDocument();
  });
});

describe('Chờ giữa hai lần xin mã', () => {
  it('khoá nút gửi lại và đếm ngược', async () => {
    view();
    await askForCode();

    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /Chưa nhận được mã\? Gửi lại sau \d+ giây/ }),
      ).toBeDisabled(),
    );
  });

  it('máy chủ báo còn phải đợi thì lấy đúng con số của máy chủ', async () => {
    /** Đồng hồ của giao diện chỉ là lớp lịch sự. Khi hai bên lệch nhau — người
     * dùng mở hai tab, hoặc tải lại trang giữa chừng — máy chủ mới đúng. */
    (startRecovery as any).mockRejectedValue({
      response: { status: 429, data: { detail: 'vui lòng đợi 47 giây trước khi yêu cầu mã mới' } },
    });
    view();

    fireEvent.change(screen.getByLabelText('Tên đăng nhập hoặc email'), {
      target: { value: 'minh123' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Tiếp tục' }));

    expect(
      await screen.findByRole('button', { name: /Gửi lại sau 4[5-7] giây/ }),
    ).toBeDisabled();
  });
});
