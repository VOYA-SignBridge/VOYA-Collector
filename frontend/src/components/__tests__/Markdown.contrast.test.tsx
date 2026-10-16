import '@testing-library/jest-dom/vitest';
import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';

import Markdown from '../Markdown';

/**
 * Chế độ tối làm dở dang ở đúng MỘT tệp.
 *
 * `tailwind.config` không khai báo `darkMode`, nên Tailwind dùng mặc định
 * `'media'`: biến thể `dark:` kích hoạt theo `prefers-color-scheme` của hệ điều
 * hành, không theo một lựa chọn nào trong ứng dụng. Nhưng ứng dụng này không có
 * chủ đề tối — không tệp nào khác dùng `dark:`, nên nền luôn sáng.
 *
 * `Markdown.tsx` từng có tám biến thể `dark:`. Trên máy bật chế độ tối, thân
 * văn bản pháp lý dựng ra `#e2e8f0` trên nền trắng (tương phản ~1.2:1, gần như
 * vô hình) và khối cảnh báo thành một mảng nâu sẫm.
 *
 * Đây là kiểu hỏng KHÔNG BAO GIỜ lộ ra với người phát triển dùng chế độ sáng,
 * nên nó phải được canh bằng một khẳng định về mã nguồn chứ không bằng mắt.
 * Bài test dựng thật thì cũng không bắt được: jsdom không áp media query, nên
 * `dark:text-slate-200` vẫn chỉ là một chuỗi trong `class`.
 */

const MARKDOWN_SRC = join(__dirname, '..', 'Markdown.tsx');

describe('Không có chủ đề tối nửa vời', () => {
  it('Markdown.tsx KHÔNG chứa biến thể dark: nào', () => {
    const src = readFileSync(MARKDOWN_SRC, 'utf-8');
    // Bỏ phần chú thích khối — nó GIẢI THÍCH vì sao không có `dark:`, nên nhắc
    // tới chuỗi đó là chuyện bình thường và không được tính là vi phạm.
    const code = src.replace(/\/\*[\s\S]*?\*\//g, '');
    const found = code.match(/\bdark:[\w[\]/.-]+/g) ?? [];
    expect(found).toEqual([]);
  });

  it('không tệp nào dùng dark: khi chiến lược vẫn là "media"', () => {
    /**
     * Bất biến thật, phát biểu đúng một lần:
     *
     *   Chừng nào `darkMode` chưa phải `'class'`, biến thể `dark:` bám theo cài
     *   đặt HỆ ĐIỀU HÀNH — nên bất kỳ tệp nào dùng nó sẽ dựng màu của chủ đề
     *   tối lên nền của chủ đề sáng.
     *
     * Đổi sang `darkMode: 'class'` và làm chủ đề tối cho cả ứng dụng thì test
     * này tự nhường đường. Đó là ý định: nó chặn bản NỬA VỜI, không chặn chủ đề
     * tối.
     */
    const config = readFileSync(
      join(__dirname, '..', '..', '..', 'tailwind.config.cjs'),
      'utf-8',
    );
    if (/darkMode\s*:\s*['"]class['"]/.test(config)) return;

    const src = join(__dirname, '..', '..');
    const offenders: string[] = [];
    const walk = (dir: string) => {
      for (const entry of readdirSync(dir, { withFileTypes: true })) {
        const full = join(dir, entry.name);
        if (entry.isDirectory()) {
          walk(full);
        } else if (/\.(tsx?|css)$/.test(entry.name)) {
          const code = readFileSync(full, 'utf-8').replace(/\/\*[\s\S]*?\*\//g, '');
          if (/\bdark:[\w[\]/.-]+/.test(code)) offenders.push(relative(src, full));
        }
      }
    };
    walk(src);

    expect(offenders).toEqual([]);
  });

  it('thân văn bản dựng ra màu chữ đậm, không phải màu của chủ đề tối', () => {
    const { container } = render(<Markdown text={'# Điều khoản\n\nNội dung.'} />);
    const wrapper = container.querySelector('div');
    expect(wrapper?.className).toContain('text-slate-800');
    expect(wrapper?.className).not.toContain('slate-200');
  });
});
