/**
 * Canh cho độ phủ i18n KHÔNG tụt lại.
 *
 * Vì sao cần một bài test cho việc này
 * -------------------------------------
 * Phiên trước i18n được báo cáo là "đã xong" trong khi `t()` chỉ được gọi ở
 * đúng MỘT tệp — độ phủ thật là 3,5%. Không ai phát hiện ra vì không có con số
 * nào để đối chiếu, và một câu tiếng Việt hiện ra ở chế độ tiếng Anh trông y
 * hệt một câu chưa kịp dịch.
 *
 * Công cụ đo đã có (`scripts/i18n-coverage.mjs`), nhưng một công cụ phải nhớ
 * chạy thì cũng là một công cụ sẽ có ngày không ai chạy. Bài test này gọi
 * thẳng nó và bắt lỗi ngay trong bộ test — chỗ mà mọi người đã nhìn.
 *
 * Ngưỡng đặt ở 95% chứ không phải 100%: mục tiêu là chặn một cú TỤT, không
 * phải khoá cứng con số hôm nay và biến mỗi lần thêm một dòng chữ mới thành
 * một lần build đỏ.
 */

import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = join(__dirname, "..", "..", "..");

function measure(): { pct: number; bare: number; missing: number; orphan: number } {
  const out = execFileSync(
    process.execPath,
    [join(ROOT, "scripts", "i18n-coverage.mjs")],
    { encoding: "utf-8" },
  );
  const num = (re: RegExp) => Number(out.match(re)?.[1] ?? "-1");
  return {
    pct: num(/Độ phủ\s+([\d.]+)%/),
    bare: num(/Chuỗi còn trần\s+(\d+)/),
    missing: num(/Khoá thiếu bản dịch EN\s+(\d+)/),
    orphan: num(/Khoá EN không ai dùng\s+(\d+)/),
  };
}

describe("độ phủ i18n", () => {
  const m = measure();

  it("công cụ đo chạy được và trả về số đọc hiểu được", () => {
    // `-1` nghĩa là không tách được con số ra khỏi đầu ra — nếu định dạng báo
    // cáo đổi, bài test phải ĐỎ chứ không được lặng lẽ so sánh với rác.
    expect(m.pct).toBeGreaterThanOrEqual(0);
    expect(m.bare).toBeGreaterThanOrEqual(0);
  });

  it("giữ độ phủ ≥ 95%", () => {
    expect(m.pct).toBeGreaterThanOrEqual(95);
  });

  it("không còn khoá nào thiếu bản dịch tiếng Anh", () => {
    // Thiếu bản dịch không làm hỏng ứng dụng — nó hiển thị tiếng Việt, và đó
    // đúng là hướng hỏng ta chọn. Nhưng chọn tiếng Anh mà thấy tiếng Việt là
    // đúng lời phàn nàn đã dẫn tới cả đợt làm này, nên nó được canh ở đây.
    expect(m.missing).toBe(0);
  });

  it("không có bản dịch mồ côi", () => {
    // Khoá mồ côi vô hại lúc chạy nhưng làm bảng số nhiễu, và nhiễu là thứ
    // khiến người ta ngừng đọc bảng số.
    expect(m.orphan).toBe(0);
  });
});
