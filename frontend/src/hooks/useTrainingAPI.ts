/**
 * Training API Hook
 * Manages communication with backend training endpoints
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { getClassesList } from '../api/dataset';
import axiosClient, { getAuthToken, getApiBaseURL } from '../api/axiosClient';

export interface DatasetInfo {
  total_samples: number;
  total_classes: number;
  languages: string[];
  dialects: Record<string, string[]>;
  class_distribution: Record<string, number>;
  split_info?: { train: number; val: number; test: number };
  // Optional mapping from class uid/slug -> human label
  label_map?: Record<string, string>;
}

export type ModelType = 'tcn' | 'cnn' | 'lstm' | 'bigru_attention' | 'hdgcn';

export interface TrainingConfig {
  model_type: ModelType;
  dialects: string[];
  languages: string[];
  epochs: number;
  batch_size: number;
  learning_rate: number;
  dropout: number;
  channels: number;
  levels: number;
  kernel_size: number;
}

export interface TrainingMetrics {
  epoch: number;
  train_loss: number;
  train_acc: number;
  val_loss: number;
  val_acc: number;
  val_f1: number;
  learning_rate?: number;
}

export interface TrainingJob {
  id: string;
  status: 'pending' | 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  config: TrainingConfig;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  current_epoch: number;
  total_epochs: number;
  checkpoint_path?: string;
  test_acc?: number;
  test_f1?: number;
  error_message?: string;
  promoted_at?: string;
}

// GET /training/jobs — lịch sử jobs kèm username người chạy
export interface TrainingJobListItem extends TrainingJob {
  username?: string | null;
}

// GET /training/jobs/{id}/evaluation — per-class breakdown + confusion matrix (test set)
export interface JobEvaluationClass {
  class_idx: number;
  label_key: string;
  precision: number;
  recall: number;
  f1: number;
  support: number;
}

export interface JobEvaluation {
  available: boolean;
  job_id?: string;
  per_class?: JobEvaluationClass[];
  confusion_matrix?: number[][];
  labels?: string[];
}

// POST /training/jobs/{id}/promote
export interface PromoteResponse {
  job: TrainingJob;
  model_id: string;
  deployed_checkpoint: string;
  registry_updated: boolean;
  realtime_reloaded: boolean;
  message: string;
}

// Use relative URL so it proxies through frontend server (nginx, dev server, etc.)
// When using axiosClient, we just need the path prefix since baseURL is already set
const API_PREFIX = `/api/v1/training`;

export function useTrainingAPI() {
  const [datasetInfo, setDatasetInfo] = useState<DatasetInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Tải dataset info
  const loadDatasetInfo = useCallback(async (dialect?: string, language?: string) => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (dialect) params.append('dialect', dialect);
      if (language) params.append('language', language);

      const response = await axiosClient.get(`${API_PREFIX}/dataset-info`, { params });
      const data = response.data;
      // Try to enrich dataset info with class labels (if available)
      try {
        const classesRes = await getClassesList();
        if (classesRes.ok && classesRes.data && Array.isArray(classesRes.data.items)) {
          const map: Record<string, string> = {};
          for (const c of classesRes.data.items) {
            const label = c.label_original || c.slug || '';
            if (c.class_uid) map[c.class_uid] = label;
            if (c.slug) map[c.slug] = label;
            // also map numeric idx
            if (c.class_idx !== undefined && c.class_idx !== null) map[String(c.class_idx)] = label;
          }
          setDatasetInfo({ ...(data as DatasetInfo), label_map: map });
        } else {
          setDatasetInfo(data);
        }
      } catch (err) {
        // If classes fetch fails, still set dataset info
        setDatasetInfo(data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  // Bắt đầu training
  const startTraining = useCallback(async (config: TrainingConfig): Promise<TrainingJob | null> => {
    setLoading(true);
    setError(null);
    try {
      const response = await axiosClient.post(`${API_PREFIX}/start`, config);
      return response.data;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  // Lấy job status
  const getJobStatus = useCallback(async (jobId: string): Promise<TrainingJob | null> => {
    try {
      const response = await axiosClient.get(`${API_PREFIX}/jobs/${jobId}`);
      return response.data;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    }
  }, []);

  // Lấy metrics
  const getJobMetrics = useCallback(async (jobId: string): Promise<TrainingMetrics[]> => {
    try {
      const response = await axiosClient.get(`${API_PREFIX}/jobs/${jobId}/metrics`);
      return response.data;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return [];
    }
  }, []);

  // Lịch sử jobs (mới nhất trước), kèm username người chạy
  const listJobs = useCallback(async (limit = 100): Promise<TrainingJobListItem[]> => {
    try {
      const response = await axiosClient.get(`${API_PREFIX}/jobs`, { params: { limit } });
      return response.data;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return [];
    }
  }, []);

  // Hủy training job đang chạy/đang chờ
  const cancelTraining = useCallback(async (jobId: string): Promise<TrainingJob | null> => {
    try {
      const response = await axiosClient.post(`${API_PREFIX}/jobs/${jobId}/cancel`);
      return response.data;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    }
  }, []);

  // Promote model của job lên realtime (admin only)
  const promoteJob = useCallback(async (jobId: string): Promise<PromoteResponse | null> => {
    try {
      const response = await axiosClient.post(`${API_PREFIX}/jobs/${jobId}/promote`);
      return response.data;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    }
  }, []);

  // Per-class breakdown + confusion matrix trên test set (Step 7)
  const getJobEvaluation = useCallback(async (jobId: string): Promise<JobEvaluation | null> => {
    try {
      const response = await axiosClient.get(`${API_PREFIX}/jobs/${jobId}/evaluation`);
      return response.data;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    }
  }, []);

  // Xóa job khỏi lịch sử huấn luyện (chỉ job đã kết thúc: completed/failed/cancelled)
  const deleteJob = useCallback(async (jobId: string): Promise<boolean> => {
    try {
      await axiosClient.delete(`${API_PREFIX}/jobs/${jobId}`);
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return false;
    }
  }, []);

  // Note: `useWebSocketProgress` is provided as a top-level hook below

  return {
    datasetInfo,
    loading,
    error,
    loadDatasetInfo,
    startTraining,
    getJobStatus,
    getJobMetrics,
    listJobs,
    cancelTraining,
    promoteJob,
    getJobEvaluation,
    deleteJob,
    useWebSocketProgress,
  };
}

// Top-level hook for subscribing to training WebSocket progress.
// Kept separate to avoid calling hooks inside callbacks returned from other hooks.
export function useWebSocketProgress(
  jobId: string | null,
  onMetric: (m: TrainingMetrics) => void,
  onStatus: (j: TrainingJob) => void,
  onError?: (msg: string) => void,
) {
  const wsRef = useRef<WebSocket | null>(null);

  // Keep the latest callbacks in a ref. Callers usually pass inline arrow
  // functions (new identity every render); if the socket effect depended on
  // them it would tear down + reopen the WebSocket on EVERY render, so the
  // connection never stayed up long enough to receive data (UI stuck at 0/0,
  // server logging a flood of "1005 no status received").
  const callbacksRef = useRef({ onMetric, onStatus, onError });
  useEffect(() => {
    callbacksRef.current = { onMetric, onStatus, onError };
  }, [onMetric, onStatus, onError]);

  useEffect(() => {
    if (!jobId) return;
    const token = getAuthToken();
    
    let wsUrl = '';
    let apiBase = getApiBaseURL().replace(/\/+$/, "");
    if (apiBase.endsWith("/api")) {
      apiBase = apiBase.slice(0, -4);
    }
    
    if (apiBase && (apiBase.startsWith('http://') || apiBase.startsWith('https://'))) {
      const wsProtocol = apiBase.startsWith('https') ? 'wss:' : 'ws:';
      const hostPath = apiBase.replace(/^https?:\/\//, '');
      wsUrl = `${wsProtocol}//${hostPath}/api/v1/training/ws/${jobId}?token=${encodeURIComponent(token || '')}`;
    } else {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      const pathPrefix = apiBase ? apiBase.replace(/^\//, '') + '/' : '';
      wsUrl = `${protocol}//${host}/${pathPrefix}api/v1/training/ws/${jobId}?token=${encodeURIComponent(token || '')}`;
    }

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === 'metric') {
          callbacksRef.current.onMetric(message.data);
        } else if (message.type === 'status') {
          callbacksRef.current.onStatus(message.data);
        }
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error('WebSocket message parse error:', err);
      }
    };

    ws.onerror = () => {
      const { onError: cb } = callbacksRef.current;
      if (cb) cb('WebSocket connection error');
      else console.error('WebSocket connection error');
    };

    return () => {
      ws.close();
    };
    // Only reconnect when the job actually changes — callbacks are read via ref.
  }, [jobId]);

  return wsRef.current;
}
