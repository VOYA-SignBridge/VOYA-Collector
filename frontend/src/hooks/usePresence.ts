import { useEffect, useRef } from "react";
import apiClient from "../api/axiosClient";

const PING_MS = 30_000;        // heartbeat: keeps the session "online" live
const GPS_REFRESH_MS = 300_000; // re-read GPS every 5 min to track movement

type Coords = { lat: number; lon: number; accuracy: number };

/**
 * Presence + precise-location reporter.
 *
 * While `enabled`, sends a lightweight heartbeat to /api/v1/presence every 30s
 * so the admin activity monitor shows the user as reliably online (even with an
 * idle-but-open tab). If the user grants the browser's location permission
 * (opt-in, one native prompt), each heartbeat also carries a precise GPS fix —
 * far more accurate than IP geolocation. Denial simply falls back to IP geo.
 *
 * Requires a secure context (HTTPS or localhost); over ngrok's HTTPS it works.
 */
export function usePresence(enabled: boolean) {
  const coords = useRef<Coords | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let stopped = false;

    const ping = () => {
      if (stopped) return;
      const body = coords.current
        ? { lat: coords.current.lat, lon: coords.current.lon, accuracy: coords.current.accuracy }
        : {};
      apiClient.post("/api/v1/presence", body).catch(() => {});
    };

    const readGps = (thenPing: boolean) => {
      if (!("geolocation" in navigator)) return;
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          coords.current = {
            lat: pos.coords.latitude,
            lon: pos.coords.longitude,
            accuracy: pos.coords.accuracy,
          };
          if (thenPing) ping();
        },
        () => { /* denied / unavailable — IP geolocation is the fallback */ },
        { enableHighAccuracy: true, timeout: 10_000, maximumAge: 60_000 }
      );
    };

    readGps(true);          // one-time permission prompt + first precise ping
    ping();                 // immediate heartbeat (even before GPS resolves)
    const pingId = window.setInterval(ping, PING_MS);
    const gpsId = window.setInterval(() => readGps(false), GPS_REFRESH_MS);

    return () => {
      stopped = true;
      window.clearInterval(pingId);
      window.clearInterval(gpsId);
    };
  }, [enabled]);
}
