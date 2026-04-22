import axiosClient from "./axiosClient";
import { validateUploadResult } from "./validators";
import type { Result } from "./validators";
import type { UploadResult, CameraUploadPayload } from "../types";

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

export const uploadVideo = async (file: File, user: string, label: string, dialect?: string): Promise<Result<UploadResult>> => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("user", user);
  formData.append("label", label);
  if (dialect) formData.append('dialect', dialect);

  // Debug: log FormData keys and file info before sending (helps diagnose missing fields in browser)
  try {
    const debugEntries: Record<string, string> = {};
    // formData.entries() may not be serializable directly; normalize to names
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    for (const [k, v] of (formData as any).entries()) {
      if (v instanceof File) debugEntries[k] = `${v.name} (${v.size} bytes)`;
      else debugEntries[k] = String(v);
    }
    // Use console.debug so it appears in browser devtools (and not in prod logs usually)
    // Note: this will run in the browser when uploadVideo is invoked from frontend code
    // and helps confirm the fields actually exist before the request leaves the client.
    console.debug("[uploadVideo] formData entries:", debugEntries);
    } catch (err) {
      // ignore debug failures
      console.debug('uploadVideo debug failed', err);
    }

  // retry logic: initial try + 2 retries = 3 attempts
  const maxAttempts = 3;
  const baseDelay = 500; // ms
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      // Let the browser set Content-Type (with boundary). Setting it manually can break the request.
      const res = await axiosClient.post("/upload/video", formData);
      return validateUploadResult(res.data);
    } catch (err: unknown) {
      // If this is the last attempt, return a helpful error message
      if (attempt === maxAttempts) {
        return { ok: false, error: extractErrorMessage(err) };
      }
      // exponential backoff with jitter
      const jitter = Math.random() * 100;
      const delay = baseDelay * 2 ** (attempt - 1) + jitter;
      await new Promise((r) => setTimeout(r, delay));
    }
  }
  // unreachable but typed
  return { ok: false, error: "Upload failed" };
};

export const uploadCamera = async (payload: CameraUploadPayload): Promise<Result<UploadResult>> => {
  const maxAttempts = 3;
  const baseDelay = 500;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const res = await axiosClient.post("/upload/camera", payload);
      return validateUploadResult(res.data);
    } catch (err: unknown) {
      if (attempt === maxAttempts) {
        return { ok: false, error: extractErrorMessage(err) };
      }
      const jitter = Math.random() * 100;
      const delay = baseDelay * 2 ** (attempt - 1) + jitter;
      await new Promise((r) => setTimeout(r, delay));
    }
  }
  return { ok: false, error: "Upload failed" };
};
