import type { Session, Label, UploadResult, JobStatus } from "../types";

export type Result<T> = { ok: true; data: T } | { ok: false; error: string };

export function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

export function validateLabels(data: unknown): Result<Label[]> {
  try {
    if (!Array.isArray(data)) throw new Error("Invalid labels response");
    const out = data.map((item) => {
      if (!isObject(item)) throw new Error("Invalid label item");
      return item as unknown as Label;
    });
    return { ok: true, data: out };
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    return { ok: false, error: msg };
  }
}

export function validateLabel(data: unknown): Result<Label> {
  try {
    if (!isObject(data)) throw new Error("Invalid label response");
    return { ok: true, data: data as unknown as Label };
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    return { ok: false, error: msg };
  }
}

export function validateSessions(data: unknown): Result<Session[]> {
  try {
    if (!Array.isArray(data)) throw new Error("Invalid sessions response");
    const out = data.map((item) => {
      if (!isObject(item)) throw new Error("Invalid session item");
      const s = item as Partial<Session>;
      if (typeof s.session_id !== "string") throw new Error("Session missing session_id");
      return {
        session_id: s.session_id,
        user: String(s.user ?? ""),
        labels: Array.isArray(s.labels) ? (s.labels as string[]) : [],
        samples_count: Number(s.samples_count ?? 0),
        created_at: String(s.created_at ?? ""),
      } as Session;
    });
    return { ok: true, data: out };
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    return { ok: false, error: msg };
  }
}

export function validateJobStatus(data: unknown): Result<JobStatus> {
  try {
    if (!isObject(data)) throw new Error("Invalid job status response");
    return { ok: true, data: data as JobStatus };
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    return { ok: false, error: msg };
  }
}

export function validateUploadResult(data: unknown): Result<UploadResult> {
  try {
    if (!isObject(data)) throw new Error("Invalid upload response");
    return { ok: true, data: data as UploadResult };
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    return { ok: false, error: msg };
  }
}
