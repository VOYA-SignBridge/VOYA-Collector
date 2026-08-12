#!/usr/bin/env node
/**
 * Bọc chuỗi tiếng Việt hiển thị được vào `t(...)`.
 *
 * Đây là một phép biến đổi MÁY MÓC, và nó cố tình làm ít hơn khả năng:
 *
 *   * Chỉ đụng `.tsx` (tệp có JSX). `.ts` chứa hằng số và bảng nhãn ở mức
 *     mô-đun, nơi không gọi hook được — những chỗ đó dịch tại NƠI DÙNG
 *     (`t(STATUS_LABEL[x])`), vì khoá vốn đã là câu tiếng Việt.
 *   * Chỉ hai vị trí: chữ giữa hai thẻ JSX, và một danh sách trắng thuộc tính.
 *     `className`, `to`, `href`, `id`, `key`, `type` không bao giờ bị đụng.
 *   * Chỉ chuỗi CÓ DẤU tiếng Việt. "OK", "CSV", "GPU" giữ nguyên.
 *
 * Lưới an toàn là TypeScript, không phải sự cẩn thận của script này. Bọc một
 * chuỗi ở nơi `t` không có trong phạm vi (component phụ trong cùng tệp, hàm
 * trợ giúp ngoài component) sẽ thành lỗi biên dịch — to, ồn, và sửa được. Kiểu
 * hỏng đáng sợ là hỏng IM LẶNG, và cách này không có kiểu đó.
 *
 * CẢNH BÁO ĐÃ TRẢ GIÁ (2026-08-10): lượt cho phép XUỐNG DÒNG đã phá 8 tệp.
 * ------------------------------------------------------------------------
 * `>` và `<` trong một tệp `.tsx` KHÔNG chỉ là thẻ JSX. Chúng còn là:
 *
 *   * dấu đóng generic — `useRef<HTMLInputElement>(null)`
 *   * toán tử so sánh — `a > b`
 *   * mũi tên hàm — `() =>`
 *
 * Khi khớp đa dòng, script nuốt từ `>` của một generic sang `<` nằm trong một
 * chú thích cách đó ba dòng, gộp tất cả thành một chuỗi, và biến cả khối mã
 * thành đối số của `t()`. Kết quả: 650 lỗi biên dịch, trong đó nguy hiểm nhất
 * là những khai báo `const [x, setX] = useState(...)` bị chôn vào sau `//`
 * trên cùng một dòng — biến mất khỏi chương trình mà cú pháp vẫn hợp lệ.
 *
 * Hai luật rút ra:
 *
 *   1. **Chạy `npx tsc -b --noEmit` NGAY sau mỗi lượt**, trước khi chạy lượt
 *      kế. Gộp nhiều lượt rồi mới kiểm thì không biết lượt nào gây ra gì.
 *   2. **Không bao giờ đụng `src/i18n/`.** Tệp định nghĩa `t()` đầy generic;
 *      script làm hỏng chính cái nó đang dùng, và mọi tệp khác đổ theo.
 *
 * Sửa đúng cho vấn đề này là một bộ phân tích cú pháp JSX thật
 * (`@babel/parser`), không phải một biểu thức chính quy khôn hơn.
 *
 * Dùng:
 *   node scripts/i18n-wrap.mjs src/pages/AccountPage.tsx ...
 *   node scripts/i18n-wrap.mjs --dry src/pages/AccountPage.tsx
 */

import { readFileSync, writeFileSync } from "node:fs";

const VIETNAMESE =
  /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;

const TEXT_ATTRS = new Set([
  "title", "placeholder", "label", "subtitle", "description", "alt",
  "aria-label", "hint", "emptyText", "confirmLabel",
]);

const dry = process.argv.includes("--dry");
const files = process.argv
  .slice(2)
  .filter((a) => !a.startsWith("--"))
  // Không bao giờ tự sửa mô-đun định nghĩa `t()`. Xem cảnh báo ở đầu tệp.
  .filter((a) => !/[/\]i18n[/\]/.test(a));

/** Vùng chú thích, để không bọc chữ trong đó. */
function commentRanges(src) {
  const ranges = [];
  for (const m of src.matchAll(/\/\*[\s\S]*?\*\//g)) ranges.push([m.index, m.index + m[0].length]);
  for (const m of src.matchAll(/(^|[^:"'])\/\/[^\n]*/gm)) ranges.push([m.index, m.index + m[0].length]);
  return ranges;
}

function inComment(ranges, i) {
  return ranges.some(([a, b]) => i >= a && i < b);
}

let touched = 0;

for (const file of files) {
  const original = readFileSync(file, "utf-8");
  let src = original;
  const ranges = commentRanges(src);
  const edits = [];

  // 1. Chữ giữa hai thẻ JSX.  >Xin chào<  →  >{t("Xin chào")}<
  //    `[^<>{}\n]` loại luôn trường hợp đã có biểu thức `{...}` bên trong.
  // Cho phep XUONG DONG: JSX qua prettier hay ngat mot cau thanh nhieu dong,
  // nen ban chi-mot-dong bo sot phan lon van xuoi dai.
  // MOT luong tu duy nhat, khong long nhau. Ban truoc viet
  //   />([^<>{}]*[^<>{}\s][^<>{}]*)</
  // de doi hoi 'co it nhat mot ky tu khong phai khoang trang'. Ba lop ky tu
  // chong nhau nhu vay cho ra backtracking cap so nhan: tren mot tep JSX vai
  // tram dong no chay vo han. Phep kiem do lam trong JS ben duoi, noi no ton
  // O(n) thay vi O(2^n).
  for (const m of src.matchAll(/>([^<>{}]*)</g)) {
    if (inComment(ranges, m.index)) continue;
    const raw = m[1];
    // Gom khoang trang thanh mot dau cach: JSX dung nhieu dong nhu MOT cau,
    // nen khoa dich phai la cau do chu khong phai cach no duoc ngat.
    const text = raw.trim().replace(/\s+/g, " ");
    if (!text || !VIETNAMESE.test(text)) continue;
    const lead = raw.slice(0, raw.length - raw.trimStart().length);
    const tail = raw.slice(raw.trimEnd().length);
    edits.push({
      start: m.index + 1,
      end: m.index + 1 + raw.length,
      text: `${lead}{t(${JSON.stringify(text)})}${tail}`,
    });
  }

  // 2. Thuộc tính trong danh sách trắng.  placeholder="Nhập tên"
  for (const m of src.matchAll(/\b([\w-]+)=(["'])([^"'\n]+)\2/g)) {
    if (inComment(ranges, m.index)) continue;
    if (!TEXT_ATTRS.has(m[1]) || !VIETNAMESE.test(m[3])) continue;
    edits.push({
      start: m.index,
      end: m.index + m[0].length,
      text: `${m[1]}={t(${JSON.stringify(m[3])})}`,
    });
  }

  if (!edits.length) continue;

  // Áp từ cuối lên đầu để chỉ số không trôi.
  edits.sort((a, b) => b.start - a.start);
  for (const e of edits) src = src.slice(0, e.start) + e.text + src.slice(e.end);

  // Thêm import + hook nếu chưa có. Chỉ chèn vào hàm export default — component
  // phụ trong cùng tệp sẽ để TypeScript báo, và sửa tay.
  if (!/from ["'].*i18n["']/.test(src)) {
    const depth = (file.match(/[/\\]/g) || []).length - 1;
    const rel = depth <= 1 ? "./i18n" : "../".repeat(depth - 1) + "i18n";
    const lastImport = [...src.matchAll(/^import .*;$/gm)].pop();
    if (lastImport) {
      const at = lastImport.index + lastImport[0].length;
      src = src.slice(0, at) + `\nimport { useI18n } from "${rel}";` + src.slice(at);
    }
  }
  if (!/const\s*\{\s*t\s*[,}]/.test(src)) {
    const fn = src.match(/export default function \w+\([^)]*\)\s*\{/);
    if (fn) {
      const at = fn.index + fn[0].length;
      src = src.slice(0, at) + `\n  const { t } = useI18n();` + src.slice(at);
    }
  }

  if (dry) {
    console.log(`${file}: ${edits.length} chuỗi`);
  } else {
    writeFileSync(file, src, "utf-8");
    touched += edits.length;
    console.log(`${file}: bọc ${edits.length}`);
  }
}

if (!dry) console.log(`\nTổng: ${touched} chuỗi trên ${files.length} tệp`);
