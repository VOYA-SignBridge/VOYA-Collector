import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * Khả năng tiếp cận — những tính chất kiểm được bằng cách đọc mã nguồn.
 *
 * Vì sao bộ test này tồn tại
 * ---------------------------
 * Đây là nền tảng phục vụ cộng đồng khiếm thính, và tính tới 2026-08-10 chưa ai
 * kiểm khả năng tiếp cận của nó. Bộ test này không thay được một lượt kiểm thật
 * với người dùng thật — nó chỉ ghim những thứ mà một lượt sửa vô ý có thể làm
 * hỏng lại, và mỗi khẳng định đều tương ứng với một tiêu chí WCAG cụ thể.
 *
 * Nó KHÔNG khẳng định giao diện đã tiếp cận được. Nó khẳng định bốn điều cụ thể
 * đã đúng và sẽ không âm thầm sai lại.
 */

const root = resolve(__dirname, '../..');

function read(rel: string): string {
  return readFileSync(resolve(root, rel), 'utf-8');
}

describe('WCAG 3.1.1 — ngôn ngữ của trang', () => {
  it('khai lang="vi", không phải "en"', () => {
    // Toàn bộ giao diện là tiếng Việt. Khai sai làm trình đọc màn hình phát âm
    // tiếng Việt theo luật tiếng Anh. Đã sai suốt cho tới 2026-08-10.
    const html = read('index.html');
    const m = html.match(/<html[^>]*\slang="([^"]+)"/);
    expect(m, 'thẻ <html> phải có thuộc tính lang').not.toBeNull();
    expect(m![1]).toBe('vi');
  });
});

describe('WCAG 1.1.1 — nội dung phi văn bản', () => {
  it('mọi <img> đều có alt (rỗng + aria-hidden nếu chỉ để trang trí)', () => {
    const files = import.meta.glob('../**/*.tsx', { eager: true, query: '?raw',
      import: 'default' }) as Record<string, string>;

    const offenders: string[] = [];
    for (const [path, src] of Object.entries(files)) {
      // Bắt cả thẻ nhiều dòng: `<img` cho tới `>` đầu tiên không nằm trong ngoặc.
      for (const tag of src.match(/<img\b[\s\S]*?\/?>/g) ?? []) {
        if (!/\balt=/.test(tag)) offenders.push(`${path}: ${tag.slice(0, 60)}…`);
      }
    }
    expect(offenders).toEqual([]);
  });
});

describe('WCAG 1.4.1 — không truyền đạt thông tin bằng RIÊNG màu sắc', () => {
  it('Badge luôn kèm biểu tượng theo sắc thái', () => {
    // Thương hiệu đã là xanh dương, nên một chip xanh dương tự nó không nói
    // "thành công" — nó chỉ nói "thuộc ứng dụng này". Biểu tượng mới mang nghĩa.
    // Khoảng 8% nam giới không phân biệt được đỏ–lục.
    const src = read('src/components/ui/Badge.tsx');
    expect(src).toMatch(/ICONS\s*:\s*Record<StatusTone/);
    for (const tone of ['success', 'warning', 'danger', 'neutral']) {
      expect(src, `thiếu biểu tượng cho sắc thái ${tone}`).toContain(`${tone}:`);
    }
  });
});

describe('WCAG 2.4.7 — vị trí con trỏ bàn phím nhìn thấy được', () => {
  it('FOCUS_RING dùng focus-visible, không phải focus', () => {
    // `focus` làm vòng nét hiện sau mỗi cú bấm chuột, và phản xạ đầu tiên của
    // lập trình viên là gỡ nó đi — lúc đó người dùng bàn phím mất hẳn dấu hiệu
    // vị trí con trỏ.
    const src = read('src/theme/status.ts');
    expect(src).toMatch(/FOCUS_RING\s*=\s*\n?\s*"focus-visible:/);
    expect(src).not.toMatch(/FOCUS_RING\s*=\s*\n?\s*"focus:(?!visible)/);
  });
});
