import { describe, it, expect } from "vitest";

/** Mirrors the two normalizers in FullscreenCaptureModal. */
const normalizeText = (value: string) =>
  value
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

const normalizeAlphabetText = (value: string) =>
  value.normalize("NFC").trim().toLowerCase();

const CATALOG = ["A", "B", "D", "E", "O", "U"]; // no diacritic letters recorded yet

const findRow = (typed: string, normalize: (v: string) => string) =>
  CATALOG.find((row) => normalize(row) === normalize(typed));

describe("fingerspelling label matching", () => {
  it("no longer claims an unrecorded diacritic letter already exists", () => {
    // The reported bug: typing Ă reported A's sample count.
    for (const letter of ["Ă", "Â", "Ê", "Ô", "Ơ", "Ư", "Đ"]) {
      expect(findRow(letter, normalizeAlphabetText)).toBeUndefined();
      // …which is exactly what the old comparison got wrong:
      expect(findRow(letter, normalizeText)).toBeDefined();
    }
  });

  it("still recognises a letter that really is in the catalog", () => {
    expect(findRow("A", normalizeAlphabetText)).toBe("A");
    expect(findRow("a", normalizeAlphabetText)).toBe("A");
  });

  it("treats both Unicode forms of a letter as the same", () => {
    const catalog = ["Ă"];
    const find = (t: string) =>
      catalog.find((r) => normalizeAlphabetText(r) === normalizeAlphabetText(t));
    expect(find("Ă".normalize("NFC"))).toBe("Ă");
    expect(find("Ă".normalize("NFD"))).toBe("Ă");
  });

  it("word signs keep the diacritic-insensitive match", () => {
    const words = ["tôm", "rang muối"];
    const find = (t: string) => words.find((r) => normalizeText(r) === normalizeText(t));
    expect(find("tom")).toBe("tôm");
    expect(find("rang muoi")).toBe("rang muối");
  });
});
