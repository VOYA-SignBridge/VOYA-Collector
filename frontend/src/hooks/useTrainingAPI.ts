/**
 * Training API Hook
 * Manages communication with backend training endpoints
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { getClassesList } from '../api/dataset';
import { getAuthToken } from '../api/axiosClient';

/** Cách tập dữ liệu ĐANG được chia — đọc từ split trên đĩa, không phải từ
 *  lựa chọn của người dùng. Bước 3 trước đây hiện thanh trượt tỉ lệ không gửi
 *  đi đâu; backend luôn dùng split đã sinh sẵn. */
export interface SplitProvenance {
  split_mode: string | null;
  signer_disjoint: boolean;
  signers: Record<string, string[]>;   // train/val/test -> signer ids
  counts: Record<string, number>;      // train/val/test -> số mẫu
  dataset_manifest: string | null;
  valid_for_research: boolean | null;
  warning: string | null;
}

export interface DatasetInfo {
  total_samples: number;
  total_classes: number;
  languages: string[];
  dialects: Record<string, string[]>;
  class_distribution: Record<string, number>;
  // Số mẫu theo từng phương ngữ — dùng cho bước chia tập (DataSplitVisualization)
  samples_by_dialect?: Record<string, number>;
  split_info?: { train: number; val: number; test: number };
  split_provenance?: SplitProvenance;
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
  /** 'smoke_test' = thăm dò nhanh (mặc định); 'research' = chạy trên split đã
   *  versioned để kết quả trích dẫn được. */
  run_purpose?: 'smoke_test' | 'research';
  split_version?: string | null;
}

// GET /training/splits — split đã versioned dùng được cho chế độ nghiên cứu
export interface ResearchSplit {
  split_version: string;
  dataset_version: string;
  recognition_profile: string;
  split_mode: string;
  num_classes: number | null;
  counts: { train: number | null; val: number | null; test: number | null };
  seed: number | null;
  dataset_manifest_checksum: string;
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

// GET /training/jobs/{id}/provenance
export interface ProvenanceCheck {
  id: string;      // C1/C5/C10/C11/C13 — same ids as scripts/research_validity.py
  label: string;
  ok: boolean;
  detail: string;
}

export interface JobProvenance {
  available: boolean;
  job_id?: string;
  code?: {
    git_commit: string;
    seed: number | null;
    run_purpose: string;
    run_status: string;
    determinism: string;
    created_at: string;
  };
  data?: {
    dataset_version: string;
    split_version: string;
    dataset_manifest_checksum: string;
    recognition_profile: string;
    vocabulary_schema_version: string;
  };
  model?: {
    model_type: string;
    num_classes: number | null;
    seq_len: number | null;
    feature_dim: number | null;
    normalization_version: string;
    storage_contract_version: string;
  };
  model_selection?: Record<string, unknown>;
  runtime_env?: Record<string, unknown>;
  checks?: ProvenanceCheck[];
  reproducible?: boolean;
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
const API_URL = '/api/v1/training';

// Training endpoints require authentication; attach the stored bearer token.
function authHeaders(): Record<string, string> {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

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

      const response = await fetch(`${API_URL}/dataset-info?${params}`, {
        headers: authHeaders(),
      });
      if (!response.ok) {
        throw new Error(`Failed to load dataset info: ${response.statusText}`);
      }

      // Ensure we received JSON; sometimes proxy/back-end misconfiguration returns HTML (index.html)
      const contentType = response.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) {
        const text = await response.text();
        throw new Error(
          `Unexpected non-JSON response from training dataset endpoint. Response begins with: ${text.slice(0, 200)}`
        );
      }

      const data = await response.json();
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
      const response = await fetch(`${API_URL}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(config),
      });

      if (!response.ok) {
        throw new Error(`Failed to start training: ${response.statusText}`);
      }

      const contentType = response.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) {
        const text = await response.text();
        throw new Error(
          `Unexpected non-JSON response from training start endpoint. Response begins with: ${text.slice(0, 200)}`
        );
      }

      return await response.json();
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
      const response = await fetch(`${API_URL}/jobs/${jobId}`, { headers: authHeaders() });
      if (!response.ok) {
        throw new Error(`Failed to fetch job status: ${response.statusText}`);
      }

      const contentType = response.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) {
        const text = await response.text();
        throw new Error(
          `Unexpected non-JSON response from job status endpoint. Response begins with: ${text.slice(0, 200)}`
        );
      }

      return await response.json();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    }
  }, []);

  // Lấy metrics
  const getJobMetrics = useCallback(async (jobId: string): Promise<TrainingMetrics[]> => {
    try {
      const response = await fetch(`${API_URL}/jobs/${jobId}/metrics`, { headers: authHeaders() });
      if (!response.ok) {
        throw new Error(`Failed to fetch metrics: ${response.statusText}`);
      }

      const contentType = response.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) {
        const text = await response.text();
        throw new Error(
          `Unexpected non-JSON response from job metrics endpoint. Response begins with: ${text.slice(0, 200)}`
        );
      }

      return await response.json();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return [];
    }
  }, []);

  // Lịch sử jobs (mới nhất trước), kèm username người chạy
  const listJobs = useCallback(async (limit = 100): Promise<TrainingJobListItem[]> => {
    try {
      const response = await fetch(`${API_URL}/jobs?limit=${limit}`, { headers: authHeaders() });
      if (!response.ok) {
        throw new Error(`Failed to list jobs: ${response.statusText}`);
      }
      return await response.json();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return [];
    }
  }, []);

  // Hủy training job đang chạy/đang chờ
  const cancelTraining = useCallback(async (jobId: string): Promise<TrainingJob | null> => {
    try {
      const response = await fetch(`${API_URL}/jobs/${jobId}/cancel`, {
        method: 'POST',
        headers: authHeaders(),
      });
      if (!response.ok) {
        throw new Error(`Failed to cancel job: ${response.statusText}`);
      }
      return await response.json();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    }
  }, []);

  // Promote model của job lên realtime (admin only)
  const promoteJob = useCallback(async (jobId: string): Promise<PromoteResponse | null> => {
    try {
      const response = await fetch(`${API_URL}/jobs/${jobId}/promote`, {
        method: 'POST',
        headers: authHeaders(),
      });
      if (!response.ok) {
        throw new Error(`Failed to promote job: ${response.statusText}`);
      }
      return await response.json();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    }
  }, []);

  // Per-class breakdown + confusion matrix trên test set (Step 7)
  const getResearchSplits = useCallback(async (): Promise<ResearchSplit[]> => {
    try {
      const response = await fetch(`${API_URL}/splits`, { headers: authHeaders() });
      if (!response.ok) {
        throw new Error(`Failed to fetch splits: ${response.statusText}`);
      }
      return await response.json();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return [];
    }
  }, []);

  const getJobProvenance = useCallback(async (jobId: string): Promise<JobProvenance | null> => {
    try {
      const response = await fetch(`${API_URL}/jobs/${jobId}/provenance`, { headers: authHeaders() });
      if (!response.ok) {
        throw new Error(`Failed to fetch provenance: ${response.statusText}`);
      }
      return await response.json();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    }
  }, []);

  const getJobEvaluation = useCallback(async (jobId: string): Promise<JobEvaluation | null> => {
    try {
      const response = await fetch(`${API_URL}/jobs/${jobId}/evaluation`, { headers: authHeaders() });
      if (!response.ok) {
        throw new Error(`Failed to fetch evaluation: ${response.statusText}`);
      }
      return await response.json();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    }
  }, []);

  // Xóa job khỏi lịch sử huấn luyện (chỉ job đã kết thúc: completed/failed/cancelled)
  const deleteJob = useCallback(async (jobId: string): Promise<boolean> => {
    try {
      const response = await fetch(`${API_URL}/jobs/${jobId}`, {
        method: 'DELETE',
        headers: authHeaders(),
      });
      if (!response.ok) {
        const contentType = response.headers.get('content-type') || '';
        const detail = contentType.includes('application/json')
          ? (await response.json())?.detail
          : undefined;
        throw new Error(detail || `Failed to delete job: ${response.statusText}`);
      }
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
    getJobProvenance,
    getResearchSplits,
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

  useEffect(() => {
    if (!jobId) return;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const token = getAuthToken();
    const wsUrl = `${protocol}//${window.location.host}/api/v1/training/ws/${jobId}?token=${encodeURIComponent(token || '')}`;

    wsRef.current = new WebSocket(wsUrl);

    wsRef.current.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === 'metric') {
          onMetric(message.data);
        } else if (message.type === 'status') {
          onStatus(message.data);
        }
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error('WebSocket message parse error:', err);
      }
    };

    wsRef.current.onerror = () => {
      if (onError) onError('WebSocket connection error');
      else console.error('WebSocket connection error');
    };

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
    // Intentionally include callbacks as dependencies
  }, [jobId, onMetric, onStatus, onError]);

  return wsRef.current;
}
