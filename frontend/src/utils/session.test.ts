import { describe, it, expect, vi, afterEach } from "vitest";
import {
  createSessionId,
  formatSessionLabel,
  requestNewSession,
  NEW_SESSION_EVENT,
} from "./session";

afterEach(() => {
  vi.useRealTimers();
});

describe("createSessionId", () => {
  // The backend and the dataset CSVs store session_id as epoch milliseconds.
  it("produces a numeric epoch-millisecond string", () => {
    const id = createSessionId();
    expect(id).toMatch(/^\d+$/);
    expect(Number(id)).toBeGreaterThan(1_600_000_000_000);
  });

  it("advances with the clock so a new session is distinguishable", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-21T14:32:00"));
    const first = createSessionId();
    vi.setSystemTime(new Date("2026-07-21T15:10:00"));
    const second = createSessionId();
    expect(second).not.toBe(first);
    expect(Number(second)).toBeGreaterThan(Number(first));
  });
});

describe("formatSessionLabel", () => {
  it("renders the wall-clock start time, zero padded", () => {
    const id = String(new Date("2026-07-21T14:32:00").getTime());
    expect(formatSessionLabel(id)).toBe("14:32");

    const early = String(new Date("2026-07-21T09:05:00").getTime());
    expect(formatSessionLabel(early)).toBe("09:05");
  });

  it("handles midnight without collapsing to a single digit", () => {
    const id = String(new Date("2026-07-21T00:00:00").getTime());
    expect(formatSessionLabel(id)).toBe("00:00");
  });

  it("falls back to a short suffix for ids that are not usable timestamps", () => {
    expect(formatSessionLabel("abcdefghij")).toBe("efghij");
    expect(formatSessionLabel("0")).toBe("0");
    expect(formatSessionLabel("-5")).toBe("-5");
  });

  // Spreadsheet round-trips mangled some stored ids into scientific notation
  // ("1.78E+12"). Number() still parses those, so they render as a real-looking
  // but wrong time rather than being rejected. That is acceptable ONLY because
  // this label is fed live session ids, which always carry full precision --
  // createSessionId never produces such a value. Do not reuse this formatter to
  // display session_id values read back from the dataset CSVs.
  it("parses spreadsheet-mangled ids instead of rejecting them", () => {
    expect(formatSessionLabel("1.78E+12")).toMatch(/^\d{2}:\d{2}$/);
  });

  it("never returns an empty label", () => {
    expect(formatSessionLabel("")).toBe("—");
  });
});

describe("requestNewSession", () => {
  it("dispatches the event capture surfaces listen for", () => {
    const seen: Event[] = [];
    const handler = (e: Event) => seen.push(e);
    window.addEventListener(NEW_SESSION_EVENT, handler);

    requestNewSession();

    window.removeEventListener(NEW_SESSION_EVENT, handler);
    expect(seen).toHaveLength(1);
    expect(seen[0].type).toBe(NEW_SESSION_EVENT);
  });
});
