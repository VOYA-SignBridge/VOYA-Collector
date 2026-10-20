import { describe, expect, it } from "vitest";
import { sotConclusion } from "./sotStatus";

const PUBLISHED = { available: true, published: true, version: "Ver5", trusted: true, signed_by: "desktop-admin" };

describe("sotConclusion — sáu trạng thái, không gộp (SOT-02)", () => {
  it("đang tải hoặc đang kiểm tra → checking", () => {
    expect(sotConclusion({ remote: null, remoteLoading: true, verify: null, verifying: false }).kind).toBe("checking");
    expect(sotConclusion({ remote: PUBLISHED, remoteLoading: false, verify: null, verifying: true }).kind).toBe("checking");
  });

  it("kho không truy cập được ≠ kho chưa có bản", () => {
    expect(sotConclusion({ remote: { available: false }, remoteLoading: false, verify: null, verifying: false }).kind).toBe("unreachable");
    expect(sotConclusion({ remote: { available: true, published: false }, remoteLoading: false, verify: null, verifying: false }).kind).toBe("nothing_published");
  });

  it("chữ ký lạ → untrusted_source, kể cả khi verify nói ok", () => {
    const c = sotConclusion({ remote: { ...PUBLISHED, trusted: false }, remoteLoading: false, verify: { ok: true }, verifying: false });
    expect(c.kind).toBe("untrusted_source");
    expect(c.tone).toBe("bad");
    expect(c.nextStep).toMatch(/Đừng đồng bộ/);
  });

  it("chưa kiểm tra ≠ kiểm tra thất bại ≠ kiểm tra đạt", () => {
    expect(sotConclusion({ remote: PUBLISHED, remoteLoading: false, verify: null, verifying: false }).kind).toBe("unchecked");
    expect(sotConclusion({ remote: PUBLISHED, remoteLoading: false, verify: { ok: false, error: "sha256 lệch" }, verifying: false }).kind).toBe("verify_failed");
    expect(sotConclusion({ remote: PUBLISHED, remoteLoading: false, verify: { ok: true }, verifying: false }).kind).toBe("verified");
  });

  it("mỗi kết luận đều có câu tiếng Việt, và chỉ trạng thái ổn mới không có việc tiếp theo", () => {
    const ok = sotConclusion({ remote: PUBLISHED, remoteLoading: false, verify: { ok: true }, verifying: false });
    expect(ok.nextStep).toBeNull();
    const warn = sotConclusion({ remote: PUBLISHED, remoteLoading: false, verify: null, verifying: false });
    expect(warn.nextStep).toBeTruthy();
    expect(warn.headline.length).toBeGreaterThan(10);
  });
});
