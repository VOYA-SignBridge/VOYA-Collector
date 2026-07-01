import axiosClient from "./axiosClient";
import type { Result } from "./validators";

/**
 * Realtime model metadata (from GET /api/v1/realtime/models)
 *
 * AI Studio NOTE: import this type directly — do NOT redefine it in types.ts or aiStudio.ts.
 *   import type { RealtimeModel } from "../api/realtime";
 *
 * Join key to DB model_versions: model.dialect === realtimeModel.dialect
 * Do NOT compare model_family against realtimeModel.id — they differ ("hoa-de-tcn" ≠ "hoa-de").
 */
export interface RealtimeModel {
  id: string;
  name: string;
  language: string;
  dialect: string;
}

/**
 * Realtime inference API contract.
 *
 * Frontend must send RAW landmark-derived features with anatomical hand slots.
 * - No normalization
 * - No mirroring
 * - MediaPipe handedness is swapped into left/right anatomical slots
 *
 * Payload shape is fixed for compatibility with training pipeline:
 * - frames: 60
 * - feature_dim: 126
 */
export interface RealtimePredictRequest {
  model_id: string;
  frames: number[][];
}

export interface RealtimePredictResponse {
  label: string;
  confidence: number;
  label_key: string;
}

const isObject = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null;

const isFiniteNumber = (v: unknown): v is number =>
  typeof v === "number" && Number.isFinite(v);

/**
 * Generate a unique request ID for observability.
 * Falls back to timestamp + random for older Electron/embedded Chromium without crypto.randomUUID.
 */
function createRequestId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

/**
 * Minimal runtime validator to prevent UI crashes from malformed backend data.
 * Does not enforce label set or confidence range.
 */
export function validateRealtimePredictResponse(data: unknown): Result<RealtimePredictResponse> {
  try {
    if (!isObject(data)) throw new Error("Invalid realtime predict response");

    const label = data.label;
    const confidence = data.confidence;
    const label_key = data.label_key;

    if (typeof label !== "string" || !label.trim()) {
      throw new Error("Invalid response: missing label");
    }
    if (!isFiniteNumber(confidence)) {
      throw new Error("Invalid response: missing confidence");
    }
    if (typeof label_key !== "string" || !label_key.trim()) {
      throw new Error("Invalid response: missing label_key");
    }

    return { ok: true, data: { label, confidence, label_key } };
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    return { ok: false, error: msg };
  }
}

/**
 * Validate models list response.
 */
function validateRealtimeModels(data: unknown): Result<RealtimeModel[]> {
  try {
    if (!Array.isArray(data)) throw new Error("Invalid models response");

    const models: RealtimeModel[] = data.map((item, idx) => {
      if (!isObject(item)) throw new Error(`Model[${idx}]: invalid object`);
      const id = item.id;
      const name = item.name;
      const language = item.language;
      const dialect = item.dialect;

      if (typeof id !== "string" || !id.trim()) {
        throw new Error(`Model[${idx}]: missing id`);
      }
      if (typeof name !== "string" || !name.trim()) {
        throw new Error(`Model[${idx}]: missing name`);
      }
      if (typeof language !== "string") {
        throw new Error(`Model[${idx}]: missing language`);
      }
      if (typeof dialect !== "string") {
        throw new Error(`Model[${idx}]: missing dialect`);
      }

      return { id: id.trim(), name: name.trim(), language, dialect };
    });

    return { ok: true, data: models };
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    return { ok: false, error: msg };
  }
}

/**
 * GET /api/v1/realtime/models
 *
 * Fetch available realtime models from backend.
 * Returns list of model metadata for UI dropdown.
 */
export async function fetchRealtimeModels(): Promise<Result<RealtimeModel[]>> {
  try {
    if (import.meta.env.DEV) console.debug("[realtime] fetching models...");
    const res = await axiosClient.get("/api/v1/realtime/models");
    const result = validateRealtimeModels(res.data);
    if (result.ok && import.meta.env.DEV) {
      console.debug("[realtime] models loaded:", result.data.length, "models");
    }
    return result;
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    console.warn("[realtime] models fetch failed:", msg);
    return { ok: false, error: msg };
  }
}

/**
 * POST /api/v1/realtime/predict
 *
 * Request policy (enforced by realtime runtime component, not here):
 * - debounce 150–250ms
 * - only one in-flight request; if in-flight => SKIP
 * - request_id sent via X-Request-ID header for observability
 */
export async function realtimePredict(
  payload: RealtimePredictRequest
): Promise<Result<RealtimePredictResponse>> {
  try {
    const request_id = createRequestId();
    if (import.meta.env.DEV) {
      console.debug("[realtime] predict req_id=%s model=%s", request_id, payload.model_id);
    }

    const res = await axiosClient.post("/api/v1/realtime/predict", payload, {
      headers: {
        "X-Request-ID": request_id,
      },
    });

    return validateRealtimePredictResponse(res.data);
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    return { ok: false, error: msg };
  }
}
