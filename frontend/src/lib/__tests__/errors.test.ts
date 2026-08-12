import { describe, it, expect } from 'vitest';
import { friendlyError, isRetryable } from '../errors';

/**
 * Bộ lọc thông báo lỗi.
 *
 * Đây là test về BẢO MẬT nhiều hơn là về giao diện. Phần lớn phép khẳng định ở
 * đây có dạng "chuỗi này KHÔNG được xuất hiện trên màn hình", vì thứ cần chặn
 * là chi tiết nội bộ đi ra ngoài: tên bảng, ràng buộc, đường dẫn trong
 * container, tên máy chủ, vết ngăn xếp.
 *
 * Quy tắc của bộ lọc là **mặc định từ chối**. Nên khi thêm dấu hiệu mới vào
 * `SYSTEM_MARKERS`, hãy thêm một test "không lộ" ở đây trước.
 */

const res = (status: number, data: unknown) => ({ response: { status, data } });

describe('Không để lộ chi tiết nội bộ', () => {
  const LEAKY = [
    ['vết ngăn xếp', 'Traceback (most recent call last): File "/app/main.py", line 42'],
    ['tên lớp ngoại lệ', 'IntegrityError: duplicate key value violates unique constraint'],
    ['tên ràng buộc', 'insert or update on table "samples" violates foreign key constraint "fk_x"'],
    ['câu SQL', 'SELECT storage_key FROM legal_documents WHERE tenant_id = $1'],
    ['đường dẫn container', 'FileNotFoundError: /src/backend/dataset/features/vn.npz'],
    ['đường dẫn Windows', 'Cannot open E:\\CTU_ProjectOutside\\dataset\\x.npz'],
    ['tên máy chủ nội bộ', 'could not connect to server at postgres:5432'],
    ['địa chỉ IP', 'upstream 172.18.0.4 timed out'],
    ['tên driver', 'psycopg2.OperationalError: connection refused'],
  ] as const;

  it.each(LEAKY)('chặn %s', (_label, detail) => {
    const shown = friendlyError(res(400, { detail }));
    expect(shown).not.toContain(detail);
    expect(shown).toBe('Yêu cầu không hợp lệ. Hãy kiểm tra lại thông tin đã nhập.');
  });

  it('lỗi 5xx không bao giờ cho detail đi qua, kể cả khi trông vô hại', () => {
    /** Nhóm 5xx là lỗi CHƯA LƯỜNG TRƯỚC — đúng nhóm hay mang theo nội dung của
     * tầng dưới. Một câu trông sạch ở đây vẫn không đáng để đánh cược. */
    const shown = friendlyError(res(500, { detail: 'Không lưu được bản ghi' }));
    expect(shown).not.toContain('Không lưu được bản ghi');
    expect(shown).toContain('Máy chủ gặp sự cố');
  });

  it('mảng lỗi 422 của FastAPI không rơi ra "[object Object]"', () => {
    const shown = friendlyError(res(422, {
      detail: [{ loc: ['query', '_args'], msg: 'field required', type: 'value_error.missing' }],
    }));
    expect(shown).not.toContain('object Object');
    expect(shown).not.toContain('_args');
    expect(shown).toBe('Dữ liệu gửi lên không hợp lệ. Hãy kiểm tra lại các ô đã nhập.');
  });

  it('chuỗi dài bất thường bị coi là bãi nôn của hệ thống', () => {
    const shown = friendlyError(res(400, { detail: 'x'.repeat(400) }));
    expect(shown.length).toBeLessThan(120);
  });
});

describe('Vẫn giữ được câu tử tế do backend soạn', () => {
  it('cho qua thông báo tiếng Việt viết cho người đọc', () => {
    const detail = 'Không thể tự khóa tài khoản của chính mình';
    expect(friendlyError(res(400, { detail }))).toBe(detail);
  });

  it('mã lỗi nghiệp vụ thắng cả detail lẫn mã HTTP', () => {
    const shown = friendlyError(res(409, {
      error_code: 'stale_version',
      detail: 'revision mismatch: 4 != 5',
    }));
    expect(shown).toContain('người khác cập nhật');
    expect(shown).not.toContain('revision mismatch');
  });
});

describe('Câu chung theo mã HTTP', () => {
  it.each([
    [401, 'đăng nhập lại'],
    [403, 'không có quyền'],
    [404, 'Không tìm thấy'],
    [429, 'chờ một lát'],
    [503, 'bảo trì'],
  ])('%i nói được việc gì đã xảy ra', (status, fragment) => {
    expect(friendlyError(res(status, {}))).toContain(fragment);
  });

  it('mã lạ thì dùng câu dự phòng theo NGỮ CẢNH của nơi gọi', () => {
    expect(friendlyError(res(418, {}), 'Không tải được danh sách tổ chức'))
      .toBe('Không tải được danh sách tổ chức');
  });
});

describe('Lỗi mạng', () => {
  it('không có phản hồi nghĩa là chưa tới được máy chủ', () => {
    expect(friendlyError({ message: 'Network Error' })).toContain('Không kết nối được máy chủ');
  });

  it('quá hạn chờ nói đúng là quá hạn chờ', () => {
    expect(friendlyError({ code: 'ECONNABORTED' })).toContain('quá lâu');
  });
});

describe('Có nên mời thử lại không', () => {
  it('không mời thử lại với lỗi phân quyền', () => {
    /** Nút "Thử lại" cạnh một lỗi 403 là lời mời làm một việc chắc chắn hỏng
     * lần nữa. */
    expect(isRetryable(res(403, {}))).toBe(false);
    expect(isRetryable(res(404, {}))).toBe(false);
  });

  it('mời thử lại với quá tải, sự cố máy chủ và lỗi mạng', () => {
    expect(isRetryable(res(429, {}))).toBe(true);
    expect(isRetryable(res(503, {}))).toBe(true);
    expect(isRetryable({ message: 'Network Error' })).toBe(true);
  });
});
