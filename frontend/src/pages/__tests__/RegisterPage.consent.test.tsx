import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, beforeEach, vi } from 'vitest';

/**
 * Ô đồng ý ở biểu mẫu đăng ký.
 *
 * Trước phần này, giao diện đăng ký KHÔNG gửi `accepted_*_version`. Hệ quả:
 * ngay khi máy chủ công bố điều khoản, mọi lượt đăng ký từ trình duyệt trả về
 * 400 `consent_required`. Nghĩa là bật tính năng ở backend mà không có phần
 * này sẽ làm hỏng đăng ký trên toàn hệ thống — nên bốn khẳng định dưới đây
 * canh đúng cái mạch nối đó.
 *
 * Khẳng định thứ năm canh chiều ngược lại: khi CHƯA công bố gì, biểu mẫu phải
 * chạy y như cũ. "Chưa công bố" là trạng thái bình thường, không phải lỗi.
 */

vi.mock('../../api/legal', async () => {
  const actual = await vi.importActual<typeof import('../../api/legal')>(
    '../../api/legal',
  );
  return { ...actual, fetchDocumentOrNull: vi.fn() };
});

vi.mock('../../api/auth', () => ({
  register: vi.fn(),
  login: vi.fn(),
}));

vi.mock('../../api/axiosClient', () => ({
  default: { post: vi.fn(), get: vi.fn() },
  notifyAuthChange: vi.fn(),
}));

import RegisterPage from '../RegisterPage';
import { fetchDocumentOrNull, type LegalDocument } from '../../api/legal';
import { register, login } from '../../api/auth';

function doc(kind: 'terms' | 'privacy', version: string): LegalDocument {
  return {
    kind,
    version,
    url: `/legal/${kind}`,
    title: kind,
    language: 'vi',
    effective_from: '2026-08-08T00:00:00Z',
    change_summary: '',
    content_hash: 'a'.repeat(64),
    requires_reconsent: false,
  };
}

function fillTheForm() {
  fireEvent.change(screen.getByPlaceholderText('vd: minh123'), {
    target: { value: 'nguoidung' },
  });
  fireEvent.change(screen.getByPlaceholderText('vd: minh@example.com'), {
    target: { value: 'nguoidung@example.com' },
  });
  fireEvent.change(screen.getByPlaceholderText('Tối thiểu 8 ký tự'), {
    target: { value: 'matkhau12345' },
  });
  fireEvent.change(screen.getByPlaceholderText('Nhập lại mật khẩu'), {
    target: { value: 'matkhau12345' },
  });
}

function renderPage() {
  return render(
    <MemoryRouter>
      <RegisterPage />
    </MemoryRouter>,
  );
}

describe('RegisterPage — khi hệ thống ĐÃ công bố văn bản', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchDocumentOrNull).mockImplementation(async (kind) =>
      doc(kind as 'terms' | 'privacy', '2026-08-08'),
    );
    vi.mocked(register).mockResolvedValue({
      id: 'u1',
      username: 'nguoidung',
      email: 'nguoidung@example.com',
    });
    vi.mocked(login).mockResolvedValue({
      id: 'u1',
      username: 'nguoidung',
      email: 'nguoidung@example.com',
    });
  });

  it('hiện ô đồng ý kèm liên kết mở được tới từng văn bản', async () => {
    renderPage();

    expect(await screen.findByRole('checkbox')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Điều khoản sử dụng' })).toHaveAttribute(
      'href',
      '/legal/terms',
    );
    expect(
      screen.getByRole('link', { name: 'Chính sách quyền riêng tư' }),
    ).toHaveAttribute('href', '/legal/privacy');
  });

  it('khoá nút gửi khi chưa tích ô đồng ý', async () => {
    renderPage();
    await screen.findByRole('checkbox');

    fillTheForm();

    expect(screen.getByRole('button', { name: /Tạo tài khoản/ })).toBeDisabled();
  });

  it('mở khoá nút gửi sau khi tích', async () => {
    renderPage();
    const box = await screen.findByRole('checkbox');

    fillTheForm();
    fireEvent.click(box);

    expect(screen.getByRole('button', { name: /Tạo tài khoản/ })).toBeEnabled();
  });

  it('gửi kèm số hiệu phiên bản vừa đọc được', async () => {
    // Đây là mạch nối thật sự: thiếu nó, máy chủ trả 400 cho mọi lượt đăng ký
    // ngay khi điều khoản được công bố.
    renderPage();
    const box = await screen.findByRole('checkbox');

    fillTheForm();
    fireEvent.click(box);
    fireEvent.click(screen.getByRole('button', { name: /Tạo tài khoản/ }));

    await waitFor(() => expect(register).toHaveBeenCalled());
    expect(vi.mocked(register).mock.calls[0][0]).toMatchObject({
      accepted_terms_version: '2026-08-08',
      accepted_privacy_version: '2026-08-08',
    });
  });

  it('bỏ tích và nạp lại khi máy chủ báo bản đã cũ', async () => {
    // Một tab mở lâu ngày. Giữ nguyên ô tích là ghi nhận sự đồng ý với bản văn
    // người dùng chưa đọc.
    vi.mocked(register).mockRejectedValueOnce({
      response: {
        data: {
          detail: {
            code: 'stale_version',
            message: 'Văn bản đã được cập nhật. Hãy tải lại trang và đọc bản mới.',
          },
        },
      },
    });
    renderPage();
    const box = await screen.findByRole('checkbox');

    fillTheForm();
    fireEvent.click(box);
    fireEvent.click(screen.getByRole('button', { name: /Tạo tài khoản/ }));

    expect(await screen.findByText(/Văn bản đã được cập nhật/)).toBeInTheDocument();
    expect(screen.getByRole('checkbox')).not.toBeChecked();
  });

  it('hiện thông điệp lỗi dạng đối tượng thành chữ, không làm trắng trang', async () => {
    // `detail` của FastAPI là chuỗi ở phần lớn endpoint nhưng là ĐỐI TƯỢNG ở
    // nhánh chấp thuận. Đưa thẳng đối tượng vào state kiểu chuỗi làm React ném
    // "Objects are not valid as a React child" và che mất chính thông báo đang
    // cần hiển thị.
    vi.mocked(register).mockRejectedValueOnce({
      response: {
        data: {
          detail: {
            code: 'consent_required',
            kind: 'terms',
            version: '2026-08-08',
            message: 'Bạn cần đọc và đồng ý trước khi tạo tài khoản.',
          },
        },
      },
    });
    renderPage();
    const box = await screen.findByRole('checkbox');

    fillTheForm();
    fireEvent.click(box);
    fireEvent.click(screen.getByRole('button', { name: /Tạo tài khoản/ }));

    expect(
      await screen.findByText('Bạn cần đọc và đồng ý trước khi tạo tài khoản.'),
    ).toBeInTheDocument();
  });
});

describe('RegisterPage — khi hệ thống CHƯA công bố văn bản', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchDocumentOrNull).mockResolvedValue(null);
    vi.mocked(register).mockResolvedValue({
      id: 'u1',
      username: 'nguoidung',
      email: 'nguoidung@example.com',
    });
    vi.mocked(login).mockResolvedValue({
      id: 'u1',
      username: 'nguoidung',
      email: 'nguoidung@example.com',
    });
  });

  it('không hiện ô đồng ý và vẫn cho đăng ký', async () => {
    // Công bố CHÍNH LÀ hành động bật cưỡng chế. Một bản triển khai chưa công bố
    // gì thì không có gì để đồng ý, và biểu mẫu không được hỏi một câu không có
    // câu trả lời.
    renderPage();

    await waitFor(() => expect(fetchDocumentOrNull).toHaveBeenCalled());
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();

    fillTheForm();
    expect(screen.getByRole('button', { name: /Tạo tài khoản/ })).toBeEnabled();
  });

  it('không gửi trường chấp thuận nào', async () => {
    renderPage();
    await waitFor(() => expect(fetchDocumentOrNull).toHaveBeenCalled());

    fillTheForm();
    fireEvent.click(screen.getByRole('button', { name: /Tạo tài khoản/ }));

    await waitFor(() => expect(register).toHaveBeenCalled());
    const payload = vi.mocked(register).mock.calls[0][0];
    expect(payload).not.toHaveProperty('accepted_terms_version');
  });
});
