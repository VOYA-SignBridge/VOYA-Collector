import { describe, expect, it } from "vitest";
import { catalogCSV } from "./catalogExport";

describe("catalog CSV", () => {
  it("keeps identity and all vocabulary metadata, quoting every cell", () => {
    const csv = catalogCSV([{
      class_uid: "uid-1", class_idx: 8, label_original: 'Xin, "chào"\nĐ', slug: "xin-chao",
      language: "vn", dialect: "common", region: "south", recognition_profile: "south",
    }]);
    expect(csv).toContain('"class_uid","class_idx"');
    expect(csv).toContain('"uid-1","8","Xin, ""chào""\nĐ"');
    expect(csv).toContain('"recognition_profile"');
    expect(csv).toContain('"south"');
  });
  it("exports an empty catalog as a header, not stale rows", () => {
    expect(catalogCSV([]).split("\r\n")).toHaveLength(1);
  });
});
