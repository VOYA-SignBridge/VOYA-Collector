import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';

/**
 * Trình soạn thảo bản nháp.
 *
 * Khẳng định quan trọng nhất ở đây không phải về soạn thảo mà về **cách xử lý
 * xung đột ghi**: khi có người lưu trước, đoạn người dùng vừa gõ phải CÒN
 * NGUYÊN. Cách hỏng mặc định — hiện "Lưu thất bại, tải lại trang" — là vứt đi
 * vài nghìn chữ, và không có test thì không ai phát hiện cho tới khi mất thật.
 *
 * Nhóm thứ hai canh bảng chuyển trạng thái: nút nào hiện ra ở trạng thái nào.
 * Một nút "Phê duyệt" hiện ngay ở bản nháp là bỏ qua bước rà soát bằng giao
 * diện, dù backend vẫn chặn.
 */

vi.mock('../../../api/legal', async () => {
  const actual = await vi.importActual<typeof import('../../../api/legal')>(
    '../../../api/legal',
  );
  return {
    ...actual,
    saveDraft: vi.fn(),
    setDraftStatus: vi.fn(),
    publishDraft: vi.fn(),
    fetchDraft: vi.fn(),
  };
});

import DraftEditor from '../DraftEditor';
import {
  RevisionConflict,
  fetchDraft,
  publishDraft,
  saveDraft,
  setDraftStatus,
  type LegalDraft,
} from '../../../api/legal';

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
    body: '# Điều khoản\n\nĐoạn một.',
    ...over,
  };
}

function renderEditor(over: Partial<LegalDraft> = {}, props: Partial<{
  onChanged: (d: LegalDraft) => void;
  onPublished: (m: string) => void;
  ensureSudo: () => Promise<boolean>;
}> = {}) {
  const onChanged = props.onChanged ?? vi.fn();
  const onPublished = props.onPublished ?? vi.fn();
  const ensureSudo = props.ensureSudo ?? vi.fn().mockResolvedValue(true);
  const d = draft(over);
  render(
    <DraftEditor
      draft={d}
      onChanged={onChanged}
      onPublished={onPublished}
      ensureSudo={ensureSudo}
    />,
  );
  return { draft: d, onChanged, onPublished, ensureSudo };
}

function typeBody(text: string) {
  fireEvent.change(screen.getByLabelText('Nội dung'), { target: { value: text } });
}

describe('DraftEditor — lưu bài', () => {
  beforeEach(() => vi.clearAllMocks());

  it('gửi kèm đúng số hiệu bản đang giữ', async () => {
    // Không có con số này thì máy chủ không phân biệt được "ghi lên bản tôi vừa
    // đọc" với "ghi đè lên bản người khác vừa lưu".
    vi.mocked(saveDraft).mockResolvedValue(draft({ revision: 4 }));
    renderEditor();

    typeBody('# Sửa');
    fireEvent.click(screen.getByRole('button', { name: 'Lưu' }));

    await waitFor(() => expect(saveDraft).toHaveBeenCalled());
    expect(vi.mocked(saveDraft).mock.calls[0][1]).toBe(3);
  });

  it('khoá nút Lưu khi chưa sửa gì', () => {
    renderEditor();

    expect(screen.getByRole('button', { name: 'Lưu' })).toBeDisabled();
  });

  it('mở khoá nút Lưu ngay khi nội dung đổi', () => {
    renderEditor();

    typeBody('# Đã sửa');

    expect(screen.getByRole('button', { name: 'Lưu' })).toBeEnabled();
  });
});

describe('DraftEditor — xung đột ghi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchDraft).mockResolvedValue(
      draft({ revision: 9, body: '# Bản của người khác' }),
    );
  });

  it('GIỮ NGUYÊN bài đang gõ khi máy chủ báo xung đột', async () => {
    // Đây là khẳng định trung tâm của cả tệp.
    vi.mocked(saveDraft).mockRejectedValue(new RevisionConflict('Có người vừa lưu.', 9));
    renderEditor();

    typeBody('# Bài của tôi, không được mất');
    fireEvent.click(screen.getByRole('button', { name: 'Lưu' }));

    await screen.findByText(/Có người vừa lưu/);
    expect(screen.getByLabelText('Nội dung')).toHaveValue(
      '# Bài của tôi, không được mất',
    );
  });

  it('cho xem bản đang có trên máy chủ để tự hợp nhất', async () => {
    vi.mocked(saveDraft).mockRejectedValue(new RevisionConflict('Có người vừa lưu.', 9));
    renderEditor();

    typeBody('# Bài của tôi');
    fireEvent.click(screen.getByRole('button', { name: 'Lưu' }));

    await screen.findByText(/Có người vừa lưu/);
    expect(await screen.findByText('# Bản của người khác')).toBeInTheDocument();
  });

  it('không tự trộn hai bản — nói rõ đó là việc của con người', async () => {
    vi.mocked(saveDraft).mockRejectedValue(new RevisionConflict('Có người vừa lưu.', 9));
    renderEditor();

    typeBody('# Bài của tôi');
    fireEvent.click(screen.getByRole('button', { name: 'Lưu' }));

    expect(await screen.findByText(/không tự trộn hai bản văn pháp lý/)).toBeInTheDocument();
  });

  it('nạp số hiệu mới mà không đụng vào ô soạn thảo', async () => {
    vi.mocked(saveDraft).mockRejectedValue(new RevisionConflict('Có người vừa lưu.', 9));
    const onChanged = vi.fn();
    renderEditor({}, { onChanged });

    typeBody('# Bài của tôi');
    fireEvent.click(screen.getByRole('button', { name: 'Lưu' }));
    await screen.findByText(/Có người vừa lưu/);
    fireEvent.click(
      screen.getByRole('button', { name: /Nạp số hiệu mới/ }),
    );

    await waitFor(() => expect(onChanged).toHaveBeenCalled());
    expect(onChanged.mock.calls[0][0].revision).toBe(9);
  });

  it('hiện lỗi thường mà KHÔNG bật màn hình xung đột', async () => {
    // Phản chứng: nếu mọi lỗi đều thành "xung đột", người dùng sẽ đi tìm một
    // người đồng nghiệp không tồn tại thay vì đọc thông báo thật.
    vi.mocked(saveDraft).mockRejectedValue({
      response: { data: { detail: { message: 'Số hiệu phiên bản để trống.' } } },
    });
    renderEditor();

    typeBody('# x');
    fireEvent.click(screen.getByRole('button', { name: 'Lưu' }));

    expect(await screen.findByText('Số hiệu phiên bản để trống.')).toBeInTheDocument();
    expect(screen.queryByText(/Xem bản đang có trên máy chủ/)).not.toBeInTheDocument();
  });
});

describe('DraftEditor — bảng chuyển trạng thái', () => {
  beforeEach(() => vi.clearAllMocks());

  it('ở trạng thái soạn chỉ cho gửi rà soát hoặc huỷ', () => {
    renderEditor({ status: 'draft' });

    expect(screen.getByRole('button', { name: 'Đang rà soát' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Đã huỷ' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Đã phê duyệt' })).not.toBeInTheDocument();
  });

  it('chỉ hiện nút Công bố khi đã phê duyệt', () => {
    renderEditor({ status: 'approved' });

    expect(screen.getByRole('button', { name: 'Công bố' })).toBeInTheDocument();
  });

  it('khoá ô soạn thảo sau khi đã phê duyệt', () => {
    // Bản đã duyệt là hiện vật người duyệt đã đọc. Sửa tiếp mà giữ nguyên trạng
    // thái "đã phê duyệt" nghĩa là công bố một bản không ai duyệt.
    renderEditor({ status: 'approved' });

    expect(screen.getByLabelText('Nội dung')).toBeDisabled();
  });

  it('chặn đổi trạng thái khi còn thay đổi chưa lưu', () => {
    renderEditor({ status: 'draft' });

    typeBody('# Vừa gõ, chưa lưu');

    expect(screen.getByRole('button', { name: 'Đang rà soát' })).toBeDisabled();
  });

  it('gửi số hiệu bản khi đổi trạng thái', async () => {
    vi.mocked(setDraftStatus).mockResolvedValue(draft({ status: 'in_review', revision: 4 }));
    renderEditor({ status: 'draft' });

    fireEvent.click(screen.getByRole('button', { name: 'Đang rà soát' }));

    await waitFor(() => expect(setDraftStatus).toHaveBeenCalledWith('dr-1', 3, 'in_review'));
  });
});

describe('DraftEditor — công bố', () => {
  beforeEach(() => vi.clearAllMocks());

  it('xin nâng quyền rồi thử lại khi máy chủ đòi', async () => {
    vi.mocked(publishDraft)
      .mockRejectedValueOnce({ response: { data: { detail: { code: 'sudo_required' } } } })
      .mockResolvedValueOnce({
        draft: draft({ status: 'published', published_version: '2026-09-01' }),
        current: null,
      });
    const ensureSudo = vi.fn().mockResolvedValue(true);
    renderEditor({ status: 'approved' }, { ensureSudo });

    fireEvent.click(screen.getByRole('button', { name: 'Công bố' }));

    await waitFor(() => expect(ensureSudo).toHaveBeenCalled());
    expect(vi.mocked(publishDraft)).toHaveBeenCalledTimes(2);
  });

  it('dừng lại khi người dùng bỏ dở bước nhập mật khẩu', async () => {
    vi.mocked(publishDraft).mockRejectedValueOnce({
      response: { data: { detail: { code: 'sudo_required' } } },
    });
    const ensureSudo = vi.fn().mockResolvedValue(false);
    const onPublished = vi.fn();
    renderEditor({ status: 'approved' }, { ensureSudo, onPublished });

    fireEvent.click(screen.getByRole('button', { name: 'Công bố' }));

    await waitFor(() => expect(ensureSudo).toHaveBeenCalled());
    expect(vi.mocked(publishDraft)).toHaveBeenCalledTimes(1);
    expect(onPublished).not.toHaveBeenCalled();
  });

  it('nói "đã lên lịch" chứ không nói "đã áp dụng" khi hẹn giờ tương lai', async () => {
    vi.mocked(publishDraft).mockResolvedValue({
      draft: draft({ status: 'published', published_version: '2026-12-01' }),
      current: {
        kind: 'terms',
        version: '2026-08-08',
        url: '/legal/terms',
        title: 'Điều khoản',
        language: 'vi',
        effective_from: '2026-08-08T00:00:00Z',
        change_summary: '',
        content_hash: 'a'.repeat(64),
        requires_reconsent: false,
      },
    });
    const onPublished = vi.fn();
    renderEditor({ status: 'approved' }, { onPublished });

    fireEvent.click(screen.getByRole('button', { name: 'Công bố' }));

    await waitFor(() => expect(onPublished).toHaveBeenCalled());
    expect(onPublished.mock.calls[0][0]).toMatch(/Đã lên lịch bản 2026-12-01/);
    expect(onPublished.mock.calls[0][0]).toMatch(/vẫn là 2026-08-08/);
  });
});

describe('DraftEditor — xem trước', () => {
  beforeEach(() => vi.clearAllMocks());

  it('dựng markdown của phần đang gõ, không phải phần đã lưu', async () => {
    renderEditor();

    typeBody('# Tiêu đề đang gõ');
    fireEvent.click(screen.getByRole('button', { name: 'Xem trước' }));

    expect(
      await screen.findByRole('heading', { name: 'Tiêu đề đang gõ' }),
    ).toBeInTheDocument();
  });
});
