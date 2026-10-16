import { useEffect, useRef } from "react";
import { logout as apiLogout } from "../api/auth";
import { clearAuthToken } from "../api/axiosClient";

/**
 * Inactivity auto-logout.
 *
 * Enforces a hard cap on how long a session may sit idle. "Idle" means no
 * genuine user interaction (mouse / keyboard / touch / scroll) — background
 * heartbeats and admin polling do NOT count, so an open-but-untouched tab is
 * still logged out on schedule. This is the precise, primary enforcer; the
 * server's short refresh-token TTL is the backstop for when JS can't run.
 *
 * Cross-tab: the last-activity timestamp lives in localStorage, so activity in
 * ANY tab keeps every tab alive, and a logout in one tab cascades to the others
 * (they lose the auth cookies and drop to the login screen on their next call).
 *
 * On timeout it revokes the session server-side, clears local state, and fires
 * a `voya:idle-logout` event that <SecurityNotices> turns into a friendly
 * "your session ended due to inactivity" notice.
 */
// 3-hour idle cap. Must stay in lockstep with the server backstop
// (REFRESH_TOKEN_EXPIRE_MINUTES): if the server TTL were shorter, an idle user
// would be logged out server-side before this timer fires.
const IDLE_LIMIT_MS =
  Number(import.meta.env.VITE_IDLE_TIMEOUT_MINUTES || 180) * 60_000;
const ACTIVITY_KEY = "voya:last-activity";
const CHECK_MS = 30_000; // how often we evaluate the idle deadline
const WRITE_THROTTLE_MS = 15_000; // don't touch localStorage on every mousemove

const ACTIVITY_EVENTS: (keyof WindowEventMap)[] = [
  "mousedown",
  "mousemove",
  "keydown",
  "wheel",
  "touchstart",
  "scroll",
  "click",
];

export function useIdleLogout(enabled: boolean) {
  const lastWrite = useRef(0);
  const firing = useRef(false);

  useEffect(() => {
    if (!enabled) return;
    firing.current = false;

    const readStamp = (): number => {
      try {
        const raw = localStorage.getItem(ACTIVITY_KEY);
        const v = raw ? Number(raw) : NaN;
        return Number.isFinite(v) ? v : 0;
      } catch {
        return 0;
      }
    };
    const stamp = (ts: number) => {
      try {
        localStorage.setItem(ACTIVITY_KEY, String(ts));
      } catch {
        /* private mode / quota — the interval check simply won't fire */
      }
    };

    // Seed a baseline so we never log out a brand-new session immediately.
    stamp(Date.now());

    const onActivity = () => {
      const t = Date.now();
      if (t - lastWrite.current < WRITE_THROTTLE_MS) return;
      lastWrite.current = t;
      stamp(t);
    };

    const fire = async () => {
      if (firing.current) return;
      firing.current = true;
      try {
        await apiLogout();
      } catch {
        /* best-effort — clear locally regardless */
      }
      try {
        localStorage.removeItem(ACTIVITY_KEY);
      } catch {
        /* ignore */
      }
      clearAuthToken(); // emits voya:auth-change → AuthProvider drops the user
      window.dispatchEvent(new CustomEvent("voya:idle-logout"));
    };

    const check = () => {
      const last = readStamp();
      if (!last) {
        stamp(Date.now());
        return;
      }
      if (Date.now() - last >= IDLE_LIMIT_MS) fire();
    };

    ACTIVITY_EVENTS.forEach((e) =>
      window.addEventListener(e, onActivity, { passive: true })
    );
    // A tab that was hidden past the deadline logs out the moment it's refocused.
    const onVisible = () => {
      if (!document.hidden) check();
    };
    document.addEventListener("visibilitychange", onVisible);

    const id = window.setInterval(check, CHECK_MS);
    return () => {
      window.clearInterval(id);
      ACTIVITY_EVENTS.forEach((e) => window.removeEventListener(e, onActivity));
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [enabled]);
}
