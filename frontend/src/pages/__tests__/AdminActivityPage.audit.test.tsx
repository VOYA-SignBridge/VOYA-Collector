import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

/**
 * Bảng "Nhật ký kiểm toán" trên trang Hoạt động.
 *
 * Trang này đã có một bảng nhật ký từ trước, đọc từ danh sách Redis `sec:log` —
 * cắt còn 500 mục, trên một Redis chạy `volatile-lru`, tức **có thể mất dòng**.
 * Bảng mới đọc từ `audit_log` trong Postgres: không bị đuổi, có `ip_hash` đối
 * chiếu được.
 *
 * Test ở đây canh hai thứ, và thứ hai mới là thứ dễ hỏng khi có người sửa lại
 * trang này về sau:
 *
 *   1. Dòng kiểm toán hiện ra và lọc được theo tiền tố hành động.
 *   2. Bảng này **không** nằm trong vòng poll 3 giây của trang. Nó là bản ghi
 *      lịch sử; hỏi lại mỗi ba giây là bắt Postgres quét một bảng chỉ tăng để
 *      hiển thị dữ liệu gần như không đổi. Một lần "dọn dẹp" gộp nó vào
 *      `fetchReport` sẽ làm test này đỏ.
 */

vi.mock('../../api/axiosClient', () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

vi.mock('../../hooks/useToast', () => ({
  useToast: () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }),
}));

import AdminActivityPage from '../AdminActivityPage';
import apiClient from '../../api/axiosClient';

const EMPTY_REPORT = {
  sessions: [],
  online_count: 0,
  anomalies: [],
  blocked: [],
  security_log: [],
  geoip_enabled: false,
};

const AUDIT_ROWS = [
  {
    audit_id: 2,
    created_at: '2026-08-08T16:00:00+00:00',
    tenant_id: 'default',
    actor_user_id: '11111111-1111-1111-1111-111111111111',
    actor_label: 'quantri',
    action: 'data.class.purge',
    target_type: 'class',
    target_id: '33370c10-ca2b-4b20-add0-ff7abb9eee71',
    detail: { op_id: 'class_purge_33370c10' },
    ip_hash: 'abcdef0123456789',
  },
  {
    audit_id: 1,
    created_at: '2026-08-08T15:00:00+00:00',
    tenant_id: 'default',
    actor_user_id: null,
    actor_label: null,
    action: 'security.block_ip',
    target_type: 'security',
    target_id: '203.0.113.9',
    detail: { reason: 'quét cổng' },
    ip_hash: null,
  },
];

const auditCalls = () =>
  (apiClient.get as any).mock.calls.filter((c: any[]) =>
    String(c[0]).includes('/audit-log'));

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  (apiClient.get as any).mockImplementation((url: string) => {
    if (url.includes('/audit-log')) return Promise.resolve({ data: { events: AUDIT_ROWS } });
    return Promise.resolve({ data: EMPTY_REPORT });
  });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('Nhật ký kiểm toán bền', () => {
  it('hiện dòng kiểm toán kèm người thực hiện và đối tượng', async () => {
    render(<AdminActivityPage />);

    expect(await screen.findByText('data.class.purge')).toBeInTheDocument();
    expect(screen.getByText('quantri')).toBeInTheDocument();
    expect(screen.getByText('security.block_ip')).toBeInTheDocument();
  });

  it('gọi hệ thống khi dòng không có người thực hiện', async () => {
    render(<AdminActivityPage />);

    await screen.findByText('security.block_ip');
    expect(screen.getByText('hệ thống')).toBeInTheDocument();
  });

  it('chỉ hiện tám ký tự đầu của băm nguồn', async () => {
    /** Băm đầy đủ dài 64 ký tự và không nói gì thêm cho người xem; tám ký tự
     * đủ để nhận ra hai hành động cùng một nguồn, mà không biến một cột thành
     * một bức tường hex. */
    render(<AdminActivityPage />);

    expect(await screen.findByText('abcdef01')).toBeInTheDocument();
    expect(screen.queryByText('abcdef0123456789')).not.toBeInTheDocument();
  });

  it('lọc theo tiền tố hành động', async () => {
    render(<AdminActivityPage />);
    await screen.findByText('data.class.purge');
    const before = auditCalls().length;

    fireEvent.click(screen.getByRole('button', { name: 'Dữ liệu' }));

    await waitFor(() => expect(auditCalls().length).toBe(before + 1));
    const last = auditCalls().at(-1);
    expect(last[1].params.action_prefix).toBe('data.');
  });

  it('KHÔNG nằm trong vòng poll ba giây của trang', async () => {
    render(<AdminActivityPage />);
    await screen.findByText('data.class.purge');

    const auditBefore = auditCalls().length;
    const reportBefore = (apiClient.get as any).mock.calls.length - auditBefore;

    await act(async () => { vi.advanceTimersByTime(10_000); });

    const auditAfter = auditCalls().length;
    const reportAfter = (apiClient.get as any).mock.calls.length - auditAfter;

    expect(auditAfter).toBe(auditBefore);
    expect(reportAfter).toBeGreaterThan(reportBefore);
  });
});
