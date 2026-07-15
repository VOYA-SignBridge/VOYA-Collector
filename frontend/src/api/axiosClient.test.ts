import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import axiosClient, { getApiBaseURL, getCsrfToken, setAuthToken, getAuthToken, clearAuthToken } from './axiosClient';

// Giả lập document.cookie
let mockCookie = '';
Object.defineProperty(document, 'cookie', {
  get: () => mockCookie,
  set: (val: string) => { mockCookie = val; }
});

describe('axiosClient API Sync Standard', () => {
  beforeEach(() => {
    mockCookie = '';
    clearAuthToken();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('1. Đảm bảo cấu hình Runtime Environment Injection hoạt động (12-Factor App)', () => {
    // Biến môi trường giả lập đã được set trong vitest.setup.ts
    const baseUrl = getApiBaseURL();
    expect(baseUrl).toBe('http://localhost:8000');
    expect(axiosClient.defaults.baseURL).toBe('http://localhost:8000');
  });

  it('2. Đảm bảo Token được lưu và thiết lập đúng chuẩn', () => {
    setAuthToken('test-token-123');
    expect(axiosClient.defaults.headers.common.Authorization).toBe('Bearer test-token-123');
    expect(getAuthToken()).toBeNull(); // saveAuthToken() saves to localStorage, setAuthToken only updates axios
  });

  it('3. Đảm bảo CSRF Token được đọc chính xác từ cookie', () => {
    mockCookie = 'other_cookie=123; voya_csrf=super-secret-csrf; another=456';
    expect(getCsrfToken()).toBe('super-secret-csrf');
  });

  it('4. Đảm bảo interceptor tự động chèn X-CSRF-Token cho các request thay đổi trạng thái (POST/PUT/DELETE)', async () => {
    mockCookie = 'voya_csrf=test-csrf-token';
    
    // Tạo giả lập interceptor request để kiểm tra config
    const mockRequest = {
      method: 'post',
      url: '/test',
      headers: {} as Record<string, string>
    };

    // Gọi trực tiếp hàm interceptor (bỏ qua mạng thật)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const interceptor = (axiosClient.interceptors.request as any).handlers[0].fulfilled;
    const config = await interceptor(mockRequest);

    expect(config.headers['X-CSRF-Token']).toBe('test-csrf-token');
  });

  it('5. Đảm bảo interceptor KHÔNG chèn X-CSRF-Token cho GET requests', async () => {
    mockCookie = 'voya_csrf=test-csrf-token';
    
    const mockRequest = {
      method: 'get',
      url: '/test',
      headers: {} as Record<string, string>
    };

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const interceptor = (axiosClient.interceptors.request as any).handlers[0].fulfilled;
    const config = await interceptor(mockRequest);

    expect(config.headers['X-CSRF-Token']).toBeUndefined();
  });
});
