import '@testing-library/jest-dom/vitest';
import { render, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useState } from 'react';
import { useBackClosesOverlay } from '../useBackClosesOverlay';

/**
 * Nút QUAY LẠI phải ĐÓNG lớp phủ, không được rời khỏi trang.
 *
 * Lỗi thật: modal thu hình mở/đóng bằng biến trạng thái React, thứ trình duyệt
 * không biết. Người dùng đang thu dở bấm quay lại — phản xạ tự nhiên để thoát
 * khỏi cái đang chiếm toàn màn hình, và trên Android là nút hệ thống — thì
 * trình duyệt làm đúng thứ nó biết: rời khỏi /upload. Cả phiên thu mất, kể cả
 * những lần đã xong nhưng chưa gửi.
 *
 * jsdom có History API thật nên popstate mô phỏng được; điều duy nhất phải làm
 * thủ công là bắn sự kiện, vì jsdom không tự bắn khi gọi history.back().
 */

function Harness({
  open,
  onClose,
  reopenOnClose = false,
}: {
  open: boolean;
  onClose: () => void;
  reopenOnClose?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(open);
  useBackClosesOverlay(isOpen, () => {
    onClose();
    // `reopenOnClose` mô phỏng người dùng HUỶ hộp thoại xác nhận: đóng được
    // gọi, nhưng lớp phủ vẫn mở.
    if (!reopenOnClose) setIsOpen(false);
  });
  return <div data-testid="overlay">{isOpen ? 'open' : 'closed'}</div>;
}

function popBack() {
  // jsdom không bắn popstate khi history.back() được gọi trong cùng tick, nên
  // test bắn tay — đúng thứ trình duyệt sẽ làm.
  window.dispatchEvent(new PopStateEvent('popstate', { state: null }));
}

describe('useBackClosesOverlay', () => {
  beforeEach(() => {
    window.history.replaceState(null, '', '/upload');
  });

  it('đẩy một mục lịch sử khi lớp phủ mở', () => {
    const before = window.history.length;
    render(<Harness open onClose={() => {}} />);
    expect(window.history.length).toBeGreaterThan(before);
  });

  it('nút quay lại gọi đóng thay vì để trang điều hướng', () => {
    const onClose = vi.fn();
    const { getByTestId } = render(<Harness open onClose={onClose} />);

    act(() => popBack());

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(getByTestId('overlay')).toHaveTextContent('closed');
    // Đường dẫn KHÔNG đổi: người dùng vẫn ở trang thu, chỉ lớp phủ đóng lại.
    expect(window.location.pathname).toBe('/upload');
  });

  it('không làm gì khi lớp phủ đang đóng', () => {
    const onClose = vi.fn();
    render(<Harness open={false} onClose={onClose} />);
    act(() => popBack());
    expect(onClose).not.toHaveBeenCalled();
  });

  it('đặt LẠI mục lịch sử khi người dùng huỷ hộp thoại xác nhận', async () => {
    /**
     * Cạnh khó nhất, và là chỗ một bản cài đặt ngây thơ sẽ sai.
     *
     * `handleClose` của modal hỏi lại khi đang thu dở. Chọn "ở lại" thì modal
     * không đóng — nhưng mục lịch sử đã bị nút quay lại tiêu mất. Không đặt
     * lại thì lần bấm sau rời khỏi trang thật: cái phanh chỉ hoạt động đúng
     * một lần.
     */
    const onClose = vi.fn();
    const { getByTestId } = render(
      <Harness open onClose={onClose} reopenOnClose />,
    );

    act(() => popBack());
    expect(getByTestId('overlay')).toHaveTextContent('open');

    // Việc đặt lại nằm trong setTimeout(0) vì đóng đi qua setState và giá trị
    // chỉ phản ánh ở lượt render sau.
    const lengthBefore = window.history.length;
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 5));
    });
    expect(window.history.length).toBeGreaterThanOrEqual(lengthBefore);

    // Lần bấm thứ hai vẫn phải được lớp phủ ăn, không rời trang.
    act(() => popBack());
    expect(onClose).toHaveBeenCalledTimes(2);
    expect(window.location.pathname).toBe('/upload');
  });

  it('gỡ listener trước khi tự gỡ mục lịch sử lúc dọn dẹp', () => {
    /**
     * `history.back()` trong hàm dọn dẹp cũng bắn popstate. Nếu listener chưa
     * được gỡ, nó gọi đóng thêm một lần nữa cho một lớp phủ vốn đã đóng — và
     * với modal thu hình, "đóng" kéo theo dừng camera và hỏi lại người dùng.
     */
    const onClose = vi.fn();
    const { unmount } = render(<Harness open onClose={onClose} />);
    unmount();
    act(() => popBack());
    expect(onClose).not.toHaveBeenCalled();
  });
});
