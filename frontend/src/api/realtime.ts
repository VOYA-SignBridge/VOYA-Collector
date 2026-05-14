import axiosClient from "./axiosClient";
import type { Result } from "./validators";

/**
 * Realtime inference API contract.
 *
 * Frontend must send RAW landmark-derived features only.
 * - No normalization
 * - No mirroring
 * - No handedness swapping
 *
 * Payload shape is fixed for compatibility with training pipeline:
 * - frames: 60
 * - feature_dim: 126
 */
export interface RealtimePredictRequest {
  frames: number[][];
}

export interface RealtimePredictResponse {
  label: string;
  confidence: number;
}

const isObject = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null;

const isFiniteNumber = (v: unknown): v is number =>
  typeof v === "number" && Number.isFinite(v);

/**
 * Minimal runtime validator to prevent UI crashes from malformed backend data.
 * Does not enforce label set or confidence range.
 */
export function validateRealtimePredictResponse(data: unknown): Result<RealtimePredictResponse> {
  try {
    if (!isObject(data)) throw new Error("Invalid realtime predict response");

    const label = data.label;
    const confidence = data.confidence;

    if (typeof label !== "string" || !label.trim()) {
      throw new Error("Invalid response: missing label");
    }
    if (!isFiniteNumber(confidence)) {
      throw new Error("Invalid response: missing confidence");
    }

    return { ok: true, data: { label, confidence } };
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    return { ok: false, error: msg };
  }
}

/**
 * POST /realtime/predict
 *
 * Request policy (enforced by realtime runtime component, not here):
 * - debounce 150–250ms
 * - only one in-flight request; if in-flight => SKIP
 */
export async function realtimePredict(
  payload: RealtimePredictRequest
): Promise<Result<RealtimePredictResponse>> {
  const res = await axiosClient.post("/realtime/predict", payload);
  return validateRealtimePredictResponse(res.data);
}
