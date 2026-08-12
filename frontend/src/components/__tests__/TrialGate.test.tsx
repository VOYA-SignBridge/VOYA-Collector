import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, beforeEach, vi } from 'vitest';

/**
 * Cổng dùng thử.
 *
 * Ràng buộc quan trọng nhất: **không dựng runtime khi chưa có phiếu**. Nếu
 * dựng, `RealtimeRuntime` xin quyền camera của khách rồi mọi lời gọi API trả
 * 401 — tức là bật camera của người ta lên mà không dùng vào việc gì, và trên
 * màn hình hiện "Không thể tải danh sách bộ nhận diện", một câu nói rằng hệ
 * thống hỏng trong khi thứ họ cần chỉ là bấm một nút.
 */

vi.mock('../../api/trial', async () => {
  const actual = await vi.importActual<typeof import('../../api/trial')>('../../api/trial');
  return { ...actual, startTrial: vi.fn(), fetchTrialStatus: vi.fn() };
});

let authState = { loading: false, isAuthenticated: false };
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => authState,
}));

import TrialGate from '../TrialGate';
import { fetchTrialStatus, startTrial, TRIAL_EVENT } from '../../api/trial';

const NO_GRANT = {
  has_grant: false, minutes_limit: 60, minutes_used: 0,
  minutes_remaining: 60, resets_at: null, exhausted: false,
};
const WITH_GRANT = { ...NO_GRANT, has_grant: true, minutes_used: 5, minutes_remaining: 55 };

const RUNTIME = <div data-testid="runtime">bộ nhận diện</div>;

const view = () =>
  render(
    <MemoryRouter>
      <TrialGate>{RUNTIME}</TrialGate>
    </MemoryRouter>,
  );

beforeEach(() => {
  vi.clearAllMocks();
  authState = { loading: false, isAuthenticated: false };
  (fetchTrialStatus as any).mockResolvedValue(NO_GRANT);
});

describe('Người đã đăng nhập', () => {
  it('đi thẳng qua, không hỏi hạn mức dùng thử', async () => {
    /** Phiếu chỉ dành cho khách. Gọi `/trial/status` cho người đã đăng nhập là
     * một vòng mạng thừa trên mỗi lượt mở trang. */
    authState = { loading: false, isAuthenticated: true };
    view();

    expect(screen.getByTestId('runtime')).toBeInTheDocument();
    expect(fetchTrialStatus).not.toHaveBeenCalled();
  });
});

describe('Khách chưa có phiếu', () => {
  it('KHÔNG dựng runtime, và mời bấm một nút', async () => {
    view();

    expect(await screen.findByRole('button', { name: 'Bắt đầu dùng thử' })).toBeInTheDocument();
    expect(screen.queryByTestId('runtime')).not.toBeInTheDocument();
  });

  it('xin phiếu xong thì runtime mới lên', async () => {
    (startTrial as any).mockResolvedValue(WITH_GRANT);
    view();

    fireEvent.click(await screen.findByRole('button', { name: 'Bắt đầu dùng thử' }));

    expect(await screen.findByTestId('runtime')).toBeInTheDocument();
    expect(screen.getByText(/Còn/)).toHaveTextContent('55');
  });

  it('xin phiếu hỏng thì nói ra, và vẫn không dựng runtime', async () => {
    (startTrial as any).mockRejectedValue({ response: { status: 429, data: {} } });
    view();

    fireEvent.click(await screen.findByRole('button', { name: 'Bắt đầu dùng thử' }));

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.queryByTestId('runtime')).not.toBeInTheDocument();
  });
});

describe('Hết phút hôm nay', () => {
  it('không dựng runtime và không mời bấm lại', async () => {
    /** Nút "bắt đầu" ở trạng thái này là lời mời làm một việc chắc chắn hỏng:
     * `start` idempotent theo cookie, bấm lại KHÔNG làm mới hạn ngạch. */
    (fetchTrialStatus as any).mockResolvedValue({
      ...WITH_GRANT, minutes_used: 60, minutes_remaining: 0, exhausted: true,
      resets_at: '2026-08-10T00:00:00Z',
    });
    view();

    expect(await screen.findByText(/Đã hết lượt dùng thử hôm nay/)).toBeInTheDocument();
    expect(screen.queryByTestId('runtime')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Bắt đầu dùng thử' })).not.toBeInTheDocument();
  });
});

describe('Đồng hồ chạy theo phản hồi thật', () => {
  it('cập nhật từ sự kiện, không phải từ một vòng gọi nữa', async () => {
    /** Cổng gác gắn số phút vào header của MỌI phản hồi đi qua phiếu, và
     * `axiosClient` phát ra sự kiện. Hỏi lại `/trial/status` cho mỗi khung hình
     * là gấp đôi lưu lượng chỉ để hiện một con số. */
    (fetchTrialStatus as any).mockResolvedValue(WITH_GRANT);
    view();
    await screen.findByTestId('runtime');

    act(() => {
      window.dispatchEvent(
        new CustomEvent(TRIAL_EVENT, { detail: { remaining: 3, limit: 60 } }),
      );
    });

    await waitFor(() => expect(screen.getByText(/Còn/)).toHaveTextContent('3'));
    // Sắp hết thì đổi sang sắc thái cảnh báo — báo lúc CÒN ÍT, không phải lúc
    // đã hết, vì lúc hết thì đã muộn để họ sắp xếp lại việc đang làm.
    expect(screen.getByRole('progressbar').firstChild).toHaveClass('bg-amber-500');
    expect(fetchTrialStatus).toHaveBeenCalledTimes(1);
  });

  it('sự kiện báo hết phút thì gỡ runtime xuống', async () => {
    (fetchTrialStatus as any).mockResolvedValue(WITH_GRANT);
    view();
    await screen.findByTestId('runtime');

    act(() => {
      window.dispatchEvent(
        new CustomEvent(TRIAL_EVENT, { detail: { remaining: 0, limit: 60, exhausted: true } }),
      );
    });

    await waitFor(() => expect(screen.queryByTestId('runtime')).not.toBeInTheDocument());
    expect(screen.getByText(/Đã hết lượt dùng thử hôm nay/)).toBeInTheDocument();
  });
});
