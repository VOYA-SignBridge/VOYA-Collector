import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * Thiết bị đang đăng nhập + lịch sử đăng nhập.
 *
 * Hai điều giao diện phải giữ: thiết bị ĐANG DÙNG không có nút đăng xuất (đá chính
 * mình khỏi trang đang mở là thao tác dễ nhầm), và "đăng xuất mọi thiết bị khác"
 * phải hỏi lại trước khi làm.
 */
const fetchSessions = vi.fn();
const revokeSession = vi.fn();
const revokeOtherSessions = vi.fn();
const fetchLoginHistory = vi.fn();
vi.mock('../../../api/auth', () => ({
  fetchSessions: (...a: unknown[]) => fetchSessions(...a),
  revokeSession: (...a: unknown[]) => revokeSession(...a),
  revokeOtherSessions: (...a: unknown[]) => revokeOtherSessions(...a),
  fetchLoginHistory: (...a: unknown[]) => fetchLoginHistory(...a),
}));
const toast = { success: vi.fn(), error: vi.fn() };
vi.mock('../../../hooks/useToast', () => ({ useToast: () => ({ toast }) }));

import DevicesSection from '../DevicesSection';
import LoginHistorySection from '../LoginHistorySection';

const NOW = '2026-11-16T07:00:00Z';
const ME = { id: 'f-me', device: 'Chrome · Windows', started_at: NOW, last_active: NOW, remembered: false, current: true };
const PHONE = { id: 'f-phone', device: 'Safari · iPhone', started_at: NOW, last_active: NOW, remembered: true, current: false };
const LAPTOP = { id: 'f-lap', device: 'Firefox · Linux', started_at: NOW, last_active: NOW, remembered: false, current: false };

beforeEach(() => {
  vi.clearAllMocks();
  fetchSessions.mockResolvedValue([ME, PHONE, LAPTOP]);
  revokeSession.mockResolvedValue(undefined);
  revokeOtherSessions.mockResolvedValue(2);
});

describe('DevicesSection', () => {
  it('liệt kê thiết bị, đánh dấu thiết bị này và thiết bị đã ghi nhớ', async () => {
    render(<DevicesSection />);
    expect(await screen.findByText('Chrome · Windows')).toBeInTheDocument();
    expect(screen.getByText('Thiết bị này')).toBeInTheDocument();
    expect(screen.getByText('Đã ghi nhớ')).toBeInTheDocument();
  });

  it('thiết bị đang dùng KHÔNG có nút đăng xuất; thiết bị khác thì có', async () => {
    render(<DevicesSection />);
    await screen.findByText('Chrome · Windows');
    const rows = screen.getAllByRole('listitem');
    expect(within(rows[0]).queryByRole('button', { name: 'Đăng xuất' })).toBeNull();
    expect(within(rows[1]).getByRole('button', { name: 'Đăng xuất' })).toBeInTheDocument();
  });

  it('đăng xuất một thiết bị: gọi đúng id rồi nạp lại danh sách', async () => {
    render(<DevicesSection />);
    await screen.findByText('Safari · iPhone');
    fireEvent.click(within(screen.getAllByRole('listitem')[1]).getByRole('button', { name: 'Đăng xuất' }));

    await waitFor(() => expect(revokeSession).toHaveBeenCalledWith('f-phone'));
    await waitFor(() => expect(fetchSessions).toHaveBeenCalledTimes(2));
    expect(toast.success).toHaveBeenCalled();
  });

  it('đăng xuất mọi thiết bị khác phải hỏi lại, và chưa làm gì khi chưa xác nhận', async () => {
    render(<DevicesSection />);
    await screen.findByText('Chrome · Windows');
    fireEvent.click(screen.getByRole('button', { name: 'Đăng xuất mọi thiết bị khác' }));

    expect(screen.getByText(/2 thiết bị khác sẽ bị đăng xuất ngay/)).toBeInTheDocument();
    expect(revokeOtherSessions).not.toHaveBeenCalled();

    // Nút xác nhận nằm trong hộp thoại, đứng SAU danh sách trong DOM.
    fireEvent.click(screen.getAllByRole('button', { name: 'Đăng xuất' }).at(-1)!);
    await waitFor(() => expect(revokeOtherSessions).toHaveBeenCalledTimes(1));
  });

  it('chỉ có một thiết bị thì không có nút đăng xuất mọi thiết bị khác', async () => {
    fetchSessions.mockResolvedValue([ME]);
    render(<DevicesSection />);
    await screen.findByText('Chrome · Windows');
    expect(screen.queryByRole('button', { name: 'Đăng xuất mọi thiết bị khác' })).toBeNull();
  });

  it('lỗi khi đăng xuất thì báo lỗi và giữ danh sách', async () => {
    revokeSession.mockRejectedValue(new Error('boom'));
    render(<DevicesSection />);
    await screen.findByText('Safari · iPhone');
    fireEvent.click(within(screen.getAllByRole('listitem')[1]).getByRole('button', { name: 'Đăng xuất' }));

    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(screen.getByText('Safari · iPhone')).toBeInTheDocument();
  });

  it('không tải được danh sách thì nói rõ và có nút thử lại', async () => {
    fetchSessions.mockRejectedValueOnce(new Error('net')).mockResolvedValueOnce([ME]);
    render(<DevicesSection />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Không tải được danh sách thiết bị');
    fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
    expect(await screen.findByText('Chrome · Windows')).toBeInTheDocument();
  });
});

describe('LoginHistorySection', () => {
  it('hiện thiết bị, nơi đăng nhập (nếu có) và thời điểm', async () => {
    fetchLoginHistory.mockResolvedValue([
      { at: NOW, device: 'Chrome · Windows', place: 'Cần Thơ, Việt Nam', remember: false },
      { at: NOW, device: 'Safari · iPhone', place: '', remember: true },
    ]);
    render(<LoginHistorySection />);
    expect(await screen.findByText('Chrome · Windows')).toBeInTheDocument();
    expect(screen.getByText(/Cần Thơ, Việt Nam/)).toBeInTheDocument();
    expect(screen.getByText('Safari · iPhone')).toBeInTheDocument();
  });

  it('chưa có lần nào thì nói thật chứ không để trống', async () => {
    fetchLoginHistory.mockResolvedValue([]);
    render(<LoginHistorySection />);
    expect(await screen.findByText('Chưa có lần đăng nhập nào được ghi lại.')).toBeInTheDocument();
  });

  it('lỗi tải thì báo, không treo vòng quay', async () => {
    fetchLoginHistory.mockRejectedValue(new Error('x'));
    render(<LoginHistorySection />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Không tải được lịch sử đăng nhập');
  });
});
