/**
 * Background job status.
 *
 * `POST /upload/video/process` hands back a `job_id` and returns immediately —
 * the actual landmark extraction runs in a Celery worker. Until now nothing in
 * the UI ever asked what happened to that job: the id was handed to DebugPanel
 * to print and otherwise dropped, so a contributor who uploaded a video got no
 * feedback at all and the page looked stuck.
 *
 * Note the path is bare `/jobs/{id}`, not `/api/v1/jobs/{id}`. Both are
 * mounted; `/jobs` is in nginx's proxied prefix list, and
 * api/__tests__/nginxRouteCoverage.test.ts pins it as backend-routed.
 */

import { tr } from "../i18n";
import axiosClient from "./axiosClient";
import { validateJobStatus } from "./validators";
import type { Result } from "./validators";
import type { JobStatus } from "../types";
import { isJobFinished } from "../types";

export const getJobStatus = async (jobId: string): Promise<Result<JobStatus>> => {
  const res = await axiosClient.get(`/jobs/${encodeURIComponent(jobId)}`);
  return validateJobStatus(res.data);
};

export interface PollOptions {
  /** Milliseconds between polls. Default 2000 — video processing is seconds-to-minutes. */
  intervalMs?: number;
  /** Give up after this long so a lost job cannot poll forever. Default 10 min. */
  timeoutMs?: number;
  /** Called after every successful poll, for progress UI. */
  onUpdate?: (status: JobStatus) => void;
  /** Abort from the caller (component unmount). */
  signal?: AbortSignal;
}

/**
 * Poll until the job reaches a terminal Celery state.
 *
 * Transient errors are tolerated rather than fatal: a single failed poll during
 * a backend restart should not make the UI declare the job dead while the
 * worker is still chewing on it. Only a run of consecutive failures gives up.
 */
export async function pollJobUntilDone(
  jobId: string,
  opts: PollOptions = {}
): Promise<Result<JobStatus>> {
  const interval = opts.intervalMs ?? 2000;
  const timeout = opts.timeoutMs ?? 10 * 60 * 1000;
  const startedAt = Date.now();
  let consecutiveErrors = 0;

  for (;;) {
    if (opts.signal?.aborted) {
      return { ok: false, error: tr("Đã hủy theo dõi tiến trình") };
    }
    if (Date.now() - startedAt > timeout) {
      return { ok: false, error: tr("Quá thời gian chờ xử lý video") };
    }

    const res = await getJobStatus(jobId);
    if (res.ok) {
      consecutiveErrors = 0;
      opts.onUpdate?.(res.data);
      if (isJobFinished(res.data.status)) return res;
    } else {
      consecutiveErrors += 1;
      // Three misses in a row (~6s) is a real outage, not a blip.
      if (consecutiveErrors >= 3) return res;
    }

    await new Promise<void>((resolve) => setTimeout(resolve, interval));
  }
}
