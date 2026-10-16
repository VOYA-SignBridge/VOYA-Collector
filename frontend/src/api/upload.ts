import axiosClient from "./axiosClient";
import { validateUploadResult } from "./validators";
import type { Result } from "./validators";
import type { UploadResult, CameraUploadPayload } from "../types";

type DebugStatus = 'SUCCESS' | 'FAILURE' | 'IN_PROGRESS';

type DebugLogData = Record<string, unknown>;

type DebugLogger = {
  log?: (entry: {
    timestamp: number;
    operation: string;
    status: DebugStatus;
  } & DebugLogData) => void;
};

type DebugWindow = Window & {
  __voyadebug?: DebugLogger;
};

const extractErrorMessage = (err: unknown, fallback = "Upload failed"): string => {
  type AxiosLikeError = {
    response?: { status?: number; data?: unknown };
    request?: unknown;
    message?: string;
  };

  const axiosErr = err as AxiosLikeError;
  if (axiosErr?.response) {
    const { status, data } = axiosErr.response;
    if (data && typeof data === "object") {
      const detail = (data as { detail?: unknown; message?: unknown }).detail
        ?? (data as { detail?: unknown; message?: unknown }).message;
      if (typeof detail === "string" && detail.trim()) {
        return `HTTP ${status} - ${detail}`;
      }
    }
    return `HTTP ${status} - ${JSON.stringify(data)}`;
  }
  if (axiosErr?.request) {
    return "No response received (request sent)";
  }
  if (axiosErr?.message) {
    return axiosErr.message;
  }
  return fallback;
};

// 4xx responses (validation / QC reject) are deterministic — retrying would
// re-POST the same bad payload. Returns the failure Result to short-circuit
// the retry loop with, or null when the error is retryable (network / 5xx).
const clientErrorResult = (err: unknown): { ok: false; error: string; errorCode?: string } | null => {
  type AxiosLikeError = { response?: { status?: number; data?: unknown } };
  const status = (err as AxiosLikeError)?.response?.status;
  if (typeof status !== "number" || status < 400 || status >= 500) return null;
  const data = (err as AxiosLikeError).response?.data;
  let errorCode: string | undefined;
  if (data && typeof data === "object") {
    const detail = (data as { detail?: unknown }).detail;
    if (detail && typeof detail === "object" && typeof (detail as { code?: unknown }).code === "string") {
      errorCode = (detail as { code: string }).code;
    }
  }
  return { ok: false, error: extractErrorMessage(err), errorCode };
};

// Helper to log to debug panel
const logDebugOperation = (operation: string, status: DebugStatus, data: DebugLogData) => {
  const debugWindow = window as DebugWindow;
  if (debugWindow.__voyadebug?.log) {
    debugWindow.__voyadebug.log({
      timestamp: Date.now(),
      operation,
      status,
      ...data,
    });
  }
};

// Stable hex idempotency key — reused across retries of the same upload so
// the backend can dedupe instead of storing the file twice.
const genUploadUid = (): string => {
  try {
    return crypto.randomUUID().replace(/-/g, "");
  } catch {
    return Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join("");
  }
};

// Video uploads can be large (backend allows up to 1GB) — the axios default
// of 30s caused client timeouts mid-upload followed by full re-uploads.
const UPLOAD_TIMEOUT_MS = 10 * 60 * 1000; // 10 minutes

export const uploadVideo = async (
  file: File,
  user: string,
  label: string,
  dialect?: string,
  onProgress?: (percent: number) => void,
): Promise<Result<UploadResult>> => {
  const startTime = Date.now();
  const sessionId = Math.random().toString(36).substring(7);
  const uploadUid = genUploadUid();
  const formData = new FormData();
  formData.append("file", file);
  formData.append("user", user);
  formData.append("label", label);
  formData.append("upload_uid", uploadUid);
  if (dialect) formData.append('dialect', dialect);

  // Log start
  logDebugOperation('UPLOAD_VIDEO', 'IN_PROGRESS', {
    session_id: sessionId,
    message: `Uploading video: ${file.name}`,
  });

  // retry logic: initial try + 2 retries = 3 attempts
  const maxAttempts = 3;
  const baseDelay = 500; // ms
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      // Let the browser set Content-Type (with boundary). Setting it manually can break the request.
      const res = await axiosClient.post("/upload/video", formData, {
        timeout: UPLOAD_TIMEOUT_MS,
        onUploadProgress: (e) => {
          if (onProgress && e.total) {
            onProgress(Math.round((e.loaded / e.total) * 100));
          }
        },
      });
      const result = validateUploadResult(res.data);
      
      if (result.ok) {
        const duration = Date.now() - startTime;
        logDebugOperation('UPLOAD_VIDEO', 'SUCCESS', {
          session_id: sessionId,
          job_id: result.data?.id,
          message: result.data?.message,
          response: result.data,
          duration_ms: duration,
        });
      } else {
        logDebugOperation('UPLOAD_VIDEO', 'FAILURE', {
          session_id: sessionId,
          error: result.error,
          duration_ms: Date.now() - startTime,
        });
      }
      return result;
    } catch (err: unknown) {
      const clientErr = clientErrorResult(err);
      // If 4xx or this is the last attempt, return a helpful error message
      if (clientErr || attempt === maxAttempts) {
        const failure = clientErr ?? { ok: false as const, error: extractErrorMessage(err) };
        logDebugOperation('UPLOAD_VIDEO', 'FAILURE', {
          session_id: sessionId,
          error: failure.error,
          error_code: failure.errorCode,
          duration_ms: Date.now() - startTime,
        });
        return failure;
      }
      // exponential backoff with jitter
      const jitter = Math.random() * 100;
      const delay = baseDelay * 2 ** (attempt - 1) + jitter;
      logDebugOperation('UPLOAD_VIDEO', 'IN_PROGRESS', {
        session_id: sessionId,
        message: `Retry attempt ${attempt}/${maxAttempts}`,
      });
      await new Promise((r) => setTimeout(r, delay));
    }
  }
  // unreachable but typed
  return { ok: false, error: "Upload failed" };
};

export const uploadCamera = async (payload: CameraUploadPayload): Promise<Result<UploadResult>> => {
  const startTime = Date.now();
  const sessionId = payload.session_id || Math.random().toString(36).substring(7);

  // Log start
  logDebugOperation('UPLOAD_CAMERA', 'IN_PROGRESS', {
    session_id: sessionId,
    message: `Processing ${(payload.frames || []).length} camera frames`,
  });

  const maxAttempts = 3;
  const baseDelay = 500;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const res = await axiosClient.post("/upload/camera", payload);
      const result = validateUploadResult(res.data);

      if (result.ok) {
        const duration = Date.now() - startTime;
        logDebugOperation('UPLOAD_CAMERA', 'SUCCESS', {
          session_id: sessionId,
          job_id: result.data?.id,
          message: result.data?.message,
          response: result.data,
          duration_ms: duration,
        });
      } else {
        logDebugOperation('UPLOAD_CAMERA', 'FAILURE', {
          session_id: sessionId,
          error: result.error,
          duration_ms: Date.now() - startTime,
        });
      }
      return result;
    } catch (err: unknown) {
      const clientErr = clientErrorResult(err);
      if (clientErr || attempt === maxAttempts) {
        const failure = clientErr ?? { ok: false as const, error: extractErrorMessage(err) };
        logDebugOperation('UPLOAD_CAMERA', 'FAILURE', {
          session_id: sessionId,
          error: failure.error,
          error_code: failure.errorCode,
          duration_ms: Date.now() - startTime,
        });
        return failure;
      }
      const jitter = Math.random() * 100;
      const delay = baseDelay * 2 ** (attempt - 1) + jitter;
      logDebugOperation('UPLOAD_CAMERA', 'IN_PROGRESS', {
        session_id: sessionId,
        message: `Retry attempt ${attempt}/${maxAttempts}`,
      });
      await new Promise((r) => setTimeout(r, delay));
    }
  }
  return { ok: false, error: "Upload failed" };
};
