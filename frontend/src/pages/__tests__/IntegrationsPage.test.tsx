import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';

/**
 * Trang Tích hợp.
 *
 * Ràng buộc quan trọng nhất là thứ dễ làm hỏng nhất khi sửa giao diện về sau:
 * **bí mật chỉ hiện một lần**. Máy chủ chỉ lưu băm của khoá và không endpoint
 * nào đọc lại bí mật webhook, nên một hộp thoại đóng được trước khi người dùng
 * sao chép là mất hẳn giá trị đó.
 *
 * Vì thế phần lớn test ở đây canh chính cơ chế "phải sao chép mới đóng được",
 * chứ không canh việc danh sách hiện đúng chữ.
 */

vi.mock('../../api/integrations', () => ({
  fetchApiKeys: vi.fn(),
  createApiKey: vi.fn(),
  revokeApiKey: vi.fn(),
  fetchWebhooks: vi.fn(),
  fetchEventTypes: vi.fn(),
  createWebhook: vi.fn(),
  deleteWebhook: vi.fn(),
  sendTestEvent: vi.fn(),
  fetchDeliveries: vi.fn(),
}));

vi.mock('../../hooks/useToast', () => ({
  useToast: () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }),
}));

/**
 * Dùng `fireEvent` chứ không phải `user-event`: gói đó chưa có trong dự án, và
 * thêm một phụ thuộc dev chỉ để bấm nút là cái giá không đáng. Các test sẵn có
 * (SecurityNotices) cũng dùng `fireEvent`.
 *
 * KHÔNG bọc lượt bấm trong `act(async ...)`. Bản đầu có bọc và cả bốn test đụng
 * tới nút đều treo tới hết 5 giây timeout — `fireEvent` đã tự bọc `act` cho
 * chính lượt bấm, còn phần chờ Promise thì `findBy*`/`waitFor` lo. Lồng thêm
 * một `act` bất đồng bộ nữa quanh chúng là chỗ treo.
 */

import IntegrationsPage from '../IntegrationsPage';
import {
  createApiKey,
  fetchApiKeys,
  fetchEventTypes,
  fetchWebhooks,
} from '../../api/integrations';

const EXISTING_KEY = {
  key_id: 'k-1',
  tenant_id: 't-1',
  name: 'đồng bộ đêm',
  prefix: 'voya_3f9a2b1c',
  scopes: 'read' as const,
  created_at: '2026-08-01T00:00:00Z',
  last_used_at: null,
  expires_at: null,
  revoked_at: null,
};

beforeEach(() => {
  vi.mocked(fetchApiKeys).mockResolvedValue([EXISTING_KEY]);
  vi.mocked(fetchWebhooks).mockResolvedValue([]);
  vi.mocked(fetchEventTypes).mockResolvedValue(['sample.created', 'training.completed']);
});

describe('IntegrationsPage — danh sách khoá', () => {
  it('listedKey_showsThePrefixAndNeverAFullKey', async () => {
    /**
     * Danh sách chỉ có prefix vì máy chủ không lưu gì khác. Nếu một ngày nào
     * đó ô này hiện được khoá đầy đủ, nghĩa là backend đã bắt đầu lưu khoá
     * nguyên văn — điều test này sẽ không bắt được, nhưng kiểu `ApiKey` không
     * có trường `key` thì trình biên dịch bắt được.
     */
    render(<IntegrationsPage />);

    expect(await screen.findByText('voya_3f9a2b1c…')).toBeInTheDocument();
  });
});

describe('IntegrationsPage — bí mật hiện một lần', () => {
  it('newlyCreatedKey_isShownInFull', async () => {
    vi.mocked(createApiKey).mockResolvedValue({
      key_id: 'k-2',
      prefix: 'voya_aabbccdd',
      scopes: 'read',
      name: '',
      key: 'voya_aabbccdd_secretsecretsecret',
    });

    render(<IntegrationsPage />);
    await screen.findByText('voya_3f9a2b1c…');
    fireEvent.click(screen.getByRole('button', { name: 'Cấp khoá mới' }));

    expect(
      await screen.findByText('voya_aabbccdd_secretsecretsecret'),
    ).toBeInTheDocument();
  });

  it('dismissButton_isDisabledUntilTheSecretIsCopied', async () => {
    /**
     * Cái chốt thật của thiết kế. Một dòng chữ nhỏ "hãy lưu lại" là cách chắc
     * chắn để người ta bỏ lỡ; nút đóng bị khoá thì không.
     */
    vi.mocked(createApiKey).mockResolvedValue({
      key_id: 'k-2',
      prefix: 'voya_aabbccdd',
      scopes: 'read',
      name: '',
      key: 'voya_aabbccdd_secretsecretsecret',
    });

    render(<IntegrationsPage />);
    await screen.findByText('voya_3f9a2b1c…');
    fireEvent.click(screen.getByRole('button', { name: 'Cấp khoá mới' }));

    expect(await screen.findByRole('button', { name: 'Tôi đã lưu' })).toBeDisabled();
  });

  it('afterCopying_theDismissButtonWorks', async () => {
    vi.mocked(createApiKey).mockResolvedValue({
      key_id: 'k-2',
      prefix: 'voya_aabbccdd',
      scopes: 'read',
      name: '',
      key: 'voya_aabbccdd_secretsecretsecret',
    });
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });

    render(<IntegrationsPage />);
    await screen.findByText('voya_3f9a2b1c…');
    fireEvent.click(screen.getByRole('button', { name: 'Cấp khoá mới' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Sao chép' }));

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Tôi đã lưu' })).toBeEnabled(),
    );
    expect(writeText).toHaveBeenCalledWith('voya_aabbccdd_secretsecretsecret');
  });

  it('clipboardUnavailable_doesNotThrowAndKeepsTheSecretSelectable', async () => {
    /**
     * `navigator.clipboard` KHÔNG tồn tại trong ngữ cảnh không bảo mật — đúng
     * cấu hình của bản triển khai CTU hiện tại (http, không phải localhost).
     * Nút sao chép phải xử lý được sự vắng mặt đó thay vì ném lỗi và làm trắng
     * hộp thoại đang giữ giá trị duy nhất người dùng có.
     */
    vi.mocked(createApiKey).mockResolvedValue({
      key_id: 'k-2',
      prefix: 'voya_aabbccdd',
      scopes: 'read',
      name: '',
      key: 'voya_aabbccdd_secretsecretsecret',
    });
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: undefined,
    });

    render(<IntegrationsPage />);
    await screen.findByText('voya_3f9a2b1c…');
    fireEvent.click(screen.getByRole('button', { name: 'Cấp khoá mới' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Sao chép' }));

    expect(
      screen.getByText('voya_aabbccdd_secretsecretsecret'),
    ).toBeInTheDocument();
  });
});

describe('IntegrationsPage — webhook', () => {
  it('eventTypeChips_comeFromTheServerNotAHardcodedList', async () => {
    /**
     * Danh sách chép cứng ở frontend sẽ lệch khỏi `EVENT_TYPES` của backend ở
     * lần thêm sự kiện tiếp theo, và người dùng đăng ký một tên không tồn tại
     * thì im lặng không nhận gì.
     */
    render(<IntegrationsPage />);

    expect(
      await screen.findByRole('button', { name: 'training.completed', pressed: false }),
    ).toBeInTheDocument();
  });

  it('emptyUrl_keepsTheCreateButtonDisabled', async () => {
    render(<IntegrationsPage />);

    expect(
      await screen.findByRole('button', { name: 'Thêm webhook' }),
    ).toBeDisabled();
  });
});
