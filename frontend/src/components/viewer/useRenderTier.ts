import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Tiered rendering (docs/PHASE2_PLAN_3D_VIEWER.md §3–4):
 *   "3d"    — flesh 3D hands (three.js)          — strong devices
 *   "2d"    — 2D canvas skeleton                 — mid devices
 *   "video" — server pre-rendered skeleton mp4   — weak/hot devices, Eco mode
 *
 * The browser cannot read CPU temperature; the trustworthy "device is hot"
 * signal is OS throttling showing up as a SUSTAINED fps drop, so the 3D
 * viewer reports its live render fps here. Downgrades are one-way within a
 * page visit (no 3D↔2D oscillation); the user can always override manually.
 */

export type RenderTier = "3d" | "2d" | "video";
export type TierChoice = RenderTier | "auto";

export const ECO_MODE_KEY = "voya_viewer_eco";

const LOW_FPS_THRESHOLD = 24;
const LOW_FPS_SECONDS_TO_DOWNGRADE = 3;

interface NavigatorExtras {
  hardwareConcurrency?: number;
  deviceMemory?: number;
  getBattery?: () => Promise<{ charging: boolean; level: number }>;
}

export function isEcoMode(): boolean {
  try {
    return localStorage.getItem(ECO_MODE_KEY) === "1";
  } catch {
    return false;
  }
}

export function setEcoMode(on: boolean): void {
  try {
    localStorage.setItem(ECO_MODE_KEY, on ? "1" : "0");
  } catch {
    /* private mode — non-fatal */
  }
}

/** Pick the starting tier from cheap hardware signals (no fps probe: a probe
 *  at load time cannot see the throttling that appears once the device heats
 *  up — the live fps monitor below handles that case). */
export function initialTier(nav: NavigatorExtras = navigator as NavigatorExtras): RenderTier {
  if (isEcoMode()) return "video";
  const cores = nav.hardwareConcurrency ?? 4;
  const memGb = nav.deviceMemory ?? 4;
  if (cores < 4 || memGb <= 2) return "2d";
  return "3d";
}

export interface RenderTierState {
  /** Effective tier the players should render with. */
  tier: RenderTier;
  /** What the user picked in the dropdown ("auto" = let the monitor decide). */
  choice: TierChoice;
  setChoice: (choice: TierChoice) => void;
  eco: boolean;
  setEco: (on: boolean) => void;
  /** Called by the 3D render loop once per rendered frame. */
  reportFps: () => void;
  /** True when an automatic downgrade happened (to explain it in the UI). */
  downgraded: boolean;
}

export function useRenderTier(): RenderTierState {
  const [choice, setChoice] = useState<TierChoice>("auto");
  const [eco, setEcoState] = useState<boolean>(isEcoMode);
  const [autoTier, setAutoTier] = useState<RenderTier>(initialTier);
  const [downgraded, setDowngraded] = useState(false);

  // On battery power and nearly empty → don't even start the GPU path.
  useEffect(() => {
    const nav = navigator as NavigatorExtras;
    if (!nav.getBattery) return;
    let cancelled = false;
    nav
      .getBattery()
      .then((battery) => {
        if (!cancelled && !battery.charging && battery.level < 0.2) {
          setAutoTier((current) => (current === "3d" ? "2d" : current));
        }
      })
      .catch(() => {
        /* battery API unavailable */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Sustained-low-fps monitor (1s buckets; N consecutive slow seconds → drop).
  const bucketStart = useRef(performance.now());
  const bucketFrames = useRef(0);
  const slowSeconds = useRef(0);

  const reportFps = useCallback(() => {
    bucketFrames.current += 1;
    const now = performance.now();
    const elapsed = now - bucketStart.current;
    if (elapsed < 1000) return;

    const avgFps = (bucketFrames.current * 1000) / elapsed;
    bucketFrames.current = 0;
    bucketStart.current = now;

    if (avgFps < LOW_FPS_THRESHOLD) {
      slowSeconds.current += 1;
      if (slowSeconds.current >= LOW_FPS_SECONDS_TO_DOWNGRADE) {
        slowSeconds.current = 0;
        setAutoTier((current) => {
          if (current !== "3d") return current;
          setDowngraded(true);
          return "2d";
        });
      }
    } else {
      slowSeconds.current = 0;
    }
  }, []);

  const setEco = useCallback((on: boolean) => {
    setEcoMode(on);
    setEcoState(on);
  }, []);

  const tier: RenderTier =
    choice !== "auto" ? choice : eco ? "video" : autoTier;

  return { tier, choice, setChoice, eco, setEco, reportFps, downgraded };
}
