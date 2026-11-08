/**
 * Ghi kết quả trả về của từng ca Vitest cho báo cáo kiểm thử. Chỉ nạp khi có
 * `KT_KET_QUA` (xem vitest.setup.ts); chạy test bình thường không đi qua tệp này.
 *
 * Mọi matcher của `expect` đi qua `chai.Assertion.prototype.assert`, nên một chỗ bọc
 * thấy được giá trị mong đợi và giá trị thực tế của từng phép so.
 */
import { appendFileSync } from "node:fs";

import { afterEach, chai, expect } from "vitest";

type SoSanh = { kiem: string; mong_doi: string; thuc_te: string };

const TOI_DA_SO_SANH = 30;
const TOI_DA_KY_TU = 300;

let soSanh: SoSanh[] = [];

function chuoi(v: unknown): string {
  try {
    const s = v instanceof Element ? v.outerHTML : typeof v === "string" ? v : (JSON.stringify(v) ?? String(v));
    return s.length > TOI_DA_KY_TU ? `${s.slice(0, TOI_DA_KY_TU)}…` : s;
  } catch {
    return String(v);
  }
}

const Assertion = chai.Assertion as unknown as { prototype: { assert: (...a: unknown[]) => unknown } };
const goc = Assertion.prototype.assert;
Assertion.prototype.assert = function (this: unknown, ...a: unknown[]) {
  if (soSanh.length < TOI_DA_SO_SANH) {
    const kiem = typeof a[1] === "function" ? (a[1] as () => string)() : String(a[1] ?? "");
    soSanh.push({ kiem: kiem.replace(/#\{[^}]*\}/g, "…"), mong_doi: chuoi(a[3]), thuc_te: chuoi(a[4]) });
  }
  return goc.apply(this, a);
};

afterEach(() => {
  const trang = expect.getState();
  appendFileSync(process.env.KT_KET_QUA as string, `${JSON.stringify({
    tep: trang.testPath ?? "",
    ten: trang.currentTestName ?? "",
    so_phep_so: trang.assertionCalls ?? 0,
    so_sanh: soSanh,
  })}\n`);
  soSanh = [];
});
