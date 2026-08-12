import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import RouteErrorBoundary from '../RouteErrorBoundary';

/**
 * Sau mỗi lần triển khai, nút QUAY LẠI hay làm trắng màn hình.
 *
 * Nguyên nhân: mọi trang đều `lazy(() => import(...))`, tên tệp chunk mang hash
 * nội dung, nên triển khai mới xoá sạch tên cũ. Một tab mở TRƯỚC lúc triển khai
 * vẫn giữ bản đồ chunk cũ; bấm quay lại về một trang chưa mở trong phiên này
 * thì trình duyệt xin đúng tệp đã biến mất, nginx trả 404, `import()` bị từ
 * chối — và không có error boundary nào, nên React gỡ cả cây.
 *
 * Quay lại là đường hay gặp nhất vì nó chuyển trang mà KHÔNG tải lại tài liệu.
 */

const reloadSpy = vi.fn();
const originalLocation = Object.getOwnPropertyDescriptor(window, 'location');

function Boom({ message }: { message: string }) {
  throw new Error(message);
}

beforeEach(() => {
  reloadSpy.mockClear();
  sessionStorage.clear();
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: { ...window.location, reload: reloadSpy },
  });
  // React in ra console.error cho mọi lỗi bị boundary bắt; im nó đi để kết quả
  // test đọc được, chứ không phải vì lỗi không đáng quan tâm.
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  if (originalLocation) Object.defineProperty(window, 'location', originalLocation);
  vi.restoreAllMocks();
});

describe('RouteErrorBoundary', () => {
  it('cho nội dung bình thường đi qua', () => {
    render(
      <RouteErrorBoundary>
        <div>nội dung</div>
      </RouteErrorBoundary>,
    );
    expect(screen.getByText('nội dung')).toBeInTheDocument();
  });

  it('tự nạp lại MỘT lần khi chunk cũ không tải được', () => {
    render(
      <RouteErrorBoundary>
        <Boom message="Failed to fetch dynamically imported module: /assets/x-a1b2.js" />
      </RouteErrorBoundary>,
    );
    expect(reloadSpy).toHaveBeenCalledTimes(1);
    expect(sessionStorage.getItem('voya:chunk-reload')).toBe('1');
  });

  it('KHÔNG nạp lại lần thứ hai — cờ trong sessionStorage cắt vòng lặp', () => {
    /**
     * Nếu nguyên nhân không phải chunk cũ mà là lỗi thật trong mã trang, tự
     * nạp lại sẽ thành vòng vô tận: hỏng, nạp lại, hỏng, nạp lại. Cờ phải nằm
     * ở sessionStorage chứ không phải một biến, vì nạp lại xoá sạch bộ nhớ và
     * một biến sẽ luôn thấy "lần đầu".
     */
    sessionStorage.setItem('voya:chunk-reload', '1');
    render(
      <RouteErrorBoundary>
        <Boom message="Failed to fetch dynamically imported module: /assets/x-a1b2.js" />
      </RouteErrorBoundary>,
    );
    expect(reloadSpy).not.toHaveBeenCalled();
    expect(screen.getByText('Ứng dụng vừa được cập nhật')).toBeInTheDocument();
  });

  it('không nạp lại với một lỗi ứng dụng bình thường', () => {
    render(
      <RouteErrorBoundary>
        <Boom message="Cannot read properties of undefined" />
      </RouteErrorBoundary>,
    );
    expect(reloadSpy).not.toHaveBeenCalled();
    expect(screen.getByText('Trang này gặp sự cố')).toBeInTheDocument();
  });

  it('phân biệt hai loại lỗi trong thông báo cho người dùng', () => {
    /**
     * Hai nguyên nhân, hai câu khác nhau: "ứng dụng vừa cập nhật, tải lại đi"
     * là hành động người dùng làm được và chắc chắn khỏi; "trang gặp sự cố" thì
     * không. Gộp làm một là bảo người ta tải lại mãi một trang không bao giờ
     * chạy.
     */
    const { unmount } = render(
      <RouteErrorBoundary>
        <Boom message="error loading dynamically imported module" />
      </RouteErrorBoundary>,
    );
    expect(screen.getByText('Ứng dụng vừa được cập nhật')).toBeInTheDocument();
    unmount();

    sessionStorage.setItem('voya:chunk-reload', '1');
    render(
      <RouteErrorBoundary>
        <Boom message="x.map is not a function" />
      </RouteErrorBoundary>,
    );
    expect(screen.getByText('Trang này gặp sự cố')).toBeInTheDocument();
  });
});
