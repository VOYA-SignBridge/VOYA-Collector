import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { describe, it, expect, beforeEach, vi } from 'vitest';

/**
 * Trang nhận lời mời.
 *
 * Hai ràng buộc được ghim, và cả hai đều về nơi mã lời mời được phép xuất hiện:
 *
 *   1. Mã đọc được từ **fragment** (`#token=…`). Đó là dạng liên kết mà trang
 *      quản trị phát ra, vì trình duyệt không gửi phần sau dấu thăng lên máy
 *      chủ nào.
 *   2. Mã tới từ **query string** vẫn dùng được — thư mời cũ có thể ở dạng đó —
 *      nhưng phải bị xoá khỏi thanh địa chỉ ngay. Muộn còn hơn không: nó chặn
 *      được phần lịch sử trình duyệt và header `Referer`.
 *
 * Và một ràng buộc về luồng: mã đi tiếp sang biểu mẫu đăng ký qua **state của
 * router**, không qua URL lần thứ hai.
 */

vi.mock('../../api/tenants', async () => {
  const actual = await vi.importActual<typeof import('../../api/tenants')>('../../api/tenants');
  return { ...actual, inspectInvitation: vi.fn() };
});

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ isAuthenticated: false, isAdmin: false, loading: false, user: null }),
}));

import InvitationPage from '../InvitationPage';
import { inspectInvitation } from '../../api/tenants';

const PREVIEW = {
  tenant_id: 'truong-b',
  tenant_display_name: 'Trường Chuyên Biệt B',
  email: 'giaovien@truongb.vn',
  role: 'member' as const,
  expires_at: null,
};

/** Phơi ra state mà `/register` nhận được, để test đọc được nó. */
function RegisterProbe() {
  const state = useLocation().state as Record<string, unknown> | null;
  return <pre data-testid="handoff">{JSON.stringify(state)}</pre>;
}

const view = (entry: string) =>
  render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/invitation" element={<InvitationPage />} />
        <Route path="/register" element={<RegisterProbe />} />
      </Routes>
    </MemoryRouter>,
  );

beforeEach(() => {
  vi.clearAllMocks();
  (inspectInvitation as any).mockResolvedValue(PREVIEW);
  window.history.replaceState(null, '', '/');
});

describe('Đọc mã lời mời', () => {
  it('lấy mã từ fragment', async () => {
    view('/invitation#token=ma-bi-mat');
    await waitFor(() => expect(inspectInvitation).toHaveBeenCalledWith('ma-bi-mat'));
    expect(await screen.findByText('Trường Chuyên Biệt B')).toBeInTheDocument();
  });

  it('chấp nhận mã ở query string nhưng gỡ nó khỏi thanh địa chỉ', async () => {
    const replace = vi.spyOn(window.history, 'replaceState');
    view('/invitation?token=ma-cu');

    await waitFor(() => expect(inspectInvitation).toHaveBeenCalledWith('ma-cu'));
    expect(replace).toHaveBeenCalledWith(null, '', '/invitation#token=ma-cu');
  });

  it('không có mã thì hỏi, không báo lỗi', async () => {
    /** Mở trang trần không phải là sự cố — người dùng có thể chỉ có mã rời chép
     * từ tin nhắn. Bắn ra một hộp đỏ ở đây là dạy họ bỏ qua hộp đỏ. */
    view('/invitation');

    expect(await screen.findByLabelText('Mã lời mời')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(inspectInvitation).not.toHaveBeenCalled();
  });

  it('mã hỏng hay hết hạn đều nói cùng một câu', async () => {
    /** Máy chủ trả 404 giống hệt nhau cho hai trường hợp, có chủ ý — phân biệt
     * được nghĩa là dò được mã. Giao diện cũng không được đoán. */
    (inspectInvitation as any).mockRejectedValue({ response: { status: 404 } });
    view('/invitation#token=ma-sai');

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.queryByText(/hết hạn từ/i)).not.toBeInTheDocument();
  });
});

describe('Chuyển sang đăng ký', () => {
  it('mang mã qua state của router, KHÔNG qua URL', async () => {
    view('/invitation#token=ma-bi-mat');
    fireEvent.click(await screen.findByRole('button', { name: 'Tạo tài khoản để gia nhập' }));

    const handoff = JSON.parse((await screen.findByTestId('handoff')).textContent || '{}');
    expect(handoff).toEqual({
      invitationToken: 'ma-bi-mat',
      invitationEmail: 'giaovien@truongb.vn',
      invitationTenant: 'Trường Chuyên Biệt B',
    });
  });

  it('hiện vai bằng tiếng Việt', async () => {
    (inspectInvitation as any).mockResolvedValue({ ...PREVIEW, role: 'admin' });
    view('/invitation#token=ma-bi-mat');

    expect(await screen.findByText('Quản trị viên')).toBeInTheDocument();
  });
});
