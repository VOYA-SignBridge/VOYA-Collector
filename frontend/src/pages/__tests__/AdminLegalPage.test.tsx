import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';

/**
 * Trang quản trị văn bản pháp lý.
 *
 * Bốn chỗ mà một lỗi hiển thị sẽ nói SAI về trạng thái tuân thủ:
 *
 *  - "đã lên lịch" bị vẽ thành "đang áp dụng" → người vận hành tưởng điều khoản
 *    đã đổi trong khi nó chưa;
 *  - "đã đồng ý" gộp cả dòng ghi hộ → bảng báo phủ 100% trong khi không ai bấm
 *    nút nào;
 *  - "chưa công bố" không nổi bật → trạng thái đó trông giống hệt chạy bình
 *    thường trên mọi màn hình khác;
 *  - sổ đăng bạ lỡ hiển thị nội dung văn bản → nhân bản một tài liệu có thể còn
 *    đang cấm phát hành sang một màn hình có quyền đọc khác.
 */

vi.mock('../../api/legal', async () => {
  const actual = await vi.importActual<typeof import('../../api/legal')>(
    '../../api/legal',
  );
  return {
    ...actual,
    fetchAdminOverview: vi.fn(),
    fetchAnyVersion: vi.fn(),
    fetchDrafts: vi.fn(),
    fetchDraft: vi.fn(),
    fetchEvents: vi.fn(),
    createDraft: vi.fn(),
  };
});

vi.mock('../../api/axiosClient', () => ({
  default: { post: vi.fn(), get: vi.fn() },
  getApiBaseURL: () => '/api',
}));

import AdminLegalPage from '../AdminLegalPage';
import { MemoryRouter } from 'react-router-dom';

/** Trang giờ chia mục theo `?tab=`; mỗi test mở thẳng mục nó cần. */
function show(tab?: 'overview' | 'compose' | 'versions' | 'consents' | 'events') {
  return render(
    <MemoryRouter initialEntries={[tab ? `/admin/legal?tab=${tab}` : '/admin/legal']}>
      <AdminLegalPage />
    </MemoryRouter>,
  );
}
import {
  createDraft,
  fetchAdminOverview,
  fetchAnyVersion,
  fetchDraft,
  fetchDrafts,
  fetchEvents,
  type LegalAdminOverview,
  type LegalDocumentRow,
  type LegalDraft,
  type LegalEvent,
} from '../../api/legal';

function row(over: Partial<LegalDocumentRow> = {}): LegalDocumentRow {
  return {
    doc_id: 'd1',
    kind: 'terms',
    version: '2026-08-08',
    url: '/legal/terms',
    title: 'Điều khoản',
    language: 'vi',
    effective_from: '2026-08-08T00:00:00Z',
    change_summary: '',
    content_hash: 'a'.repeat(64),
    requires_reconsent: false,
    body_length: 4200,
    is_effective: true,
    status: 'current' as const,
    consent_count: 3,
    published_at: '2026-08-08T00:00:00Z',
    published_by: null,
    ...over,
  };
}

function draft(over: Partial<LegalDraft> = {}): LegalDraft {
  return {
    draft_id: 'dr-1',
    kind: 'terms',
    title: 'Điều khoản',
    language: 'vi',
    body_format: 'markdown',
    change_summary: '',
    target_version: '2026-09-01',
    requires_reconsent: false,
    effective_from: null,
    status: 'draft',
    revision: 3,
    based_on_version: '2026-08-08',
    published_version: null,
    storage_key: null,
    content_hash: null,
    byte_size: 0,
    created_at: '2026-08-08T00:00:00Z',
    updated_at: '2026-08-08T10:00:00Z',
    body: '# Điều khoản\n\nĐoạn.',
    ...over,
  };
}

const OVERVIEW: LegalAdminOverview = {
  documents: [row()],
  kinds: ['terms', 'privacy', 'data_contribution', 'guardian'],
  required_at_registration: ['terms', 'privacy'],
  missing_required: ['privacy'],
  coverage: [
    { kind: 'terms', version: '2026-08-08', accounts: 10, accepted: 8, accepted_by_user: 2, missing: 2 },
    { kind: 'privacy', version: null, accounts: 10, accepted: 0, accepted_by_user: 0, missing: 10 },
  ],
};

const EVENTS: LegalEvent[] = [
  {
    event_id: 2,
    occurred_at: '2026-08-08T10:00:00Z',
    action: 'draft.update',
    kind: 'terms',
    version: null,
    draft_id: 'dr-1',
    revision: 3,
    storage_key: null,
    content_hash: null,
    detail: { fields: ['body'] },
    actor: 'quantri',
  },
];

describe('AdminLegalPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchAdminOverview).mockResolvedValue(OVERVIEW);
    vi.mocked(fetchDrafts).mockResolvedValue([]);
    vi.mocked(fetchEvents).mockResolvedValue(EVENTS);
    vi.mocked(fetchDraft).mockResolvedValue(draft());
  });

  it('Tổng quan: mỗi loại một thẻ — đang áp dụng / chưa công bố, bắt buộc thì đỏ', async () => {
    show();
    // Điều khoản: có bản hiện hành.
    const termsCard = (await screen.findByRole('heading', { name: 'Điều khoản sử dụng' })).closest('div')!.parentElement!;
    expect(termsCard).toHaveTextContent('đang áp dụng');
    expect(termsCard).toHaveTextContent('2026-08-08');
    // Quyền riêng tư: bắt buộc mà chưa có → nói thẳng hậu quả.
    const privacyCard = screen.getByRole('heading', { name: 'Chính sách quyền riêng tư' }).closest('div')!.parentElement!;
    expect(privacyCard).toHaveTextContent('chưa công bố');
    expect(privacyCard).toHaveTextContent(/Bắt buộc lúc đăng ký/);
  });

  it('năm mục là tab thật: có tablist, đổi mục bằng bấm', async () => {
    show();
    expect(await screen.findAllByRole('tab')).toHaveLength(5);
    fireEvent.click(screen.getByRole('tab', { name: /Lịch sử/ }));
    expect(await screen.findByText('Sổ đăng bạ')).toBeInTheDocument();
  });

  it('cảnh báo rõ loại văn bản bắt buộc còn thiếu', async () => {
    show('overview');

    expect(await screen.findByText(/Chưa công bố: Chính sách quyền riêng tư/)).toBeInTheDocument();
    expect(screen.getByText(/không thu chấp thuận nào/)).toBeInTheDocument();
  });

  it('tách "đã đồng ý" khỏi "người dùng tự bấm"', async () => {
    show('consents');

    await screen.findByText('Độ phủ chấp thuận');
    const cells = screen.getAllByRole('cell').map((c) => c.textContent);
    // 8 đã đồng ý nhưng chỉ 2 là chữ ký thật — hai con số phải cùng hiện.
    expect(cells).toContain('8');
    expect(cells).toContain('2');
  });

  it('gắn nhãn "đã lên lịch" cho bản chưa tới ngày hiệu lực', async () => {
    vi.mocked(fetchAdminOverview).mockResolvedValue({
      ...OVERVIEW,
      documents: [row({ is_effective: false, status: 'scheduled', version: '2026-12-01' })],
    });

    show('versions');

    expect(await screen.findByText('đã lên lịch')).toBeInTheDocument();
    expect(screen.queryByText('đang áp dụng')).not.toBeInTheDocument();
  });

  it('bản quá khứ đã bị thay thế KHÔNG được gắn "đang áp dụng" — LEG-02', async () => {
    // Bản trước suy trạng thái từ `effective_from <= now()`, nên hai bản quá
    // khứ cùng hiện "đang áp dụng" — người quản trị không biết bản nào đang
    // được phục vụ. Trạng thái do máy chủ tính bằng đúng quy tắc phục vụ.
    vi.mocked(fetchAdminOverview).mockResolvedValue({
      ...OVERVIEW,
      documents: [
        row({ status: 'current', version: '2026-08-08' }),
        row({ doc_id: 'd-old', status: 'superseded', version: '2026-01-01' }),
      ],
    });

    show('versions');

    expect(await screen.findByText('đang áp dụng')).toBeInTheDocument();
    expect(screen.getAllByText('đang áp dụng')).toHaveLength(1);
    expect(screen.getByText('đã thay thế')).toBeInTheDocument();
  });

  it('nút "Xem" của bản TỆP dựng trình đọc tệp, không phải markdown trống — LEG-01', async () => {
    vi.mocked(fetchAdminOverview).mockResolvedValue({
      ...OVERVIEW,
      documents: [row({ has_file: true, file_name: 'dieu-khoan.pdf', file_mime: 'application/pdf', file_size: 1234 })],
    });
    vi.mocked(fetchAnyVersion).mockResolvedValue({
      ...row({ has_file: true, file_name: 'dieu-khoan.pdf', file_mime: 'application/pdf', file_size: 1234 }),
      body: '',
      body_format: 'file',
    } as any);

    show('versions');
    fireEvent.click(await screen.findByRole('button', { name: /Xem/ }));

    // Trình đọc tệp: tên tệp + nút tải bản gốc, và đường tải là đường QUẢN TRỊ
    // (bản đã lên lịch cũng mở được), không phải đường công khai.
    expect(await screen.findByText('dieu-khoan.pdf')).toBeInTheDocument();
    const link = screen.getAllByRole('link', { name: /Tải bản gốc/ })[0];
    expect(link.getAttribute('href')).toContain('/admin/legal/documents/terms/2026-08-08/file');
  });

  it('không có nút sửa bản đã công bố', async () => {
    // Sửa một bản đã công bố là viết lại bản văn nằm dưới những chữ ký đã thu;
    // cơ sở dữ liệu chặn việc đó. Một nút đi tới bức tường ấy chỉ để nhận lỗi
    // là thiết kế mời người ta thử.
    show('versions');
    await screen.findByText('Các bản đã công bố');

    expect(screen.queryByRole('button', { name: /Sửa/ })).not.toBeInTheDocument();
  });

  it('không còn đường công bố thẳng — chỉ soạn qua bản nháp', async () => {
    // Biểu mẫu dán-nội-dung-rồi-Công-bố đã bị gỡ: một bản văn pháp lý ra khỏi
    // tay một người mà không ai đọc lại là đúng thứ quy trình tồn tại để chặn.
    show('compose');
    await screen.findByText('Bản nháp');

    expect(screen.queryByRole('button', { name: 'Công bố' })).not.toBeInTheDocument();
  });

  it('mở bản nháp mới và hiển thị trình soạn thảo', async () => {
    vi.mocked(createDraft).mockResolvedValue(draft({ status: 'draft' }));
    show('compose');
    await screen.findByText('Bản nháp');

    fireEvent.click(screen.getByRole('button', { name: 'Soạn bản mới' }));

    await waitFor(() => expect(createDraft).toHaveBeenCalledWith('terms', true));
    expect(await screen.findByLabelText('Nội dung')).toBeInTheDocument();
  });

  it('liệt kê bản nháp đang mở kèm trạng thái và số hiệu bản ghi', async () => {
    vi.mocked(fetchDrafts).mockResolvedValue([draft({ body: undefined, body_length: 19 })]);

    show('compose');

    // Truy theo NÚT của bản nháp, không truy theo chữ rời: `#3` cũng xuất hiện
    // trong sổ đăng bạ bên dưới, và một phép tìm mơ hồ sẽ đỏ vì lý do không
    // liên quan tới thứ test này đang kiểm.
    const entry = await screen.findByRole('button', { name: /2026-09-01/ });
    expect(entry).toHaveTextContent('Đang soạn');
    expect(entry).toHaveTextContent('#3');
  });

  it('dựng sổ đăng bạ với hành động và người thực hiện', async () => {
    show('events');

    expect(await screen.findByText('draft.update')).toBeInTheDocument();
    expect(screen.getByText('quantri')).toBeInTheDocument();
  });

  it('sổ đăng bạ không hiển thị nội dung văn bản', async () => {
    // Sổ chỉ mang TÊN trường đã đổi, không mang giá trị. Nếu giao diện lỡ dựng
    // `detail` thô ra màn hình thì mọi bảo đảm ở backend thành vô nghĩa.
    vi.mocked(fetchEvents).mockResolvedValue([
      { ...EVENTS[0], detail: { fields: ['body'] } },
    ]);

    show('events');

    await screen.findByText('draft.update');
    expect(screen.queryByText(/Đoạn\./)).not.toBeInTheDocument();
  });
});
