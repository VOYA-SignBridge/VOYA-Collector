#!/usr/bin/env node
/**
 * Cổng i18n: biến một BÁO CÁO thành một điều kiện đạt/trượt.
 *
 * Vì sao cần một tệp riêng thay vì vài dòng trong workflow
 * --------------------------------------------------------
 * `i18n-coverage.mjs` luôn thoát 0. Đó là lựa chọn đúng cho nó — nó là công cụ
 * để NGƯỜI đọc, và một công cụ báo cáo mà thoát khác 0 thì phiền. Nhưng nghĩa
 * là không có gì ngăn độ phủ trôi ngược.
 *
 * Và độ phủ ĐÃ trôi ngược hai lần mà không ai biết: hai lần kho này ghi nhận
 * "i18n đã xong 100%", lần đầu còn sót 36 chuỗi, lần sau 122. Cả hai lần con
 * số ấy là một câu người tự khẳng định sau khi nhìn qua, không phải một phép
 * đo chạy lại được.
 *
 * Logic gác để ở đây chứ không nhúng vào YAML vì hai lý do: chạy được ở máy
 * trước khi đẩy, và không phải escape ba tầng shell/YAML/JS — lớp escape ấy
 * tự nó đã là một nguồn lỗi.
 *
 * Ngưỡng là KHÔNG, không phải phần trăm. Đo 11/09/2026: 2188 chuỗi đã qua
 * `t()`, 0 chuỗi trần, 0 khoá thiếu, 0 khoá rác. Khi đã sạch thì ngưỡng đúng
 * duy nhất là giữ sạch; một ngưỡng "95%" chỉ hợp thức hoá phần trôi ngược.
 *
 * Và phần trăm ở đây còn gác kém hơn vẻ ngoài của nó: với 2188 chuỗi đã dịch,
 * một chuỗi trần mới làm độ phủ thành 99,954% và bảng in ra "100.0%". Con số
 * tròn ấy đúng về mặt làm tròn và sai về mặt điều nó khiến người đọc tin. Đếm
 * tuyệt đối không có vùng mù đó.
 *
 * Dùng:
 *   node scripts/i18n-gate.mjs              # gác
 *   node scripts/i18n-gate.mjs --self-test  # tự chứng minh là gác thật
 */
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const srcRoot = path.join(here, "..", "src");

/**
 * Tự chứng minh: gieo một chuỗi tiếng Việt còn trần, chạy lại chính cổng này,
 * và đòi nó phải ĐỎ.
 *
 * Đây không phải nghi thức. Bản đầu của cổng này báo ĐẠT khi có chuỗi trần
 * thật — nó đọc `perFile` như một map trong khi công cụ trả về một MẢNG, nên
 * tổng luôn bằng 0. Mã trông đúng, chạy không lỗi, in ra một câu khẳng định
 * tự tin. Chỉ có việc tiêm một lỗi vào mới phân biệt được "không có lỗi" với
 * "không nhìn thấy lỗi nào".
 */
function selfTest() {
  const probe = path.join(srcRoot, "__i18n_gate_selftest.tsx");
  if (fs.existsSync(probe)) {
    console.error("Tep thu da ton tai, khong ghi de: " + probe);
    process.exit(2);
  }

  // Chuỗi phải là tiếng Việt CÓ DẤU thì bộ quét mới tính là chữ người đọc —
  // đó chính là bộ lọc "chữ người đọc hay chuỗi máy đọc" của i18n-coverage.
  const lines = [
    "export function I18nGateSelfTest() {",
    "  return <div>Chuỗi này cố ý để trần để kiểm cổng</div>;",
    "}",
    "",
  ];
  fs.writeFileSync(probe, lines.join("\n"), "utf8");

  let code = 0;
  try {
    execFileSync(process.execPath, [fileURLToPath(import.meta.url)], { stdio: "pipe" });
  } catch (err) {
    code = err.status ?? 1;
  } finally {
    fs.unlinkSync(probe);
  }

  if (code === 1) {
    console.log("Self-test DAT: cong bat duoc chuoi tran da gieo (thoat 1).");
    process.exit(0);
  }
  console.error("Self-test TRUOT: da gieo mot chuoi tran nhung cong thoat " + code + ", dang le phai la 1.");
  console.error("Nghia la cong nay KHONG gac gi ca — dung tin bang so cua no.");
  process.exit(2);
}

if (process.argv.includes("--self-test")) selfTest();

let report;
try {
  const raw = execFileSync(
    process.execPath,
    [path.join(here, "i18n-coverage.mjs"), "--json"],
    { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 },
  );
  report = JSON.parse(raw);
} catch (err) {
  console.error("Khong chay duoc i18n-coverage.mjs --json:");
  console.error(err.stderr?.toString() || err.message);
  process.exit(2);
}

// `perFile` là một MẢNG `{file, bare: [...]}`, không phải map tệp -> số.
const perFile = Array.isArray(report.perFile) ? report.perFile : [];
const bareByFile = perFile
  .map((entry) => [entry.file, Array.isArray(entry.bare) ? entry.bare.length : 0])
  .filter(([, n]) => n > 0)
  .sort((a, b) => b[1] - a[1]);

const bare = bareByFile.reduce((sum, [, n]) => sum + n, 0);
const missing = report.missing || [];
const orphan = report.orphan || [];

const problems = [];
if (bare) problems.push(bare + " chuoi tieng Viet con tran (chua qua t()), o " + bareByFile.length + " tep");
if (missing.length) problems.push(missing.length + " khoa da qua t() nhung thieu ban dich EN");
if (orphan.length) problems.push(orphan.length + " khoa trong en.ts khong con ai dung");

if (!problems.length) {
  console.log("Cong i18n: DAT — 0 chuoi tran, 0 khoa thieu, 0 khoa rac.");
  process.exit(0);
}

console.error("Cong i18n: TRUOT");
for (const p of problems) console.error("  - " + p);

if (bareByFile.length) {
  console.error("");
  console.error("Tep con nhieu chuoi tran nhat:");
  for (const [file, n] of bareByFile.slice(0, 10)) console.error("  " + String(n).padStart(4) + "  " + file);
}
if (missing.length) console.error("\nKhoa thieu ban dich (toi da 10): " + missing.slice(0, 10).join(" | "));
if (orphan.length) console.error("\nKhoa khong ai dung (toi da 10): " + orphan.slice(0, 10).join(" | "));

console.error("\nXem day du: node scripts/i18n-coverage.mjs --list");
process.exit(1);
