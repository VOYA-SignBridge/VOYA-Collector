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

export const uploadVideo = async (file: File, user: string, label: string, dialect?: string): Promise<Result<UploadResult>> => {
  const startTime = Date.now();
  const sessionId = Math.random().toString(36).substring(7);
  const formData = new FormData();
  formData.append("file", file);
  formData.append("user", user);
  formData.append("label", label);
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
      const res = await axiosClient.post("/upload/video", formData);
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
      // If this is the last attempt, return a helpful error message
      if (attempt === maxAttempts) {
        const errorMsg = extractErrorMessage(err);
        logDebugOperation('UPLOAD_VIDEO', 'FAILURE', {
          session_id: sessionId,
          error: errorMsg,
          duration_ms: Date.now() - startTime,
        });
        return { ok: false, error: errorMsg };
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
  const sessionUid = payload.session_uid || Math.random().toString(36).substring(7);

  // Log start
  logDebugOperation('UPLOAD_CAMERA', 'IN_PROGRESS', {
    session_uid: sessionUid,
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
          session_uid: sessionUid,
          job_id: result.data?.id,
          message: result.data?.message,
          response: result.data,
          duration_ms: duration,
        });
      } else {
        logDebugOperation('UPLOAD_CAMERA', 'FAILURE', {
          session_uid: sessionUid,
          error: result.error,
          duration_ms: Date.now() - startTime,
        });
      }
      return result;
    } catch (err: unknown) {
      if (attempt === maxAttempts) {
        const errorMsg = extractErrorMessage(err);
        logDebugOperation('UPLOAD_CAMERA', 'FAILURE', {
          session_uid: sessionUid,
          error: errorMsg,
          duration_ms: Date.now() - startTime,
        });
        return { ok: false, error: errorMsg };
      }
      const jitter = Math.random() * 100;
      const delay = baseDelay * 2 ** (attempt - 1) + jitter;
      logDebugOperation('UPLOAD_CAMERA', 'IN_PROGRESS', {
        session_uid: sessionUid,
        message: `Retry attempt ${attempt}/${maxAttempts}`,
      });
      await new Promise((r) => setTimeout(r, delay));
    }
  }
  return { ok: false, error: "Upload failed" };
};
