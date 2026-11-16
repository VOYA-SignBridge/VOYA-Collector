import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

/**
 * Proves the idle auto-logout cap is now 3 HOURS, not the old 90 minutes:
 *  - at 90 min idle  -> still logged in (would have logged out under the old cap)
 *  - past 3 hours    -> logged out (apiLogout called + local state cleared)
 *
 * Uses fake timers so "3 hours" runs instantly; logs the observed call counts.
 */

const apiLogout = vi.fn().mockResolvedValue(undefined);
const clearAuthToken = vi.fn();
let remembered = false;

vi.mock('../../api/auth', () => ({ logout: () => apiLogout() }));
vi.mock('../../api/axiosClient', () => ({
  clearAuthToken: () => clearAuthToken(),
  isRememberedSession: () => remembered,
}));

import { useIdleLogout } from '../useIdleLogout';

describe('useIdleLogout — 3-hour idle cap', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'setTimeout', 'clearTimeout', 'Date'] });
    localStorage.clear();
    apiLogout.mockClear();
    clearAuthToken.mockClear();
    remembered = false;
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('stays logged in at 90 min, logs out only after 3 hours', async () => {
    renderHook(() => useIdleLogout(true));

    // 90 minutes idle — the OLD limit. Must NOT log out anymore.
    // (async advance flushes the promise chain inside the logout path)
    await vi.advanceTimersByTimeAsync(90 * 60_000);
    console.log('[evidence] at  90 min idle: apiLogout calls =', apiLogout.mock.calls.length);
    expect(apiLogout).not.toHaveBeenCalled();

    // Cross the 3-hour boundary (total 181 min).
    await vi.advanceTimersByTimeAsync(91 * 60_000);
    console.log('[evidence] at 181 min idle: apiLogout calls =', apiLogout.mock.calls.length,
      '| clearAuthToken calls =', clearAuthToken.mock.calls.length);
    expect(apiLogout).toHaveBeenCalled();
    expect(clearAuthToken).toHaveBeenCalled();
  });

  it('never idle-logs-out a session the user chose to remember', async () => {
    remembered = true;
    renderHook(() => useIdleLogout(true));
    await vi.advanceTimersByTimeAsync(24 * 60 * 60_000); // a whole day idle
    expect(apiLogout).not.toHaveBeenCalled();
    expect(clearAuthToken).not.toHaveBeenCalled();
  });

  it('does not log out a disabled (guest) session', async () => {
    renderHook(() => useIdleLogout(false));
    await vi.advanceTimersByTimeAsync(4 * 60 * 60_000); // 4 hours
    console.log('[evidence] disabled hook after 4h: apiLogout calls =', apiLogout.mock.calls.length);
    expect(apiLogout).not.toHaveBeenCalled();
  });
});
