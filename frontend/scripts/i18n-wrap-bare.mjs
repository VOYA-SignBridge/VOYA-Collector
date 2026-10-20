#!/usr/bin/env node
/**
 * Bọc `t()` quanh đúng những chuỗi mà `i18n-coverage.mjs` báo là còn trần.
 *
 * Vì sao KHÔNG dùng codemod chạy mù
 * ----------------------------------
 * Lần trước một codemod sửa nhiều dòng đã phá 8 tệp cùng lúc, và lỗi hiện ra ở
 * dòng khác chỗ nó gây ra. Nên công cụ này bị bó lại cho nhỏ nhất có thể:
 *
 *   - Chỉ đụng tới **cặp (tệp, chuỗi)** do chính bộ đo liệt kê ra. Không tự đi
 *     tìm thêm.
 *   - Chỉ sửa **trong một dòng**, không bao giờ vắt qua dòng.
 *   - Bỏ qua nếu chuỗi đã nằm trong `t(` / `tr(` — nếu không sẽ ra `t(t("…"))`.
 *   - Không tự thêm `useI18n()`. Tệp nào chưa có bộ dịch trong tầm thì **báo ra
 *     rồi bỏ qua**, để người sửa tay. Một cái import thêm bừa vào tệp không
 *     phải component là cách nhanh nhất để có một lỗi lúc chạy thay vì lúc dịch.
 *
 * Chạy xong PHẢI `npm run typecheck`: chỗ `t` không có trong tầm sẽ đỏ ở đó.
 *
 *   node scripts/i18n-wrap-bare.mjs --dry    # xem trước, không ghi
 *   node scripts/i18n-wrap-bare.mjs
 */
import { readFileSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(fileURLToPath(new URL(".", import.meta.url)), "..");
const DRY = process.argv.includes("--dry");

const report = JSON.parse(
  execFileSync("node", [join(ROOT, "scripts", "i18n-coverage.mjs"), "--json"], {
    encoding: "utf-8",
    maxBuffer: 32 * 1024 * 1024,
  }),
);

/** Bộ dịch có sẵn trong tệp: `t` (trong component) hay `tr` (ngoài React)? */
function translatorFor(src) {
  if (/\bconst\s*\{[^}]*\bt\b[^}]*\}\s*=\s*useI18n\(\)/.test(src)) return "t";
  if (/\bimport\s*\{[^}]*\btr\b[^}]*\}\s*from\s*["'][^"']*i18n/.test(src)) return "tr";
  return null;
}

const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/**
 * Vị trí `at` có nằm trong chú thích không?
 *
 * Quét thô từ đầu tệp: đủ cho việc này vì ta chỉ cần biết ĐANG ở trong chú
 * thích hay không, không cần phân tích cú pháp. Chuỗi có chứa `//` (đường dẫn,
 * URL) là chỗ dễ nhầm nhất, nên phải theo dõi cả dấu nháy đang mở.
 */
function inComment(src, at) {
  let line = false, block = false, quote = "";
  for (let i = 0; i < at; i++) {
    const c = src[i], d = src[i + 1];
    if (line) { if (c === "\n") line = false; continue; }
    if (block) { if (c === "*" && d === "/") { block = false; i++; } continue; }
    if (quote) {
      if (c === "\\") i++;
      else if (c === quote) quote = "";
      continue;
    }
    if (c === '"' || c === "'" || c === "`") quote = c;
    else if (c === "/" && d === "/") { line = true; i++; }
    else if (c === "/" && d === "*") { block = true; i++; }
  }
  return line || block;
}

let changed = 0;
const skipped = [];

for (const { file, bare } of report.perFile) {
  const path = join(ROOT, file);
  let src = readFileSync(path, "utf-8");
  const fn = translatorFor(src);
  if (!fn) {
    skipped.push({ file, bare, why: "không có t()/tr() trong tầm" });
    continue;
  }

  let hits = 0;
  const held = [];
  for (const text of bare) {
    // Chỉ literal nguyên vẹn, và chỉ khi ngay trước nó KHÔNG phải `t(`/`tr(`.
    const re = new RegExp(`(?<![\\w.])(?<!\\bt\\(\\s*)(?<!\\btr\\(\\s*)(["'])${esc(text)}\\1`, "g");
    const next = src.replace(re, (m, _q, at) => {
      const before = src.slice(Math.max(0, at - 24), at);
      const after = src.slice(at + m.length, at + m.length + 2);

      // Trong chú thích thì để yên. Một chú thích giải thích rằng ô trống hiện
      // ra chữ "chưa ghi" mà bị sửa thành `t("chưa ghi")` thì vẫn biên dịch
      // được — nó chỉ lặng lẽ nói sai về chính đoạn mã bên dưới. Không có bộ
      // kiểm nào bắt được loại hỏng đó, nên phải chặn từ đây.
      if (inComment(src, at)) {
        held.push(`${text}  ← nằm trong chú thích`);
        return m;
      }

      // So sánh: `x === "Đang chờ"`, `case "Đang chờ":`, `includes("…")`.
      // Bọc `t()` ở đây KHÔNG làm hỏng lúc dịch — nó làm hỏng lúc CHẠY, và chỉ
      // ở tiếng Anh: phép so sánh không bao giờ đúng nữa, nhánh đó chết lặng.
      // Đúng cách sửa là tách hằng ra khỏi chữ hiển thị, và đó là việc của
      // người, không phải của công cụ này.
      if (/(===?|!==?)\s*$/.test(before) || /\bcase\s*$/.test(before)) {
        held.push(`${text}  ← đem đi so sánh`);
        return m;
      }
      // Khoá của object: `"Đang chờ": …` — dịch khoá là đổi chính cái khoá.
      //
      // Cái bẫy: dấu `:` của toán tử ba ngôi trông y hệt dấu `:` của khoá.
      // `{running ? "Dừng nhận diện" : t("Bắt đầu")}` mà bị coi là khoá thì
      // công cụ sẽ bỏ qua ĐÚNG nhóm chuỗi nó sinh ra để bắt. Phân định bằng
      // dấu `?` đứng trước trên CÙNG dòng — có `?` thì đó là ba ngôi.
      const lineStart = src.lastIndexOf("\n", at) + 1;
      const openedTernary = /\?[^.?]/.test(src.slice(lineStart, at));
      if (/^\s*:/.test(after) && !openedTernary) {
        held.push(`${text}  ← khoá object`);
        return m;
      }
      hits++;
      return `${fn}(${m})`;
    });
    src = next;
  }
  if (held.length) skipped.push({ file, bare: held, why: "giữ nguyên có chủ ý" });
  if (!hits) {
    skipped.push({ file, bare, why: "không khớp literal nào (chuỗi bị cắt?)" });
    continue;
  }
  changed += hits;
  if (!DRY) writeFileSync(path, src, "utf-8");
  console.log(`  ${hits.toString().padStart(3)}  ${file}`);
}

console.log(`\n  Đã bọc ${changed} chuỗi${DRY ? " (DRY — chưa ghi)" : ""}.`);
if (skipped.length) {
  console.log(`\n  BỎ QUA — sửa tay:`);
  for (const s of skipped) {
    console.log(`    ${s.file}  (${s.why})`);
    for (const b of s.bare) console.log(`        ${b}`);
  }
}
