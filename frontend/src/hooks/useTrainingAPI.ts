/**
 * Training API Hook
 * Manages communication with backend training endpoints
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { getClassesList } from '../api/dataset';
import axiosClient, { getAuthToken } from '../api/axiosClient';

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
  /** true: split triển khai riêng cho đúng dialect đang chọn. false: rơi về
   *  split gốc dùng chung — split đó luôn có counts > 0, nên KHÔNG được suy
   *  "đã chuẩn bị cho phạm vi này" chỉ từ counts. */
  is_deployment_split: boolean;
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
  /** Cách phân hoạch đã tạo ra test_acc/test_f1. Backend luôn trả về; hiển thị
   *  cạnh chỉ số để không ai so một split đơn với trung bình LOSO trong báo cáo. */
  split_provenance?: SplitProvenance | null;
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

/** Một bước trong quy trình chuẩn bị dữ liệu. */
export interface PrepareStep {
  step: string;
  ok?: boolean;
  returncode?: number;
  started_at?: string;
  finished_at?: string;
  stdout_tail?: string;
  stderr_tail?: string;
}

export interface PreparedSplit {
  split_version: string;
  exists: boolean;
  split_mode?: string | null;
  num_classes?: number | null;
  counts?: Record<string, number> | null;
  class_coverage?: Record<string, number> | null;
  valid_for_research?: boolean | null;
  invalid_reasons?: string[];
}

export interface PrepareReport {
  run_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  manifest_version: string;
  manifest: string;
  profiles: string[];
  current_step: string | null;
  error?: string;
  /** Vấn đề được ghi nhận nhưng KHÔNG chặn quy trình (ví dụ file mồ côi). */
  warnings?: string[];
  started_at?: string;
  finished_at?: string;
  steps: PrepareStep[];
  artifacts: Record<string, {
    deployment: PreparedSplit;
    research: PreparedSplit;
    loso: { protocol: string; folds: string[] };
  }>;
}

/** Mọi lời gọi ở đây đi qua axiosClient, KHÔNG dùng fetch() thô.
 *
 *  Trước đây hook này gọi fetch() trực tiếp và tự gắn Bearer token từ
 *  localStorage. Nhưng hệ thống đã chuyển sang cookie httpOnly — login chủ động
 *  xoá token localStorage — nên header đó luôn rỗng, và quan trọng hơn: fetch()
 *  bỏ qua interceptor echo cookie CSRF. Backend (`csrf_protect` trong
 *  app/main.py) chặn mọi POST/DELETE có cookie đăng nhập mà thiếu header
 *  X-CSRF-Token, nên start/cancel/promote/delete đều trả 403.
 *
 *  Đi qua axiosClient thì được cả gói: CSRF tự động, tự refresh khi 401, và
 *  thông báo lỗi tiếng Việt (`userMessage`) thay vì "Forbidden". */
function errMessage(err: unknown, fallback: string): string {
  if (err && typeof err === 'object') {
    const e = err as { userMessage?: string; response?: { data?: { detail?: unknown } }; message?: string };
    const detail = e.response?.data?.detail;
    if (typeof detail === 'string' && detail) return detail;
    if (e.userMessage) return e.userMessage;
    if (e.message) return e.message;
  }
  return fallback;
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

      const response = await axiosClient.get(`${API_URL}/dataset-info`, { params });
      const data = response.data as DatasetInfo;
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
          setDatasetInfo({ ...data, label_map: map });
        } else {
          setDatasetInfo(data);
        }
      } catch {
        // If classes fetch fails, still set dataset info
        setDatasetInfo(data);
      }
    } catch (err) {
      setError(errMessage(err, 'Không tải được thông tin dataset.'));
    } finally {
      setLoading(false);
    }
  }, []);

  // Bắt đầu training
  const startTraining = useCallback(async (config: TrainingConfig): Promise<TrainingJob | null> => {
    setLoading(true);
    setError(null);
    try {
      const response = await axiosClient.post(`${API_URL}/start`, config);
      return response.data as TrainingJob;
    } catch (err) {
      setError(errMessage(err, 'Không bắt đầu được phiên huấn luyện.'));
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  // Lấy job status
  const getJobStatus = useCallback(async (jobId: string): Promise<TrainingJob | null> => {
    try {
      const response = await axiosClient.get(`${API_URL}/jobs/${jobId}`);
      return response.data as TrainingJob;
    } catch (err) {
      setError(errMessage(err, 'Không đọc được trạng thái phiên huấn luyện.'));
      return null;
    }
  }, []);

  // Lấy metrics
  const getJobMetrics = useCallback(async (jobId: string): Promise<TrainingMetrics[]> => {
    try {
      const response = await axiosClient.get(`${API_URL}/jobs/${jobId}/metrics`);
      return (response.data ?? []) as TrainingMetrics[];
    } catch (err) {
      setError(errMessage(err, 'Không đọc được chỉ số huấn luyện.'));
      return [];
    }
  }, []);

  // Lịch sử jobs (mới nhất trước), kèm username người chạy
  const listJobs = useCallback(async (limit = 100): Promise<TrainingJobListItem[]> => {
    try {
      const response = await axiosClient.get(`${API_URL}/jobs`, { params: { limit } });
      return (response.data ?? []) as TrainingJobListItem[];
    } catch (err) {
      setError(errMessage(err, 'Không tải được lịch sử huấn luyện.'));
      return [];
    }
  }, []);

  // Hủy training job đang chạy/đang chờ
  const cancelTraining = useCallback(async (jobId: string): Promise<TrainingJob | null> => {
    try {
      const response = await axiosClient.post(`${API_URL}/jobs/${jobId}/cancel`);
      return response.data as TrainingJob;
    } catch (err) {
      setError(errMessage(err, 'Không hủy được phiên huấn luyện.'));
      return null;
    }
  }, []);

  // Promote model của job lên realtime (admin only)
  const promoteJob = useCallback(async (jobId: string): Promise<PromoteResponse | null> => {
    try {
      const response = await axiosClient.post(`${API_URL}/jobs/${jobId}/promote`);
      return response.data as PromoteResponse;
    } catch (err) {
      setError(errMessage(err, 'Không đưa được model vào Realtime.'));
      return null;
    }
  }, []);

  // Per-class breakdown + confusion matrix trên test set (Step 7)
  /** Chạy toàn bộ quy trình chuẩn bị: manifest -> kiểm định -> các split. */
  const startDatasetPreparation = useCallback(
    async (dialects?: string[]): Promise<{ run_id: string; manifest_version: string; profiles?: string[] } | null> => {
      try {
        // Gửi phương ngữ, không gửi profile: ánh xạ nằm ở danh mục nhãn phía
        // máy chủ, giữ một bản sao trong giao diện thì nó sẽ lệch khi từ vựng đổi.
        const response = await axiosClient.post(`${API_URL}/dataset/prepare`, { dialects: dialects ?? null });
        return response.data as { run_id: string; manifest_version: string };
      } catch (err) {
        setError(errMessage(err, 'Không bắt đầu được việc chuẩn bị bộ dữ liệu.'));
        return null;
      }
    },
    [],
  );

  const getDatasetPreparation = useCallback(async (runId: string): Promise<PrepareReport | null> => {
    try {
      const response = await axiosClient.get(`${API_URL}/dataset/prepare/${runId}`);
      // Xoá lỗi cũ ngay khi poll thành công trở lại — hàm này bị gọi lặp lại mỗi
      // 3 giây, nên một lần lỗi thoáng qua (ví dụ trùng lúc backend được tạo lại)
      // không được phép kẹt vĩnh viễn trên banner trong khi report vẫn đang cập
      // nhật đúng ở các lần poll sau.
      setError(null);
      return response.data as PrepareReport;
    } catch (err) {
      setError(errMessage(err, 'Không đọc được tiến độ chuẩn bị.'));
      return null;
    }
  }, []);

  const getResearchSplits = useCallback(async (): Promise<ResearchSplit[]> => {
    try {
      const response = await axiosClient.get(`${API_URL}/splits`);
      return (response.data ?? []) as ResearchSplit[];
    } catch (err) {
      setError(errMessage(err, 'Không tải được danh sách split nghiên cứu.'));
      return [];
    }
  }, []);

  const getJobProvenance = useCallback(async (jobId: string): Promise<JobProvenance | null> => {
    try {
      const response = await axiosClient.get(`${API_URL}/jobs/${jobId}/provenance`);
      return response.data as JobProvenance;
    } catch (err) {
      setError(errMessage(err, 'Không đọc được thông tin nguồn gốc model.'));
      return null;
    }
  }, []);

  const getJobEvaluation = useCallback(async (jobId: string): Promise<JobEvaluation | null> => {
    try {
      const response = await axiosClient.get(`${API_URL}/jobs/${jobId}/evaluation`);
      return response.data as JobEvaluation;
    } catch (err) {
      setError(errMessage(err, 'Không đọc được kết quả đánh giá.'));
      return null;
    }
  }, []);

  // Xóa job khỏi lịch sử huấn luyện (chỉ job đã kết thúc: completed/failed/cancelled)
  const deleteJob = useCallback(async (jobId: string): Promise<boolean> => {
    try {
      await axiosClient.delete(`${API_URL}/jobs/${jobId}`);
      return true;
    } catch (err) {
      setError(errMessage(err, 'Không xóa được phiên huấn luyện này.'));
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
    startDatasetPreparation,
    getDatasetPreparation,
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
