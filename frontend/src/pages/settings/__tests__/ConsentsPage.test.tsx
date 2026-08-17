import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, beforeEach, vi } from 'vitest';

/**
 * Trang "Đồng thuận của tôi" — /settings/consents.
 *
 * Tách khỏi AccountPage.test.tsx ngày 16/08/2026, cùng lúc với việc tách chính
 * màn hình: ký hay rút một văn bản pháp lý và sửa tên đăng nhập không cùng một
 * nhịp, nên chúng không nên chung một trang — và bộ test đi theo màn hình chứ
 * không đi theo lịch sử tệp.
 *
 * Màn hình này là mắt xích cuối của một chuỗi đã hoàn chỉnh ở mọi mắt khác:
 * bảng signer_consents có từ v3.4, cổng đồng thuận đọc nó, ba endpoint đã sống
 * — và không màn hình nào gọi tới. Kết quả đo được: 10 tài khoản đã ký lúc đăng
 * ký, signer_consents 0 dòng, mọi bản phát hành nghiên cứu rỗng.
 *
 * Vì thế các khẳng định dưới đây canh những chỗ mà một trang "trông đúng" vẫn
 * có thể nói dối: gửi nhầm số hiệu bản, gộp hai trạng thái khác nhau vào một
 * chữ, hoặc hứa một hệ quả mà cơ chế không làm.
 */

vi.mock('../../../api/legal', async () => {
  const actual = await vi.importActual<typeof import('../../../api/legal')>(
    '../../../api/legal',
  );
  return {
    ...actual,
    fetchMyConsents: vi.fn(),
    acceptDocument: vi.fn(),
    withdrawDocument: vi.fn(),
  };
});

const toast = { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() };
vi.mock('../../../hooks/useToast', () => ({ useToast: () => ({ toast }) }));

import ConsentsPage from '../ConsentsPage';
import {
  acceptDocument,
  fetchMyConsents,
  withdrawDocument,
  type MyConsent,
} from '../../../api/legal';

function consent(over: Partial<MyConsent> = {}): MyConsent {
  return {
    kind: 'data_contribution',
    title: 'Đồng ý đóng góp dữ liệu',
    current_version: '2026-08-08',
    accepted: false,
    accepted_version: null,
    accepted_at: null,
    needs_reconsent: false,
    required_at_registration: false,
    self_signable: true,
    withdrawable: true,
    grants_scope: 'internal_training',
    ...over,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ConsentsPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('Ký một văn bản', () => {
  it('khoá nút ký cho tới khi người dùng xác nhận đã đọc', async () => {
    vi.mocked(fetchMyConsents).mockResolvedValue([consent()]);
    renderPage();

    const button = await screen.findByRole('button', { name: 'Ghi nhận đồng ý' });
    expect(button).toBeDisabled();

    fireEvent.click(screen.getByRole('checkbox'));
    expect(button).toBeEnabled();
  });

  it('gửi bản ĐANG hiệu lực, không phải bản đã ký trước đó', async () => {
    // Máy chủ đối chiếu với bản hiện hành và trả 409 `stale_version` nếu lệch.
    // Gửi `accepted_version` là xin ghi chữ ký cho một bản văn đã bị thay thế —
    // đúng thứ mà `record_consent` tồn tại để từ chối.
    vi.mocked(fetchMyConsents).mockResolvedValue([
      consent({
        accepted: false,
        needs_reconsent: true,
        accepted_version: '2026-01-01',
        accepted_at: '2026-01-01T00:00:00Z',
        current_version: '2026-08-08',
      }),
    ]);
    vi.mocked(acceptDocument).mockResolvedValue({
      kind: 'data_contribution',
      accepted: true,
      version: '2026-08-08',
    });
    renderPage();

    fireEvent.click(await screen.findByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'Ghi nhận đồng ý' }));

    await waitFor(() => expect(acceptDocument).toHaveBeenCalled());
    expect(vi.mocked(acceptDocument).mock.calls[0]).toEqual([
      'data_contribution',
      '2026-08-08',
    ]);
  });

  it('bỏ tích và nạp lại khi máy chủ từ chối', async () => {
    // Giữ nguyên ô tích sau một lượt 409 là mời người dùng bấm lại lần nữa cho
    // một bản văn họ chưa đọc.
    vi.mocked(fetchMyConsents).mockResolvedValue([consent()]);
    vi.mocked(acceptDocument).mockRejectedValue({
      response: { status: 409, data: { detail: { code: 'stale_version' } } },
    });
    renderPage();

    fireEvent.click(await screen.findByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'Ghi nhận đồng ý' }));

    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    expect(fetchMyConsents).toHaveBeenCalledTimes(2);
  });

  it('nói ra mức mà chữ ký này cấp, và mức nó KHÔNG cấp', async () => {
    // Bản văn `data_contribution` mục 4 tách "Có" khỏi "chỉ khi đồng ý riêng
    // bằng văn bản". Một nút "Đồng ý" trơ trọi biến một lần bấm thành giấy phép
    // công bố khuôn mặt người ta.
    vi.mocked(fetchMyConsents).mockResolvedValue([consent()]);
    renderPage();

    expect(
      await screen.findByText(/Huấn luyện nội bộ trong tổ chức của bạn/),
    ).toBeInTheDocument();
    expect(screen.getByText(/cần một thoả thuận riêng bằng văn bản/)).toBeInTheDocument();
  });
});

describe('Ba trạng thái, ba câu', () => {
  it('phân biệt "chưa ký bao giờ" với "đã ký bản cũ"', async () => {
    // Gộp hai trạng thái này lại là nói với người đã từng đồng ý rằng họ chưa
    // từng làm vậy.
    vi.mocked(fetchMyConsents).mockResolvedValue([
      consent({ needs_reconsent: true, accepted_version: '1.0' }),
    ]);
    renderPage();

    expect(await screen.findByText('Cần đồng ý lại')).toBeInTheDocument();
    expect(screen.queryByText('Chưa đồng ý')).not.toBeInTheDocument();
  });

  it('mở lại đúng bản mình đã ký, kèm số hiệu', async () => {
    // Đây là lý do cả chuỗi phiên bản tồn tại: một bản ghi chấp thuận trỏ tới
    // (loại, số hiệu), và nếu số hiệu ấy không mở ra được gì thì bản ghi chỉ là
    // một con số.
    vi.mocked(fetchMyConsents).mockResolvedValue([
      consent({ accepted: true, accepted_version: '2026-01-01' }),
    ]);
    renderPage();

    expect(await screen.findByRole('link', { name: '2026-01-01' })).toHaveAttribute(
      'href',
      '/legal/data_contribution?version=2026-01-01',
    );
  });
});

describe('Văn bản hỏi theo từng buổi ghi hình', () => {
  it('không mời ký một lần cho cả tài khoản', async () => {
    // Bản `guardian` tự nói: "mỗi buổi thu là một lần bạn biết cụ thể hôm nay
    // con em mình làm gì". Một ô tích vĩnh viễn ở đây thu đúng thứ nó từ chối.
    vi.mocked(fetchMyConsents).mockResolvedValue([
      consent({
        kind: 'guardian',
        title: 'Đồng ý của người giám hộ',
        self_signable: false,
        withdrawable: false,
        grants_scope: null,
      }),
    ]);
    renderPage();

    expect(await screen.findByText(/từng buổi ghi hình/)).toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Ghi nhận đồng ý' }),
    ).not.toBeInTheDocument();
    // Và không gắn cho nó một việc còn nợ mà người dùng không làm được ở đây.
    expect(screen.queryByText('Chưa đồng ý')).not.toBeInTheDocument();
  });
});

describe('Rút đồng ý', () => {
  it('không hiện nút rút khi máy chủ nói không rút được', async () => {
    // `withdrawable` đến TỪ MÁY CHỦ. Giao diện tự suy từ tên văn bản sẽ có ngày
    // hiện một cái nút chắc chắn trả 409.
    vi.mocked(fetchMyConsents).mockResolvedValue([
      consent({
        kind: 'terms',
        accepted: true,
        accepted_version: '1.0',
        required_at_registration: true,
        withdrawable: false,
        grants_scope: null,
      }),
    ]);
    renderPage();

    await screen.findByText('Đã đồng ý');
    expect(screen.queryByRole('button', { name: 'Rút đồng ý' })).not.toBeInTheDocument();
    expect(screen.getByText(/không rút riêng được/)).toBeInTheDocument();
  });

  it('đòi một bước xác nhận, và không hứa xoá dữ liệu', async () => {
    // Cơ chế chặn lượt chọn TIẾP THEO; nó không xoá tệp đã có. Hứa xoá ở đây là
    // hứa một việc hệ thống không làm.
    vi.mocked(fetchMyConsents).mockResolvedValue([
      consent({ accepted: true, accepted_version: '2026-08-08' }),
    ]);
    vi.mocked(withdrawDocument).mockResolvedValue({
      kind: 'data_contribution',
      accepted: false,
      withdrawn: true,
    });
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Rút đồng ý' }));
    expect(withdrawDocument).not.toHaveBeenCalled();

    expect(screen.getByText(/không bị xoá/)).toBeInTheDocument();
    expect(screen.getByText(/mọi mức/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận rút' }));
    await waitFor(() => expect(withdrawDocument).toHaveBeenCalledWith('data_contribution'));
  });

  it('bấm "Giữ nguyên" thì không gọi gì cả', async () => {
    vi.mocked(fetchMyConsents).mockResolvedValue([
      consent({ accepted: true, accepted_version: '2026-08-08' }),
    ]);
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Rút đồng ý' }));
    fireEvent.click(screen.getByRole('button', { name: 'Giữ nguyên' }));

    expect(withdrawDocument).not.toHaveBeenCalled();
    expect(screen.queryByText(/không bị xoá/)).not.toBeInTheDocument();
  });
});
