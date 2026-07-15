import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useTrainingAPI } from './useTrainingAPI';
import axiosClient from '../api/axiosClient';

// Mock axiosClient
vi.mock('../api/axiosClient', async () => {
  const actual = await vi.importActual('../api/axiosClient') as object;
  return {
    ...actual,
    default: {
      get: vi.fn(),
      post: vi.fn(),
      delete: vi.fn(),
      defaults: { baseURL: 'http://localhost:8000' }
    },
    getAuthToken: vi.fn(() => 'mock-token'),
    getApiBaseURL: vi.fn(() => 'http://localhost:8000')
  };
});

// Mock getClassesList which is called internally by loadDatasetInfo
vi.mock('../api/dataset', () => ({
  getClassesList: vi.fn().mockResolvedValue({ ok: true, data: { items: [] } })
}));

describe('useTrainingAPI API Sync Standard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(globalThis, 'fetch'); // Spy on fetch to ensure it's not called
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('1. Đảm bảo loadDatasetInfo gọi qua axiosClient thay vì fetch', async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (axiosClient.get as any).mockResolvedValue({ data: { total_samples: 100 } });
    
    const { result } = renderHook(() => useTrainingAPI());
    
    // Gọi hàm load bọc trong act
    await act(async () => {
      await result.current.loadDatasetInfo('North', 'Vi');
    });
    
    // Kiểm tra đã gọi axiosClient
    expect(axiosClient.get).toHaveBeenCalledWith('/api/v1/training/dataset-info', {
      params: expect.any(URLSearchParams)
    });
    // Đảm bảo không có fetch nào được gọi thủ công
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it('2. Đảm bảo startTraining dùng chuẩn axiosClient.post', async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (axiosClient.post as any).mockResolvedValue({ data: { id: 'job-123' } });
    
    const { result } = renderHook(() => useTrainingAPI());
    
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const config: any = { model_type: 'tcn', epochs: 10 };
    await act(async () => {
      await result.current.startTraining(config);
    });
    
    expect(axiosClient.post).toHaveBeenCalledWith('/api/v1/training/start', config);
  });
});
