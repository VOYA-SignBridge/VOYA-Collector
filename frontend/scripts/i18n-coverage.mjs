#!/usr/bin/env node
/**
 * Đo độ phủ i18n, và liệt kê chính xác những gì còn thiếu.
 *
 * Vì sao cần công cụ này
 * -----------------------
 * "Đã làm i18n" là một câu không kiểm chứng được bằng mắt. Đợt trước bộ khung
 * i18n được dựng xong, 63 chuỗi được dịch, và báo cáo ghi là "đã xong" — trong
 * khi `t()` chỉ được gọi ở đúng MỘT tệp. Đổi ngôn ngữ sang tiếng Anh thì không
 * có gì đổi. Không ai phát hiện ra vì không có con số nào để đối chiếu.
 *
 * Công cụ này đếm ba thứ:
 *
 *   1. Chuỗi tiếng Việt **hiển thị được** còn nằm trần trong mã (chưa qua `t()`)
 *   2. Khoá đã đi qua `t()` nhưng **thiếu bản dịch** trong `en.ts`
 *   3. Khoá trong `en.ts` **không còn ai dùng** (rác sau khi đổi giao diện)
 *
 * Chỗ khó là (1): phải phân biệt chữ người dùng ĐỌC với chuỗi chỉ máy đọc.
 * `className="..."`, `to="/settings"`, khoá của object, tên biến — tất cả đều
 * là chuỗi, và không cái nào cần dịch. Bộ lọc dưới đây đi theo hướng **báo
 * thiếu còn hơn báo thừa**: một cảnh báo giả làm người ta ngừng tin cả bảng số.
 *
 * Dùng:
 *   node scripts/i18n-coverage.mjs           # tóm tắt
 *   node scripts/i18n-coverage.mjs --list    # kèm từng chuỗi còn trần
 *   node scripts/i18n-coverage.mjs --missing # kèm khoá thiếu bản dịch
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(fileURLToPath(new URL(".", import.meta.url)), "..");
const SRC = join(ROOT, "src");

const VIETNAMESE =
  /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;

/** Thuộc tính JSX mang chữ người dùng đọc. Ngoài danh sách này thì bỏ qua. */
const TEXT_ATTRS = new Set([
  "title", "placeholder", "label", "subtitle", "description", "alt",
  "aria-label", "hint", "body", "heading", "emptyText", "confirmLabel",
]);

/** Tệp không tính: test, bản dịch, và công cụ. */
const SKIP = /(__tests__|\.test\.|\.spec\.|[/\\]i18n[/\\])/;

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.tsx?$/.test(full) && !SKIP.test(full)) out.push(full);
  }
  return out;
}

/**
 * Bỏ chú thích để chữ tiếng Việt trong đó không bị tính là chuỗi giao diện.
 *
 * Thay bằng DẤU CÁCH chứ không xoá hẳn: độ dài chuỗi giữ nguyên, nên vị trí
 * `index` của mọi phép khớp vẫn trỏ đúng vào bản gốc. Nhờ vậy mới tra ngược
 * được số dòng — và số dòng là thứ cần để đọc chỉ thị `i18n-ignore-next-line`.
 * Bản cũ xoá hẳn khiến mọi dòng sau một chú thích khối bị lệch.
 */
function stripComments(src) {
  const blank = (m) => m.replace(/[^\n]/g, " ");
  return src
    .replace(/\/\*[\s\S]*?\*\//g, blank)
    .replace(/(^|[^:])(\/\/.*)$/gm, (_, pre, c) => pre + blank(c));
}

/**
 * Dòng được miễn trừ bằng `// i18n-ignore-next-line`.
 *
 * Có sẵn `@i18n-key-table` rồi, vì sao cần thêm?  Vì marker kia che CẢ TỆP, và
 * đó đúng là cách nó đã hai lần giấu chuỗi thật khỏi bảng số. Một chỉ thị bó
 * trong MỘT dòng thì phạm vi nhỏ nhất có thể, và nó nằm ngay cạnh dòng nó tha
 * — người đọc mã thấy ngay lý do, thay vì phải cuộn lên đầu tệp.
 *
 * Chỉ dùng cho chữ KHÔNG bao giờ lên màn hình người dùng: `console.warn` ở DEV,
 * khoá của một bảng đã được dịch ở chỗ khác. Kèm lý do ngay dòng dưới.
 */
function ignoredLines(raw) {
  const lines = raw.split("\n");
  const out = new Set();
  lines.forEach((line, i) => {
    if (!/i18n-ignore-next-line/.test(line)) return;
    // "Dòng kế" nghĩa là dòng MÃ kế tiếp, không phải dòng văn bản kế tiếp: lý
    // do của một miễn trừ thường dài hơn một dòng, và nếu phần lý do tự nuốt
    // mất hiệu lực của chỉ thị thì chỉ thị đó im lặng không làm gì.
    let j = i + 1;
    while (j < lines.length && /^\s*(\/\/|\*|\/\*)/.test(lines[j])) j++;
    out.add(j + 1); // 1-based
  });
  return out;
}

/**
 * Các chuỗi ĐÃ đi qua `t(...)` hoặc `<Trans k="…">`, để trừ ra khỏi phần trần.
 *
 * `<Trans>` phải được đếm ở đây, nếu không công cụ sẽ **phạt** đúng việc sửa
 * mảnh câu: gộp năm mảnh thành một khoá trọn vẹn sẽ làm độ phủ tụt xuống và năm
 * mảnh cũ hiện lên như "khoá không ai dùng". Một thước đo trừng phạt cách làm
 * đúng là một thước đo người ta sẽ ngừng nghe.
 */
/**
 * Giải mã ký tự thoát của một literal TS về đúng chuỗi lúc chạy.
 *
 * Bắt buộc, không phải cho đẹp: `t('Dùng nút "X"')` và `t("Dùng nút \"X\"")` là
 * CÙNG một khoá lúc chạy nhưng khác nhau ở dạng nguồn. So sánh dạng nguồn sẽ
 * báo một khoá đã dịch là "còn thiếu" và bản dịch của nó là "không ai dùng" —
 * hai con số sai cùng một lúc, và cách sửa mà chúng gợi ý (thêm khoá thứ hai)
 * làm hỏng từ điển.
 */
function unescapeLiteral(raw) {
  return raw.replace(/\\(["'\\nt])/g, (_, c) =>
    c === "n" ? "\n" : c === "t" ? "\t" : c,
  );
}

function translatedKeys(src) {
  const keys = new Set();
  // `t(...)` trong component và `tr(...)` ngoài React — xem i18n/index.tsx.
  const re = /\b(?:t|tr)\(\s*(["'])((?:\\.|(?!\1)[^\\])*)\1/g;
  let m;
  while ((m = re.exec(src))) keys.add(unescapeLiteral(m[2]));
  const trans = /\bk=\{?\s*(["'])((?:\\.|(?!\1)[^\\])*)\1/g;
  while ((m = trans.exec(src))) keys.add(unescapeLiteral(m[2]));

  // Khoá KHÔNG đứng ngay sau `t(`. Chuyện thường gặp và hoàn toàn đúng:
  //
  //     const title = t(cancelled ? 'Huấn luyện đã bị hủy' : diag.title);
  //
  // Cả hai nhánh đều là khoá, và `t()` bọc ngoài dịch bất kể nhánh nào trúng.
  // Không đếm chúng thì bộ đo báo là "còn trần", và cách sửa mà nó gợi ý —
  // bọc thêm `t()` vào từng nhánh — tạo ra `t(t(x))`, dịch hai lần.
  //
  // Nên: quét cân bằng ngoặc, mọi literal nằm TRONG một lời gọi `t(`/`tr(` đều
  // tính là đã dịch.
  for (const call of src.matchAll(/\b(?:t|tr)\(/g)) {
    let i = call.index + call[0].length;
    let depth = 1;
    while (i < src.length && depth > 0) {
      const c = src[i];
      if (c === "(") depth++;
      else if (c === ")") depth--;
      else if (c === '"' || c === "'") {
        const lit = new RegExp(`${c}((?:\\\\.|[^\\\\${c}])*)${c}`, "y");
        lit.lastIndex = i;
        const hit = lit.exec(src);
        if (hit) {
          keys.add(unescapeLiteral(hit[1]));
          i = lit.lastIndex;
          continue;
        }
      }
      i++;
    }
  }
  return keys;
}

/**
 * Tệp khai báo BẢNG KHOÁ: chữ tiếng Việt trong đó là khoá từ điển, được dịch ở
 * chỗ dùng (`tr(BY_CODE[code])`), không phải chữ bỏ quên.
 *
 * Cần một lối khai báo tường minh vì công cụ không thể tự biết: `"Hủy"` trong
 * một object literal trông y hệt dù nó là nhãn nút chưa dịch hay một khoá sẽ đi
 * qua `t()` ở nơi khác. Đoán bừa theo hướng nào cũng sai — hoặc bỏ sót chuỗi
 * thật, hoặc báo động giả tới mức không ai còn đọc bảng số.
 *
 * Đặt marker này là một lời hứa: mọi chuỗi tiếng Việt trong BẢNG của tệp PHẢI
 * được đưa qua `t()`/`tr()` ở chỗ dùng. Nó không tự kiểm được, nên đừng rắc bừa.
 *
 * **Marker CHỈ che chuỗi trong bảng (luật 2–4), KHÔNG che chữ JSX (luật 1, 5).**
 * Ranh giới này là kết quả của một lần đo sai: bản đầu cho marker che cả tệp,
 * và 33 câu tiếng Việt nằm thẳng trong JSX của 9 tệp có marker bị tính là "đã
 * dịch". Báo cáo ra 100% trong khi màn hình vẫn còn chữ Việt lúc chọn tiếng
 * Anh. Chữ JSX không bao giờ là "khoá của một bảng", nên không có lý do gì cho
 * nó nấp sau marker.
 */
const KEY_TABLE = /@i18n-key-table\b/;

/**
 * Bỏ mọi `${…}` khỏi một chuỗi mẫu, ĐẾM CÂN BẰNG NGOẶC NHỌN.
 *
 * `\$\{[^}]*\}` dừng ở dấu `}` đầu tiên, nên một biểu thức có object bên trong
 * — `${t("…", { n: x })}` — chỉ bị cắt một nửa, và phần đuôi còn lại mang theo
 * chữ tiếng Việt của chính lời gọi `t()` đó. Kết quả là công cụ báo một chuỗi
 * ĐÃ dịch là còn trần.
 */
function stripInterp(body) {
  let out = "", i = 0;
  while (i < body.length) {
    if (body[i] === "$" && body[i + 1] === "{") {
      let depth = 1;
      i += 2;
      while (i < body.length && depth > 0) {
        if (body[i] === "{") depth++;
        else if (body[i] === "}") depth--;
        i++;
      }
      continue;
    }
    out += body[i++];
  }
  return out;
}

/**
 * Trả về hai nhóm tách bạch:
 *   `table` — chuỗi trong bảng/hằng, marker `@i18n-key-table` che được;
 *   `jsx`   — chữ hiển thị thẳng trong JSX, KHÔNG bao giờ được che.
 */
function bareStrings(src, skipLines = new Set()) {
  const table = [];
  const jsx = [];
  const seen = new Set();

  // Bảng tra chỉ số → số dòng, dựng một lần. `stripComments` giữ nguyên độ dài
  // nên chỉ số ở đây trỏ đúng vào tệp gốc.
  const lineStarts = [0];
  for (let i = 0; i < src.length; i++) if (src[i] === "\n") lineStarts.push(i + 1);
  const lineOf = (at) => {
    let lo = 0, hi = lineStarts.length - 1;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if (lineStarts[mid] <= at) lo = mid;
      else hi = mid - 1;
    }
    return lo + 1;
  };

  const make = (bucket) => (text, at) => {
    const s = text.trim();
    if (s.length < 2 || !VIETNAMESE.test(s) || seen.has(s)) return;
    if (at !== undefined && skipLines.has(lineOf(at))) return;
    seen.add(s);
    bucket.push(s);
  };
  const pushJsx = make(jsx);
  const push = make(table);

  // 1. Chữ nằm giữa hai thẻ JSX: >Xin chào<
  for (const m of src.matchAll(/>([^<>{}\n][^<>{}]*)</g)) pushJsx(m[1], m.index);

  // 2. Thuộc tính JSX trong danh sách trên: placeholder="Nhập tên"
  for (const m of src.matchAll(/\b([\w-]+)\s*=\s*(["'])([^"'\n]+)\2/g)) {
    if (TEXT_ATTRS.has(m[1])) push(m[3], m.index);
  }

  // 3. Giá trị chuỗi trong object literal — nơi các bảng nhãn hay nằm
  //    (`STATUS_LABEL`, `CATEGORY_LABEL`, mảng cấu hình…).
  for (const m of src.matchAll(/:\s*(["'])([^"'\n]{2,})\1/g)) push(m[2], m.index);

  // 4. Câu gán cho một hằng hoặc một tham số mặc định: `const X = "…"`,
  //    `function f(msg = "…")`. Bỏ qua nhóm này từng làm một câu tiếng Việt
  //    có thật biến mất khỏi mọi con số — nó không bị tính là còn trần, và
  //    bản dịch của nó thì bị báo là "không ai dùng".
  for (const m of src.matchAll(/=\s*(["'])([^"'\n]{2,})\1/g)) push(m[2], m.index);

  // 5. Chữ nằm CÙNG nút văn bản với một `{biểu thức}`:
  //       >Đã chụp {n} mẫu<        →  "Đã chụp" và "mẫu"
  //    Luật 1 loại hẳn mọi đoạn có `{`, nên nhóm này từng vô hình — và nó
  //    chính là nhóm `<Trans>` sinh ra để xử lý. Bỏ sót nó nghĩa là báo 100%
  //    trong khi màn hình vẫn còn chữ Việt lúc chọn tiếng Anh.
  //
  //    Hai đầu neo giữ nguyên lớp ký tự cấm của luật 1 (`<`, `>`, `{`, `}`,
  //    xuống dòng). Nới rộng hơn là gặp lại đúng cái bẫy `=>` và dấu đóng
  //    generic đã phá 8 tệp — xem docs/I18N.md §7.
  const jsxAdjacent = (text, at) => {
    // `$`, backtick và dấu nháy chỉ xuất hiện khi phép khớp đã trượt vào một
    // chuỗi mẫu lồng nhau (`${…}`), không phải chữ thật trong JSX.
    if (/[`$"']/.test(text)) return;
    pushJsx(text, at);
  };
  for (const m of src.matchAll(/>([^<>{}\n]{2,})\{/g)) jsxAdjacent(m[1], m.index);
  for (const m of src.matchAll(/\}([^<>{}\n]{2,})</g)) jsxAdjacent(m[1], m.index);

  // 6. Nhánh của toán tử ba ngôi và của `??` / `||`:
  //       {running ? "Dừng nhận diện" : t("Bắt đầu nhận diện")}
  //       {name || "(không tên)"}
  //    Nhóm này từng vô hình HOÀN TOÀN, và nó là nhóm đông nhất còn lại:
  //    nhánh sau `?` không khớp luật nào, còn nhánh sau `:` thì khớp luật 3 —
  //    tức rơi vào `table` và bị marker `@i18n-key-table` che mất. Một câu như
  //    "Dừng nhận diện" nằm ngay giữa màn hình nhận diện mà bảng số vẫn báo
  //    100%: đúng cái bẫy đã sập một lần, chỉ khác lối vào.
  //
  //    Đi theo DÒNG chứ không theo cả tệp: chỉ những literal đứng SAU dấu `?`
  //    đầu tiên của dòng mới là toán hạng ba ngôi. Nhờ vậy một dòng bảng bình
  //    thường (`{ ok: "Được", bad: "Hỏng" }`) không bị đụng tới.
  //
  //    Vào thẳng `jsx`: đây là chữ dựng lúc chạy, không đời nào là "khoá của
  //    một bảng", nên marker không được phép che.
  //    `${`, `}` và backtick chỉ lọt vào khi phép khớp đã trượt vào giữa một
  //    chuỗi mẫu — mảnh cụt kiểu `}°C · Công suất ${x ??` không phải chuỗi thật.
  const ternary = (text, at) => {
    if (/[`}]/.test(text) || text.includes("${")) return;
    pushJsx(text, at);
  };
  {
    let base = 0;
    for (const line of src.split("\n")) {
      const q = line.search(/\?[^.?]/); // bỏ qua `?.` và `??`
      const tail = q >= 0 ? line.slice(q) : "";
      for (const m of tail.matchAll(/["']([^"'\n]{2,})["']/g)) ternary(m[1], base + q + m.index);
      for (const m of line.matchAll(/(?:\?\?|\|\|)\s*(["'])([^"'\n]{2,})\1/g)) ternary(m[2], base + m.index);
      base += line.length + 1;
    }
  }

  // 7. Chuỗi mẫu (template literal) có chữ tiếng Việt:
  //       confirmLabel: `Xóa ${n} mục`
  //       message: `Xóa VĨNH VIỄN nhãn "${ten}". Không thể hoàn tác.`
  //    Không luật nào ở trên nhìn thấy nhóm này — chúng không phải literal
  //    thường, không nằm giữa hai thẻ, không đứng sau `?`. Nút "Xóa vĩnh viễn"
  //    trong thùng rác nằm đúng ở đây, và nó hiện ra chữ Việt giữa màn hình
  //    tiếng Anh trong khi bảng số vẫn báo 100%.
  //
  //    Báo cả chuỗi mẫu chứ không cắt nhỏ: cách sửa đúng là một khoá TRỌN CÂU
  //    với chỗ trống (`t("Xóa {n} mục", { n })`), nên thứ cần hiện ra trước mắt
  //    người sửa cũng phải là trọn câu.
  //
  //    Vào `jsx` — marker không che được, vì đây không phải bảng khoá.
  //    Bó trong MỘT dòng (`\n` nằm trong lớp ký tự cấm). Cho phép vắt dòng thì
  //    một dấu backtick lẻ — trong chú thích, hay trong chuỗi mẫu lồng nhau —
  //    sẽ nuốt trọn mấy chục dòng mã và in ra như thể đó là một câu cần dịch.
  //    Chuỗi mẫu nhiều dòng có chữ Việt gần như không có; thà bỏ sót một cái
  //    còn hơn in ra một bảng không ai đọc nổi.
  for (const m of src.matchAll(/`([^`\\\n]*)`/g)) {
    const body = m[1];
    // Chỉ xét phần CHỮ, bỏ mọi `${…}` ra ngoài. `` `· ${t("vĩnh viễn")}` `` đã
    // được dịch tử tế rồi; tính nó là còn trần thì công cụ đang phạt đúng cách
    // làm đúng, và người ta sẽ học cách phớt lờ bảng số.
    if (!VIETNAMESE.test(stripInterp(body))) continue;
    // Chuỗi mẫu chỉ dùng để ghép class CSS hay đường dẫn thì không có chữ Việt,
    // nên tới được đây nghĩa là nó mang chữ người đọc.
    pushJsx(body.replace(/\s+/g, " "), m.index);
  }

  return { table, jsx };
}

const files = walk(SRC);
let bareTotal = 0;
const perFile = [];
const usedKeys = new Set();

for (const file of files) {
  const raw = readFileSync(file, "utf-8");
  const src = stripComments(raw);
  const done = translatedKeys(src);
  for (const k of done) usedKeys.add(k);

  const { table, jsx } = bareStrings(src, ignoredLines(raw));

  // Marker chỉ áp cho nhóm `table`. Chữ JSX luôn phải tự đi qua `t()`.
  const declared = KEY_TABLE.test(raw);
  if (declared) for (const s of table) usedKeys.add(s);

  // So khớp cả dạng đã cắt khoảng trắng. Khoá `" và "` (dấu cách hai đầu nằm
  // TRONG khoá, vì bản dịch phải tự quyết khoảng trắng của mình) được bộ đo
  // hiển thị dưới dạng đã cắt là `"và"` — nếu chỉ so nguyên văn thì một chuỗi
  // đã dịch tử tế vẫn bị đếm là còn trần, mãi mãi.
  const doneTrimmed = new Set([...done].map((k) => k.trim()));
  const bare = [...(declared ? [] : table), ...jsx].filter(
    (s) => !done.has(s) && !doneTrimmed.has(s.trim()),
  );
  if (bare.length) {
    perFile.push({ file: relative(ROOT, file), bare });
    bareTotal += bare.length;
  }
}

// en.ts: khoá đã dịch
const enSrc = readFileSync(join(SRC, "i18n", "en.ts"), "utf-8");
const translated = new Set(
  [...enSrc.matchAll(/^\s*(["'])((?:\\.|(?!\1)[^\\])*)\1\s*:/gm)].map((m) =>
    unescapeLiteral(m[2]),
  ),
);

/**
 * Khoá được tra ĐỘNG: `t(a.message)`, `t(s.role)` — chuỗi đến từ máy chủ.
 *
 * Công cụ này chỉ nhìn thấy literal, nên một khoá chỉ được dùng qua biến sẽ
 * hiện lên như "không ai dùng". Xoá nó đi là làm bảng số xanh trong khi màn
 * hình mất chữ — hỏng đúng thứ mà con số đó lẽ ra phải bảo vệ.
 *
 * Nên phải khai báo, và khai báo phải CÓ BIÊN: một cặp begin/end trong `en.ts`
 * chứ không phải một cờ che cả tệp. Cái marker che-cả-tệp đã hai lần giấu mất
 * chuỗi thật; không lặp lại kiểu đó ở đây.
 *
 *     // @i18n-dynamic:begin — lý do
 *     "API": "API",
 *     // @i18n-dynamic:end
 */
function dynamicKeys(enSource) {
  const out = new Set();
  let inside = false;
  for (const line of enSource.split("\n")) {
    if (/@i18n-dynamic:begin/.test(line)) { inside = true; continue; }
    if (/@i18n-dynamic:end/.test(line)) { inside = false; continue; }
    if (!inside) continue;
    const m = /^\s*(["'])((?:\\.|(?!\1)[^\\])*)\1\s*:/.exec(line);
    if (m) out.add(unescapeLiteral(m[2]));
  }
  return out;
}

const dynamic = dynamicKeys(enSrc);
const missing = [...usedKeys].filter((k) => VIETNAMESE.test(k) && !translated.has(k));
const orphan = [...translated].filter((k) => !usedKeys.has(k) && !dynamic.has(k));

const wrapped = usedKeys.size;
const totalVisible = wrapped + bareTotal;
const pct = totalVisible ? ((wrapped / totalVisible) * 100).toFixed(1) : "0.0";

// `--json` cho công cụ khác đọc (codemod, CI). In ra rồi thoát để không lẫn với
// bảng số dành cho người.
if (process.argv.includes("--json")) {
  console.log(JSON.stringify({ perFile, missing, orphan }, null, 2));
  process.exit(0);
}

console.log("");
console.log("  ĐỘ PHỦ i18n");
console.log("  " + "-".repeat(58));
console.log(`  Chuỗi đã qua t()          ${String(wrapped).padStart(5)}`);
console.log(`  Chuỗi còn trần            ${String(bareTotal).padStart(5)}  (${perFile.length} tệp)`);
console.log(`  Độ phủ                    ${String(pct).padStart(5)}%`);
console.log("  " + "-".repeat(58));
console.log(`  Khoá thiếu bản dịch EN    ${String(missing.length).padStart(5)}`);
console.log(`  Khoá EN không ai dùng     ${String(orphan.length).padStart(5)}`);
console.log("");

if (process.argv.includes("--missing") && missing.length) {
  console.log("  THIẾU BẢN DỊCH:");
  for (const k of missing.sort()) console.log(`    ${JSON.stringify(k)}: "",`);
  console.log("");
}

// Khoá mồ côi thường xuất hiện sau khi gộp mảnh câu hoặc đổi chữ trong giao
// diện. Chúng vô hại lúc chạy nhưng làm bảng số nhiễu, nên phải xoá được.
if (process.argv.includes("--orphan") && orphan.length) {
  console.log("  KHOÁ EN KHÔNG AI DÙNG:");
  for (const k of orphan.sort()) console.log(`    ${JSON.stringify(k)}`);
  console.log("");
}

if (process.argv.includes("--list")) {
  for (const { file, bare } of perFile.sort((a, b) => b.bare.length - a.bare.length)) {
    console.log(`  ${file}  (${bare.length})`);
    for (const s of bare) console.log(`      ${s}`);
  }
} else if (perFile.length) {
  console.log("  TỆP CÒN NHIỀU CHUỖI TRẦN NHẤT:");
  for (const { file, bare } of perFile.sort((a, b) => b.bare.length - a.bare.length).slice(0, 15)) {
    console.log(`    ${String(bare.length).padStart(4)}  ${file}`);
  }
  console.log("");
  console.log("  (--list để xem từng chuỗi, --missing để lấy khuôn cho en.ts)");
}
console.log("");
