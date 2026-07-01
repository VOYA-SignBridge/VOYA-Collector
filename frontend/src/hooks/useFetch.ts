import { useCallback, useEffect, useState } from "react";
import type { Result } from "../api/validators";

/**
 * Base data-fetching hook for AI Studio hooks.
 *
 * CONVENTION: All hooks under src/hooks/ai-studio/ must follow this pattern.
 *
 * Safety guarantees:
 *  1. AbortController.abort() is called on cleanup — prevents state updates
 *     on unmounted components (React 18 strict-mode safe).
 *  2. signal.aborted is checked before every setState call — prevents stale
 *     closures from race conditions when deps change rapidly.
 *  3. `rev` increment via refetch() re-triggers the effect without changing deps.
 *
 * Usage:
 *   const { data, loading, error, refetch } = useFetch(() => listModels(), [])
 *
 * Note: The fetcher function does NOT receive the AbortSignal because existing
 * axios calls do not yet forward it to the HTTP layer. The signal is used only
 * to suppress post-unmount state updates. If axios calls are updated to support
 * cancellation, add `signal` as a parameter to fetcher and forward it.
 *
 * For polling (e.g. useExperiments auto-poll when status === "running"):
 *   Implement polling inside the consuming hook using setInterval + clearInterval.
 *   Call refetch() from the interval callback.
 *   Clear the interval in the useEffect cleanup function.
 *
 * For module-level cache (e.g. useModels):
 *   Declare a Map<string, { data: T; fetchedAt: number }> at module level.
 *   Check cache before calling the API.
 *   Clear cache entries after mutating operations (updateModelStatus).
 */
export function useFetch<T>(
  fetcher: () => Promise<Result<T>>,
  deps: readonly unknown[]
): { data: T | null; loading: boolean; error: string | null; refetch: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rev, setRev] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    fetcher()
      .then((result) => {
        if (controller.signal.aborted) return;
        if (result.ok) {
          setData(result.data);
          setError(null);
        } else {
          setError(result.error);
        }
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, rev]);

  const refetch = useCallback(() => setRev((r) => r + 1), []);

  return { data, loading, error, refetch };
}
