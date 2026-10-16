import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { Link, MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { describe, it, expect, beforeEach, vi } from 'vitest';

/**
 * Trang đọc văn bản pháp lý.
 *
 * Trang này là đích của ô "Tôi đồng ý" ở biểu mẫu đăng ký. Trước đây `url`
 * trong bản ghi trỏ tới một file tĩnh chưa từng tồn tại, nên đường dẫn ấy là
 * 404 và ô tích kia là lời hứa suông — nên khẳng định đầu tiên là khẳng định
 * đơn giản nhất: bản văn phải hiện ra.
 *
 * `?version=` là mục đích cuối cùng của cả chuỗi phiên bản: một chấp thuận trỏ
 * tới `(loại, số hiệu)`, và nếu số hiệu ấy không mở ra được gì thì bản ghi chỉ
 * là một con số.
 */

vi.mock('../../api/legal', async () => {
  const actual = await vi.importActual<typeof import('../../api/legal')>(
    '../../api/legal',
  );
  return { ...actual, fetchContent: vi.fn(), fetchDocumentOrNull: vi.fn() };
});

import LegalDocumentPage from '../LegalDocumentPage';
import { fetchContent, fetchDocumentOrNull, type LegalDocumentContent } from '../../api/legal';

const DOC: LegalDocumentContent = {
  kind: 'terms',
  version: '2026-08-08',
  url: '/legal/terms',
  title: 'Điều khoản sử dụng',
  language: 'vi',
  effective_from: '2026-08-08T00:00:00Z',
  change_summary: '',
  content_hash: 'abc123def456789000000000000000000000000000000000000000000000beef',
  requires_reconsent: false,
  body: '# Điều khoản\n\nMục một nói về tài khoản.',
  body_format: 'markdown',
};

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/legal/:kind" element={<LegalDocumentPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('LegalDocumentPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchDocumentOrNull).mockResolvedValue(DOC);
  });

  it('dựng thân văn bản đã tải về', async () => {
    vi.mocked(fetchContent).mockResolvedValue(DOC);

    renderAt('/legal/terms');

    expect(await screen.findByText('Mục một nói về tài khoản.')).toBeInTheDocument();
  });

  it('hiện số hiệu phiên bản của bản đang đọc', async () => {
    vi.mocked(fetchContent).mockResolvedValue(DOC);

    renderAt('/legal/terms');

    expect(await screen.findByText(/Bản 2026-08-08/)).toBeInTheDocument();
  });

  it('bản đang đọc trùng bản đang áp dụng → nhãn "Đang áp dụng"', async () => {
    vi.mocked(fetchContent).mockResolvedValue(DOC);
    renderAt('/legal/terms');
    expect(await screen.findByText('Đang áp dụng')).toBeInTheDocument();
    expect(screen.queryByText('Bản cũ')).not.toBeInTheDocument();
  });

  it('mở một bản cũ → nói rõ là bản cũ và dẫn tới bản đang áp dụng', async () => {
    vi.mocked(fetchContent).mockResolvedValue({ ...DOC, version: '2026-01-01' });
    renderAt('/legal/terms?version=2026-01-01');
    expect(await screen.findByText('Bản cũ')).toBeInTheDocument();
    expect(screen.getByText(/Bản đang áp dụng là bản 2026-08-08/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Mở bản đang áp dụng' })).toHaveAttribute('href', '/legal/terms');
  });

  it('mục lục dựng từ tiêu đề markdown và trỏ đúng id', async () => {
    vi.mocked(fetchContent).mockResolvedValue({
      ...DOC,
      body: ["# Điều khoản", "", "## Phạm vi áp dụng", "", "Một.", "", "## Trách nhiệm của bạn", "", "Hai."].join(String.fromCharCode(10)),
    });
    renderAt('/legal/terms');
    await screen.findByText('Một.');
    const links = screen.getAllByRole('link', { name: 'Phạm vi áp dụng' });
    expect(links[0]).toHaveAttribute('href', '#pham-vi-ap-dung');
    expect(document.getElementById('pham-vi-ap-dung')?.tagName).toBe('H2');
  });

  it('một câu giải thích văn bản này nói về điều gì, bằng chữ thường', async () => {
    vi.mocked(fetchContent).mockResolvedValue(DOC);
    renderAt('/legal/privacy');
    expect(await screen.findByText(/thu thập những dữ liệu nào của bạn/)).toBeInTheDocument();
  });

  it('KHÔNG hiện mã băm trên trang văn bản', async () => {
    // Đổi ngày 20/08 theo yêu cầu sản phẩm. Mã băm vẫn được tính, vẫn lưu, và
    // `user_consents` vẫn ghi lại — thứ bị gỡ là MÀN HÌNH, không phải cơ chế.
    // Một chuỗi 64 ký tự hex giữa trang điều khoản không nói gì với người đọc
    // văn bản; ai cần đối chiếu thì đối chiếu qua API.
    //
    // Test giữ nguyên chứ không xoá: nó khoá lại QUYẾT ĐỊNH đó. Nếu mai kia mã
    // băm quay lại trang này thì phải là một lựa chọn có người ký tên, chứ
    // không phải một lần dán nhầm.
    vi.mocked(fetchContent).mockResolvedValue(DOC);

    renderAt('/legal/terms');

    await screen.findByText('Mục một nói về tài khoản.');
    expect(screen.queryByText(/abc123def456/)).not.toBeInTheDocument();
  });

  it('truyền ?version= xuống API để mở đúng bản đã ký', async () => {
    vi.mocked(fetchContent).mockResolvedValue({ ...DOC, version: '2026-01-01' });

    renderAt('/legal/terms?version=2026-01-01');

    await screen.findByText('Mục một nói về tài khoản.');
    expect(fetchContent).toHaveBeenCalledWith('terms', '2026-01-01');
  });

  it('nói rõ "chưa công bố" thay vì để trang trắng', async () => {
    vi.mocked(fetchContent).mockRejectedValue({ response: { status: 404 } });

    renderAt('/legal/privacy');

    expect(await screen.findByText(/chưa công bố văn bản này/i)).toBeInTheDocument();
  });

  it('nói rõ bản nào không tìm thấy khi hỏi một số hiệu cụ thể', async () => {
    vi.mocked(fetchContent).mockRejectedValue({ response: { status: 404 } });

    renderAt('/legal/terms?version=khong-co');

    expect(await screen.findByText(/Không tìm thấy bản khong-co/)).toBeInTheDocument();
  });

  it('mất mạng thì nói "không kết nối được", KHÔNG nói "chưa công bố" — LEG-03', async () => {
    // Lỗi không có phản hồi HTTP (axios Network Error) ≠ máy chủ trả 404.
    vi.mocked(fetchContent).mockRejectedValue(new Error('Network Error'));

    renderAt('/legal/privacy');

    expect(await screen.findByText(/Không kết nối được với máy chủ/)).toBeInTheDocument();
    expect(screen.queryByText(/chưa công bố/)).not.toBeInTheDocument();
  });

  it('không có quyền thì nói đúng như vậy', async () => {
    vi.mocked(fetchContent).mockRejectedValue({ response: { status: 403 } });
    renderAt('/legal/terms?version=2026-12-01');
    expect(await screen.findByText(/không có quyền xem bản này/)).toBeInTheDocument();
  });

  it('đổi sang bản lỗi thì KHÔNG còn thân của bản trước dưới tiêu đề mới — LEG-03', async () => {
    vi.mocked(fetchContent)
      .mockResolvedValueOnce(DOC)
      .mockRejectedValueOnce({ response: { status: 404 } });

    render(
      <MemoryRouter initialEntries={['/legal/terms']}>
        <Routes>
          <Route
            element={
              <>
                <Link to="/legal/terms?version=khong-co">mo ban khac</Link>
                <Outlet />
              </>
            }
          >
            <Route path="/legal/:kind" element={<LegalDocumentPage />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText(/Mục một nói về tài khoản/)).toBeInTheDocument();

    fireEvent.click(screen.getByText('mo ban khac'));

    expect(await screen.findByText(/Không tìm thấy bản khong-co/)).toBeInTheDocument();
    expect(screen.queryByText(/Mục một nói về tài khoản/)).not.toBeInTheDocument();
  });

  it('từ chối một loại văn bản không tồn tại mà không gọi API', async () => {
    renderAt('/legal/tu-nghi-ra');

    expect(await screen.findByText('Không có loại văn bản này.')).toBeInTheDocument();
    expect(fetchContent).not.toHaveBeenCalled();
  });

  it('hiện tóm tắt thay đổi khi bản mới có ghi', async () => {
    // Bắt người ta đồng ý lại mà không nói đổi cái gì thì họ bấm mà không đọc.
    vi.mocked(fetchContent).mockResolvedValue({
      ...DOC,
      change_summary: 'Bổ sung mục về xuất dữ liệu.',
    });

    renderAt('/legal/terms');

    expect(await screen.findByText('Bổ sung mục về xuất dữ liệu.')).toBeInTheDocument();
  });
});
