#!/usr/bin/env node
/**
 * Đổi chuỗi mẫu có chữ tiếng Việt thành một khoá TRỌN CÂU kèm chỗ trống:
 *
 *     `Đã chặn ${ip}`            →  t("Đã chặn {ip}", { ip })
 *     `Xóa ${sel.size} mục`      →  t("Xóa {size} mục", { size: sel.size })
 *
 * Vì sao phải là trọn câu
 * ------------------------
 * Cắt thành `t("Đã chặn ") + ip` thì bản dịch bị khoá vào trật tự từ của tiếng
 * Việt. Tiếng Anh có thể muốn "{ip} has been blocked" — đảo chỗ. Một khoá trọn
 * câu để người dịch tự quyết định chỗ trống rơi vào đâu. Đây cũng chính là lý
 * do `<Trans>` tồn tại; xem docs/I18N.md §4.
 *
 * Đặt tên chỗ trống
 * ------------------
 * Lấy từ chính biểu thức: `ip` → `{ip}`, `sel.size` → `{size}`,
 * `c.sample_count ?? 0` → `{sample_count}`. Biểu thức không rút được tên thì
 * lùi về `{p1}`, `{p2}`… Tên trùng nhau trong cùng một câu thì thêm số.
 *
 * Ranh giới — công cụ này CỐ Ý bỏ qua:
 *   - chuỗi mẫu nằm trong chú thích;
 *   - chuỗi mẫu đã nằm trong `t(...)`/`tr(...)`;
 *   - tệp không có `t`/`tr` trong tầm;
 *   - biểu thức có chứa `${` lồng nhau hoặc dấu nháy — quá dễ cắt sai.
 *
 * Chạy xong PHẢI `npm run typecheck`.
 *
 *   node scripts/i18n-wrap-template.mjs --dry
 */
import { readFileSync, writeFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(fileURLToPath(new URL(".", import.meta.url)), "..");
const SRC = join(ROOT, "src");
const DRY = process.argv.includes("--dry");

const VIETNAMESE =
  /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;
const SKIP = /(__tests__|\.test\.|\.spec\.|[/\\]i18n[/\\]|[/\\]scripts[/\\])/;

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.tsx?$/.test(full) && !SKIP.test(full)) out.push(full);
  }
  return out;
}

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

/** Tên chỗ trống rút từ biểu thức, hoặc null nếu không rút được cái nào gọn. */
function nameOf(expr) {
  const e = expr.trim();
  // `x`, `a.b.c`, `a?.b`, và vế trái của `??` / `||`
  const head = e.split(/\?\?|\|\|/)[0].trim();
  const m = /^[A-Za-z_$][\w$]*(?:\??\.[A-Za-z_$][\w$]*)*$/.exec(head);
  if (!m) return null;
  const last = head.split(/\??\./).pop();
  return /^[A-Za-z_$][\w$]*$/.test(last) ? last : null;
}

function translatorFor(src) {
  if (/\bconst\s*\{[^}]*\bt\b[^}]*\}\s*=\s*useI18n\(\)/.test(src)) return "t";
  if (/\bimport\s*\{[^}]*\btr\b[^}]*\}\s*from\s*["'][^"']*i18n/.test(src)) return "tr";
  return null;
}

let total = 0;
const skipped = [];

for (const file of walk(SRC)) {
  let src = readFileSync(file, "utf-8");
  if (!/`[^`\n]*`/.test(src)) continue;
  const fn = translatorFor(src);

  let hits = 0;
  const held = [];
  const out = src.replace(/`([^`\\\n]*)`/g, (whole, body, at) => {
    const text = body.replace(/\$\{[^}]*\}/g, "");
    if (!VIETNAMESE.test(text)) return whole;
    if (inComment(src, at)) return whole;
    if (!fn) { held.push(`${body}  ← không có t()/tr() trong tầm`); return whole; }

    // Đã nằm ngay trong `t(` / `tr(` thì thôi.
    if (/\b(?:t|tr)\(\s*$/.test(src.slice(Math.max(0, at - 6), at))) return whole;
    // `${` lồng hoặc dấu nháy trong biểu thức: cắt tay an toàn hơn.
    if (/["']/.test(body.replace(/[^$]*/, "")) && /\$\{[^}]*["']/.test(body)) {
      held.push(`${body}  ← biểu thức có dấu nháy`);
      return whole;
    }

    const used = new Map();
    const vars = [];
    let n = 0;
    const key = body.replace(/\$\{([^}]*)\}/g, (_, expr) => {
      let name = nameOf(expr) || `p${++n}`;
      if (used.has(name)) {
        const k = used.get(name) + 1;
        used.set(name, k);
        name = `${name}${k}`;
      } else used.set(name, 1);
      vars.push(name === expr.trim() ? name : `${name}: ${expr.trim()}`);
      return `{${name}}`;
    });

    hits++;
    const esc = key.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
    return vars.length ? `${fn}("${esc}", { ${vars.join(", ")} })` : `${fn}("${esc}")`;
  });

  if (held.length) skipped.push({ file: relative(ROOT, file), held });
  if (!hits) continue;
  total += hits;
  if (!DRY) writeFileSync(file, out, "utf-8");
  console.log(`  ${String(hits).padStart(3)}  ${relative(ROOT, file)}`);
}

console.log(`\n  Đã đổi ${total} chuỗi mẫu${DRY ? " (DRY — chưa ghi)" : ""}.`);
if (skipped.length) {
  console.log("\n  BỎ QUA — sửa tay:");
  for (const s of skipped) {
    console.log(`    ${s.file}`);
    for (const h of s.held) console.log(`        ${h}`);
  }
}
