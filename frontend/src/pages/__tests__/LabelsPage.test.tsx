import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import LabelsPage from '../LabelsPage';
import * as datasetApi from '../../api/dataset';
import * as useAuthHook from '../../hooks/useAuth';

// Mock toàn bộ API và Hook
vi.mock('../../api/dataset', () => ({
  getLabels: vi.fn(),
  getClassesList: vi.fn(),
  getClassesStats: vi.fn(),
  updateClass: vi.fn(),
  deleteClass: vi.fn(),
  registerClass: vi.fn(),
}));

vi.mock('../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}));

// `Link` is mocked as well as `useNavigate`: a partial mock of this module
// throws "No 'Link' export is defined" the moment any child renders one, and
// PageHeader's breadcrumb does. Rendering it as a plain anchor keeps the href
// assertable without pulling a Router into every page test.
vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
  Link: ({ to, children }: { to: string; children: React.ReactNode }) => (
    <a href={to}>{children}</a>
  ),
}));

describe('LabelsPage - Comprehensive Automation Tests (Edge Cases & Errors)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    // Giả lập trạng thái người dùng MẶC ĐỊNH là Admin
    vi.mocked(useAuthHook.useAuth).mockReturnValue({
      loading: false,
      isAdmin: true,
      user: { id: '1', username: 'admin' },
      login: vi.fn(),
      logout: vi.fn(),
      checkStatus: vi.fn()
    } as any);

    // Mock API Success by default
    vi.mocked(datasetApi.getLabels).mockResolvedValue({
      ok: true,
      data: [
        { class_idx: 1, label_original: 'Xin chào', slug: 'hello' },
        { class_idx: 2, label_original: 'Cảm ơn', slug: 'thanks' }
      ]
    } as any);

    vi.mocked(datasetApi.getClassesList).mockResolvedValue({
      ok: true,
      data: {
        count: 2,
        items: [
          {
            class_uid: 'uid-1', class_idx: 1, slug: 'hello', label_original: 'Xin chào',
            language: 'vn', dialect: 'common', is_common_language: true, is_common_global: false
          },
          {
            class_uid: 'uid-2', class_idx: 2, slug: 'thanks', label_original: 'Cảm ơn',
            language: 'vn', dialect: 'common', is_common_language: true, is_common_global: false
          }
        ]
      }
    } as any);

    vi.mocked(datasetApi.getClassesStats).mockResolvedValue({
      ok: true,
      data: {
        total_classes: 2, max_count: 6,
        distribution: [
          { class_uid: 'uid-1', count: 2, samples_count: 12 }, // 12 samples => 2 sessions (Thiếu 3 lần quay)
          { class_uid: 'uid-2', count: 6, samples_count: 31 }  // 31 samples => 6 sessions (Dư, 6/5)
        ]
      }
    } as any);
  });

  describe('Hiển thị Tiến độ (Progress UI)', () => {
    it('Tính toán đúng các trường hợp thiếu mẫu và đủ mẫu', async () => {
      render(<LabelsPage />);
      
      await waitFor(() => {
        expect(screen.getByText('Xin chào')).toBeInTheDocument();
      });

      // Kiểm tra nhãn thiếu mẫu (12 samples = 2 sessions -> 2/5)
      expect(screen.getAllByText('2 / 5')[0]).toBeInTheDocument();
      expect(screen.getByText('Cần thêm 3 lần quay')).toBeInTheDocument();

      // Kiểm tra nhãn đủ/dư mẫu (31 samples = 6 sessions -> 6/5)
      expect(screen.getAllByText('6 / 5')[0]).toBeInTheDocument();
      expect(screen.getByText('Đã đủ điều kiện huấn luyện')).toBeInTheDocument();
    });
  });

  describe('Phân quyền (Authorization Edge Cases)', () => {
    it('Không hiển thị nút "Tạo nhãn mới" nếu không phải Admin', async () => {
      // Đổi mock thành User thường
      vi.mocked(useAuthHook.useAuth).mockReturnValue({
        loading: false, isAdmin: false, user: { id: '2', username: 'user' }
      } as any);

      render(<LabelsPage />);
      
      await waitFor(() => {
        expect(screen.getByText('Xin chào')).toBeInTheDocument();
      });

      // Nút "Tạo nhãn mới" không được tồn tại trong DOM
      expect(screen.queryByText('Tạo nhãn mới')).not.toBeInTheDocument();
      // Phải có dòng text thông báo quyền
      expect(screen.getAllByText('Chỉ quản trị viên có thể chỉnh sửa').length).toBeGreaterThan(0);
    });
  });

  describe('Tạo nhãn mới (Form Validation & API Errors)', () => {
    it('Chặn không cho tạo nhãn nếu để trống Tên nhãn (Validation Error)', async () => {
      render(<LabelsPage />);
      await waitFor(() => expect(screen.getByText('Xin chào')).toBeInTheDocument());

      fireEvent.click(screen.getByText('Tạo nhãn mới'));
      
      // Không gõ gì cả, bấm tạo luôn
      const submitBtn = screen.getByText('Tạo nhãn', { selector: 'button' });
      fireEvent.click(submitBtn);

      // Phải báo lỗi validation
      expect(screen.getByText('Tên nhãn không được để trống.')).toBeInTheDocument();
      
      // Đảm bảo API KHÔNG hề bị gọi
      expect(datasetApi.registerClass).not.toHaveBeenCalled();
    });

    it('Hiển thị thông báo lỗi hệ thống nếu API trả về lỗi 500/Thất bại', async () => {
      // Mock API trả về thất bại
      vi.mocked(datasetApi.registerClass).mockResolvedValue({
        ok: false,
        error: 'Lỗi máy chủ nội bộ. Vui lòng thử lại.'
      } as any);

      render(<LabelsPage />);
      await waitFor(() => expect(screen.getByText('Xin chào')).toBeInTheDocument());

      fireEvent.click(screen.getByText('Tạo nhãn mới'));
      
      const input = screen.getByPlaceholderText('Ví dụ: Xin chào, Cảm ơn...');
      fireEvent.change(input, { target: { value: 'Lỗi Test' } });

      const submitBtn = screen.getByText('Tạo nhãn', { selector: 'button' });
      fireEvent.click(submitBtn);

      // Chờ API xử lý
      await waitFor(() => expect(datasetApi.registerClass).toHaveBeenCalled());

      // Phải hiển thị Banner thông báo lỗi từ Server
      expect(screen.getByText('Lỗi máy chủ nội bộ. Vui lòng thử lại.')).toBeInTheDocument();
      // Thông báo thành công KHÔNG được hiện
      expect(screen.queryByText(/Đã tạo nhãn/i)).not.toBeInTheDocument();
    });

    it('Tạo nhãn thành công (Happy Path)', async () => {
      vi.mocked(datasetApi.registerClass).mockResolvedValue({
        ok: true,
        data: { class_uid: 'uid-3', class_idx: 3, label_original: 'Tạm biệt', language: 'vn', dialect: 'common' }
      } as any);

      render(<LabelsPage />);
      await waitFor(() => expect(screen.getByText('Xin chào')).toBeInTheDocument());

      fireEvent.click(screen.getByText('Tạo nhãn mới'));
      
      const input = screen.getByPlaceholderText('Ví dụ: Xin chào, Cảm ơn...');
      fireEvent.change(input, { target: { value: 'Tạm biệt' } });

      const submitBtn = screen.getByText('Tạo nhãn', { selector: 'button' });
      fireEvent.click(submitBtn);

      await waitFor(() => expect(datasetApi.registerClass).toHaveBeenCalled());
      expect(screen.getByText(/Đã tạo nhãn "Tạm biệt"/i)).toBeInTheDocument();
    });
  });

  describe('Tải dữ liệu danh sách (List Fetching Errors)', () => {
    it('Hiển thị lỗi và trạng thái rỗng khi API danh sách sập (GetList Error)', async () => {
      // Mock cả 2 endpoint danh sách đều chết
      vi.mocked(datasetApi.getClassesList).mockRejectedValue(new Error('Network Disconnected'));
      vi.mocked(datasetApi.getLabels).mockRejectedValue(new Error('Network Disconnected'));

      render(<LabelsPage />);
      
      await waitFor(() => {
        expect(screen.getByText('Network Disconnected')).toBeInTheDocument();
      });

      // Giao diện Empty State phải hiện ra
      expect(screen.getByText('Không tìm thấy nhãn')).toBeInTheDocument();
    });
  });
});
