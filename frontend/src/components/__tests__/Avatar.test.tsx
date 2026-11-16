import '@testing-library/jest-dom/vitest';
import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import Avatar from '../Avatar';
import { AVATAR_PRESETS, defaultAvatarColor, findAvatarPreset } from '../../lib/avatars';

/**
 * Máy chủ chỉ lưu khoá mẫu và chỉ kiểm DẠNG khoá, nên giao diện phải chịu được
 * khoá lạ (một mẫu đã bị gỡ khỏi bộ) mà không hỏng.
 */
describe('Avatar', () => {
  it('vẽ mẫu đã chọn: có biểu tượng, không có chữ cái', () => {
    const { container } = render(<Avatar user={{ username: 'kha', avatar_key: 'heart' }} />);
    expect(container.querySelector('svg')).not.toBeNull();
    expect(container.textContent).toBe('');
  });

  it('chưa chọn thì vẽ chữ cái đầu viết hoa', () => {
    const { container } = render(<Avatar user={{ username: 'kha' }} />);
    expect(container.textContent).toBe('K');
    expect(container.querySelector('svg')).toBeNull();
  });

  it('khoá lạ thì rơi về chữ cái đầu chứ không hỏng', () => {
    const { container } = render(<Avatar user={{ username: 'kha', avatar_key: 'da-bi-go' }} />);
    expect(container.textContent).toBe('K');
  });

  it('không có người dùng thì vẫn vẽ được', () => {
    const { container } = render(<Avatar user={null} />);
    expect(container.textContent).toBe('C');
  });

  it('là trang trí: ẩn với trình đọc màn hình vì tên luôn nằm cạnh', () => {
    const { container } = render(<Avatar user={{ username: 'kha' }} />);
    expect(container.firstElementChild).toHaveAttribute('aria-hidden', 'true');
  });
});

describe('bộ mẫu', () => {
  it('khoá duy nhất và đúng dạng máy chủ chấp nhận', () => {
    const keys = AVATAR_PRESETS.map((p) => p.key);
    expect(new Set(keys).size).toBe(keys.length);
    for (const k of keys) expect(k).toMatch(/^[a-z0-9-]{1,32}$/);
  });

  it('màu mặc định ổn định theo tên và thuộc bộ màu', () => {
    expect(defaultAvatarColor('kha')).toBe(defaultAvatarColor('kha'));
    expect(AVATAR_PRESETS.map((p) => p.bg)).toContain(defaultAvatarColor('kha'));
    expect(findAvatarPreset('nope')).toBeNull();
  });
});
