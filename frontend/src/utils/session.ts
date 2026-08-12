/**
 * Collection-session identity.
 *
 * Every uploaded sample carries a `session_id` identifying the sitting it was
 * recorded in. That value is the grouping key the dataset splits depend on:
 * takes recorded back to back share signer, lighting, framing and pose, so they
 * are near-duplicates. If takes from one sitting land on both sides of a split
 * boundary the model has effectively seen the test sample during training and
 * the reported score is inflated.
 *
 * The practical consequence for the UI: when a new signer sits down, the
 * collector MUST start a new session, otherwise two people's recordings are
 * filed under one group and the grouping silently stops meaning anything.
 */

/** Window event asking any mounted capture surface to start a fresh session. */
export const NEW_SESSION_EVENT = "voya:new-session";

/**
 * Session ids are epoch milliseconds as a string. Kept numeric because the
 * dataset CSVs and backend already store them that way.
 */
export const createSessionId = (): string => Date.now().toString();

const pad2 = (n: number) => String(n).padStart(2, "0");

/**
 * Short human label for a session — the wall-clock time it started.
 * A collector recognises "14:32" far more readily than a 13-digit id; the full
 * id stays available as a tooltip for correlating with stored samples.
 */
export function formatSessionLabel(sessionId: string): string {
  const ms = Number(sessionId);
  if (!Number.isFinite(ms) || ms <= 0) return sessionId.slice(-6) || "—";

  const started = new Date(ms);
  if (Number.isNaN(started.getTime())) return sessionId.slice(-6) || "—";

  return `${pad2(started.getHours())}:${pad2(started.getMinutes())}`;
}

/** Ask whichever capture surface is mounted to roll over to a new session. */
export function requestNewSession(): void {
  window.dispatchEvent(new CustomEvent(NEW_SESSION_EVENT));
}
