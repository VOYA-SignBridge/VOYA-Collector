#!/usr/bin/env node
/**
 * Lượt hai: bọc giá trị chuỗi trong OBJECT LITERAL nằm trong thân component.
 *
 * Lượt một (`i18n-wrap.mjs`) chỉ đụng chữ giữa hai thẻ JSX và một danh sách
 * trắng thuộc tính. Phần lớn chữ còn lại nằm ở dạng khác:
 *
 *     const TABS = [{ key: "audit", label: "Nhật ký kiểm toán" }];
 *
 * Ranh giới của lượt này, và nó hẹp có lý do
 * -------------------------------------------
 * Chỉ bọc khi object nằm **trong thân một component** — tức nơi `t` có trong
 * phạm vi. Object ở MỨC MÔ-ĐUN thì không: gọi hook ngoài component là vi phạm
 * luật hook của React, và không có cách nào bọc chúng tại chỗ.
 *
 * Với những bảng ở mức mô-đun (`STATUS_LABEL`, `CATEGORY_LABEL`…), cách đúng là
 * **để nguyên tiếng Việt làm khoá và dịch tại NƠI DÙNG**: `t(STATUS_LABEL[x])`.
 * Khoá vốn đã là câu tiếng Việt nên phép này không cần thêm gì. Việc đó phải
 * làm tay vì nó thay đổi nơi gọi, không thay đổi nơi khai báo.
 *
 * Chỉ bọc khoá nằm trong danh sách trắng dưới đây. `key`, `value`, `id`,
 * `href`, `className`, `type`, `status`, `kind` là định danh máy đọc — dịch
 * chúng là làm hỏng logic, không phải làm hỏng giao diện, và kiểu hỏng đó im
 * lặng hơn nhiều.
 */

import { readFileSync, writeFileSync } from "node:fs";

const VIETNAMESE =
  /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;

/** Khoá mang chữ người dùng đọc. */
const TEXT_KEYS = new Set([
  "label", "title", "name", "description", "desc", "text", "hint", "message",
  "subtitle", "heading", "caption", "tooltip", "placeholder", "summary",
  "empty", "emptyText", "note", "help", "legend",
]);

const dry = process.argv.includes("--dry");
const files = process.argv.slice(2).filter((a) => !a.startsWith("--"));

function matchClose(s, i, open, close) {
  let d = 0;
  for (; i < s.length; i += 1) {
    if (s[i] === open) d += 1;
    else if (s[i] === close) {
      d -= 1;
      if (d === 0) return i;
    }
  }
  return -1;
}

/** Khoảng [đầu, cuối) của mọi thân component có `t` trong phạm vi. */
function componentBodies(src) {
  const spans = [];
  const rx = /(?:^|\n)\s*(?:export\s+)?(?:default\s+)?(?:function\s+([A-Z]\w*)|const\s+([A-Z]\w*)\s*(?::[^=\n]*)?=)/g;
  let m;
  while ((m = rx.exec(src))) {
    const brace = src.indexOf("{", m.index + m[0].length);
    if (brace < 0) continue;
    const end = matchClose(src, brace, "{", "}");
    if (end < 0) continue;
    const body = src.slice(brace, end);
    if (/const\s*\{[^}]*\bt\b[^}]*\}\s*=\s*useI18n/.test(body)) spans.push([brace, end]);
  }
  return spans;
}

const inSpan = (spans, i) => spans.some(([a, b]) => i > a && i < b);

let total = 0;

for (const file of files) {
  const original = readFileSync(file, "utf-8");
  let src = original;
  const spans = componentBodies(src);
  if (!spans.length) continue;

  const edits = [];
  for (const m of src.matchAll(/\b([\w]+)\s*:\s*(["'])([^"'\n]{2,})\2/g)) {
    if (!TEXT_KEYS.has(m[1]) || !VIETNAMESE.test(m[3])) continue;
    if (!inSpan(spans, m.index)) continue;
    edits.push({
      start: m.index,
      end: m.index + m[0].length,
      text: `${m[1]}: t(${JSON.stringify(m[3])})`,
    });
  }
  if (!edits.length) continue;

  edits.sort((a, b) => b.start - a.start);
  for (const e of edits) src = src.slice(0, e.start) + e.text + src.slice(e.end);

  if (dry) {
    console.log(`${file}: ${edits.length}`);
  } else {
    writeFileSync(file, src, "utf-8");
    total += edits.length;
    console.log(`${file}: bọc ${edits.length}`);
  }
}

if (!dry) console.log(`\nTổng: ${total} chuỗi`);
