import { describe, it, expect } from 'vitest';
import { safeRedirectTarget } from './redirect';

describe('safeRedirectTarget', () => {
  it('giữ nguyên đường dẫn nội bộ hợp lệ', () => {
    expect(safeRedirectTarget('/training')).toBe('/training');
    expect(safeRedirectTarget('/admin/users')).toBe('/admin/users');
    expect(safeRedirectTarget('/labels?dialect=bac')).toBe('/labels?dialect=bac');
  });

  it('giải mã giá trị đã encode', () => {
    expect(safeRedirectTarget(encodeURIComponent('/labels?dialect=bac'))).toBe('/labels?dialect=bac');
  });

  it('về mặc định khi thiếu tham số', () => {
    expect(safeRedirectTarget(null)).toBe('/upload');
    expect(safeRedirectTarget(undefined)).toBe('/upload');
    expect(safeRedirectTarget('')).toBe('/upload');
  });

  it('chặn open-redirect ra ngoài site', () => {
    expect(safeRedirectTarget('//evil.com')).toBe('/upload');
    expect(safeRedirectTarget('https://evil.com')).toBe('/upload');
    expect(safeRedirectTarget('http://evil.com')).toBe('/upload');
    expect(safeRedirectTarget('/\\evil.com')).toBe('/upload');
    expect(safeRedirectTarget(encodeURIComponent('//evil.com'))).toBe('/upload');
  });

  it('không quay lại chính các trang xác thực (tránh vòng lặp)', () => {
    expect(safeRedirectTarget('/login')).toBe('/upload');
    expect(safeRedirectTarget('/register')).toBe('/upload');
    expect(safeRedirectTarget('/reset-password?token=abc')).toBe('/upload');
  });

  it('không vỡ khi chuỗi encode hỏng', () => {
    expect(safeRedirectTarget('%E0%A4%A')).toBe('/upload');
  });
});
