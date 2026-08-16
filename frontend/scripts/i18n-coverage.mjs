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
  const ranges = [];
  // `t(...)` trong component và `tr(...)` ngoài React — xem i18n/index.tsx.
  const re = /\b(?:t|tr)\(\s*(["'])((?:\\.|(?!\1)[^\\])*)\1/g;
  let m;
  while ((m = re.exec(src))) keys.add(unescapeLiteral(m[2]));
  // `<Trans k="…" vars={…}/>`. Khoá của nó cũng phải ghi KHOẢNG, không chỉ ghi
  // chữ: luật 4 (`= "…"`) khớp đúng vào literal này, nên nếu không có khoảng
  // che thì mọi câu dùng `<Trans>` đều bị báo là còn trần.
  const trans = /\bk=\{?\s*(["'])((?:\\.|(?!\1)[^\\])*)\1/g;
  while ((m = trans.exec(src))) {
    keys.add(unescapeLiteral(m[2]));
    ranges.push([m.index, m.index + m[0].length]);
  }

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
  // Đồng thời ghi lại KHOẢNG ký tự của mỗi lời gọi. Chỉ có tập khoá thôi thì
  // chưa đủ: xem chú thích của `ranges` ở chỗ dùng dưới kia.
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
    ranges.push([call.index, i]);
  }
  return { keys, ranges };
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
function bareStrings(src, skipLines = new Set(), wrapped = []) {
  const table = [];
  const jsx = [];

  // Một literal được tha CHỈ KHI nó nằm bên trong một lời gọi `t(`/`tr(`, xét
  // theo VỊ TRÍ. Bản trước tha theo VĂN BẢN: chuỗi nào trùng chữ với một khoá
  // đã bọc ở đâu đó trong cùng tệp thì được bỏ qua. Nghe thì hợp lý, nhưng nó
  // xoá đúng nhóm lỗi hay gặp nhất:
  //
  //     title={t("Đăng nhập")}                    ← dòng 190, đã dịch
  //     {loading ? t("Đang đăng nhập...") : "Đăng nhập"}   ← dòng 256, CÒN TRẦN
  //
  // Luật 6 bắt được dòng 256, rồi bộ lọc ném nó đi vì dòng 190 có cùng chữ.
  // Sáu nút hành động chính của hệ thống — Đăng nhập, Tạo tài khoản, Đặt lại
  // mật khẩu, Chặn IP, Khóa tài khoản, Xóa — nấp trong khe này và vẫn hiện chữ
  // Việt giữa màn hình tiếng Anh, trong khi bảng số báo 100,0%.
  //
  // Gộp khoảng chồng nhau trước khi tìm nhị phân. `t(msg, { n: t("…") })` sinh
  // ra một khoảng nằm lọt trong khoảng khác; tìm nhị phân trên tập chồng nhau
  // có thể rơi vào khoảng con rồi kết luận "ngoài" cho một vị trí thật ra nằm
  // trong khoảng cha.
  const merged = [];
  for (const [a, b] of [...wrapped].sort((x, y) => x[0] - y[0])) {
    const last = merged[merged.length - 1];
    if (last && a <= last[1]) last[1] = Math.max(last[1], b);
    else merged.push([a, b]);
  }

  const inWrapped = (at) => {
    if (at === undefined) return false;
    let lo = 0, hi = merged.length - 1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      const [a, b] = merged[mid];
      if (at < a) hi = mid - 1;
      else if (at >= b) lo = mid + 1;
      else return true;
    }
    return false;
  };

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

  // Nhóm được chọn theo LUẬT MẠNH NHẤT đã khớp, không theo luật khớp TRƯỚC.
  //
  // Bản trước dùng một tập `seen` chung cho cả hai nhóm, nên luật nào chạy sớm
  // hơn thì giành được chuỗi. Điều đó vô hiệu hoá ranh giới ghi ở chú thích của
  // KEY_TABLE ("marker không bao giờ che chữ JSX"), theo một đường vòng:
  //
  //     {busy ? t("Đang khóa…") : "Khóa tài khoản"}
  //
  // Luật 3 tìm giá trị của object literal bằng mẫu `: "…"` — và dấu hai chấm
  // của toán tử ba ngôi trông y hệt. Luật 3 chạy trước luật 6, nên chuỗi rơi
  // vào nhóm `table`; tệp có `@i18n-key-table` nên cả nhóm `table` bị bỏ; chuỗi
  // biến mất. Nút "Khóa tài khoản", "Chặn IP", "Xóa" nằm đúng trong khe này.
  //
  // Nay `jsx` luôn thắng `table`, bất kể luật nào khớp trước.
  const bucketOf = new Map();
  const make = (name) => (text, at) => {
    const s = text.trim();
    if (s.length < 2 || !VIETNAMESE.test(s)) return;
    if (at !== undefined && skipLines.has(lineOf(at))) return;
    if (inWrapped(at)) return;
    const prev = bucketOf.get(s);
    if (prev === name || prev === "jsx") return;
    if (prev === "table") {
      const i = table.indexOf(s);
      if (i >= 0) table.splice(i, 1);
    }
    bucketOf.set(s, name);
    (name === "jsx" ? jsx : table).push(s);
  };
  const pushJsx = make("jsx");
  const push = make("table");

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

  // 8. Chuỗi làm ĐỐI SỐ của một lời gọi hàm:
  //       useState("Tính toán…")
  //       new Error("Dữ liệu máy chủ trả về không đúng định dạng.")
  //       window.confirm("Bạn có chắc muốn hủy huấn luyện này?")
  //       friendlyError(err, "Không đọc được thông tin tổ chức của bạn.")
  //
  //    Nhóm này từng vô hình HOÀN TOÀN, và nó là chỗ mù cuối cùng làm bảng số
  //    báo 100% trong khi màn hình tiếng Anh vẫn còn chữ Việt. Không luật nào ở
  //    trên chạm tới nó: không nằm giữa hai thẻ (luật 1, 5), không phải thuộc
  //    tính (2), không đứng sau `:` (3) hay sau `=` (4) — vì sau `=` là tên hàm
  //    chứ không phải dấu nháy — không đứng sau `?` (6), không phải chuỗi mẫu (7).
  //
  //    Phản ví dụ đã đo được ngày 15/08/2026: `api/realtime.ts` KHÔNG mang
  //    marker nào, chứa bốn câu `throw new Error("Dữ liệu máy chủ…")`, và bộ đo
  //    vẫn báo tệp đó sạch.
  //
  //    Hai nửa, vì một biểu thức chính quy không nhìn được xa hơn một dấu:
  //      8a  neo theo TÊN HÀM  -> đối số đầu, ít nhiễu, biết được callee
  //      8b  neo theo dấu phẩy -> đối số thứ hai trở đi, và cả phần tử mảng
  //
  //    8b PHẢI phân biệt đối số với phần tử mảng, và đây là chỗ bản đầu sai:
  //    nó đẩy cả hai vào `jsx`, nên một bảng khoá viết dưới dạng MẢNG —
  //    `PRESET_REASONS` trong `BlockIpModal`, đã khai `@i18n-key-table` và đã
  //    dịch tử tế bằng `{t(r)}` ở chỗ dựng — bị báo là còn trần. Một công cụ
  //    phạt đúng cách làm đúng thì người ta sẽ học cách phớt lờ bảng số của nó.
  //
  //    Nên dò ngược tìm dấu mở đang bao literal:
  //        `(`  đối số lời gọi   -> `jsx`,   marker KHÔNG che được
  //        `[`  phần tử mảng     -> `table`, marker che được
  //        `{`  giá trị object   -> `table`, cùng nhóm với luật 3
  const CALLEE_SKIP = /^(t|tr|console\.\w+|require|import|Symbol|BigInt)$/;
  for (const m of src.matchAll(/([A-Za-z_$][\w$.]*)\s*\(\s*(["'])([^"'\n]{2,})\2/g)) {
    if (CALLEE_SKIP.test(m[1])) continue;
    pushJsx(m[3], m.index);
  }
  const enclosingOpener = (at) => {
    let depth = 0;
    for (let i = at; i >= 0; i--) {
      const c = src[i];
      if (c === ")" || c === "]" || c === "}") depth++;
      else if (c === "(" || c === "[" || c === "{") {
        if (depth === 0) return c;
        depth--;
      }
    }
    return "";
  };
  for (const m of src.matchAll(/,\s*(["'])([^"'\n]{2,})\1/g)) {
    (enclosingOpener(m.index - 1) === "(" ? pushJsx : push)(m[2], m.index);
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
  const { keys: done, ranges } = translatedKeys(src);
  for (const k of done) usedKeys.add(k);

  const { table, jsx } = bareStrings(src, ignoredLines(raw), ranges);

  // Marker chỉ áp cho nhóm `table`. Chữ JSX luôn phải tự đi qua `t()`.
  const declared = KEY_TABLE.test(raw);
  if (declared) for (const s of table) usedKeys.add(s);

  // Việc tha cho literal nằm trong `t()` đã chuyển vào `bareStrings`, xét theo
  // VỊ TRÍ. Ở đây không lọc theo văn bản nữa: trùng chữ với một khoá đã dịch
  // KHÔNG phải là bằng chứng rằng chỗ này đã dịch.
  const bare = [...(declared ? [] : table), ...jsx];
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
