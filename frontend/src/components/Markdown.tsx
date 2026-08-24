/**
 * Bộ dựng Markdown tối giản cho văn bản pháp lý.
 *
 * Vì sao tự viết thay vì thêm thư viện
 * -------------------------------------
 * Mọi thư viện markdown phổ biến đều dựng ra một chuỗi HTML, và dùng nó nghĩa
 * là gọi `dangerouslySetInnerHTML`. Trên một trang bình thường đó là đánh đổi
 * quen thuộc; trên trang này thì không, vì nội dung đến từ cơ sở dữ liệu và
 * người ghi vào đó là quản trị viên — nghĩa là một tài khoản quản trị bị chiếm
 * sẽ có một đường chạy script trong trình duyệt của MỌI người đang đọc điều
 * khoản, kể cả người chưa đăng nhập.
 *
 * Bộ dựng này trả về node React. Không có `innerHTML` ở bất kỳ đâu, nên không
 * có đường nào để một thẻ `<script>` trong bản văn trở thành thẻ script thật —
 * nó hiện ra dưới dạng chữ, đúng như nó là.
 *
 * Cái giá: chỉ hiểu tập cú pháp mà bốn văn bản pháp lý thật sự dùng — tiêu đề,
 * đoạn, danh sách, bảng, trích dẫn, đường kẻ, **đậm**, *nghiêng*, `mã`, và
 * liên kết. Cú pháp ngoài tập đó hiện ra nguyên văn thay vì biến mất; với một
 * văn bản pháp lý thì hiện thừa vài dấu sao vẫn tốt hơn là nuốt mất một câu.
 */

import { Fragment, type ReactNode } from "react";

/** Cú pháp trong DÒNG: `**đậm**`, `*nghiêng*`, `` `mã` ``, `[chữ](đường-dẫn)`. */
const INLINE = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;

/**
 * Chỉ cho phép liên kết trỏ ra ngoài bằng http(s) hoặc trỏ vào trong bằng `/`.
 *
 * Không có phép lọc này thì `[bấm vào đây](javascript:...)` là một liên kết
 * chạy được — đúng lỗ hổng mà việc tránh `innerHTML` ở trên định bịt, chỉ là
 * đi qua thuộc tính `href` thay vì qua thẻ.
 */
function safeHref(href: string): string | null {
  const trimmed = href.trim();
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  if (trimmed.startsWith("/") && !trimmed.startsWith("//")) return trimmed;
  return null;
}

function inline(text: string, keyPrefix: string): ReactNode[] {
  return text.split(INLINE).map((piece, i) => {
    const key = `${keyPrefix}-${i}`;
    if (piece.startsWith("**") && piece.endsWith("**") && piece.length > 4) {
      return <strong key={key}>{piece.slice(2, -2)}</strong>;
    }
    if (piece.startsWith("`") && piece.endsWith("`") && piece.length > 2) {
      return (
        <code key={key} className="rounded bg-slate-100 px-1 py-0.5 text-[0.9em]">
          {piece.slice(1, -1)}
        </code>
      );
    }
    if (piece.startsWith("*") && piece.endsWith("*") && piece.length > 2) {
      return <em key={key}>{piece.slice(1, -1)}</em>;
    }
    const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(piece);
    if (link) {
      const href = safeHref(link[2]);
      if (href === null) return <Fragment key={key}>{link[1]}</Fragment>;
      const external = href.startsWith("http");
      return (
        <a
          key={key}
          href={href}
          className="text-sky-700 underline underline-offset-2 hover:text-sky-900"
          {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
        >
          {link[1]}
        </a>
      );
    }
    return <Fragment key={key}>{piece}</Fragment>;
  });
}

/** Một dòng của bảng markdown thành mảng ô, bỏ hai dấu `|` ngoài cùng. */
function cells(row: string): string[] {
  return row.replace(/^\s*\|/, "").replace(/\|\s*$/, "").split("|").map((c) => c.trim());
}

/**
 * VÌ SAO KHÔNG CÓ MỘT BIẾN THỂ `dark:` NÀO TRONG TỆP NÀY
 * ------------------------------------------------------
 * Đã từng có tám cái, và chúng gây ra một lỗi hiển thị nghiêm trọng.
 *
 * `tailwind.config` không khai báo `darkMode`, nên Tailwind dùng mặc định
 * `'media'` — biến thể `dark:` kích hoạt theo `prefers-color-scheme` của HỆ
 * ĐIỀU HÀNH. Nhưng ứng dụng này **không có chủ đề tối**: không tệp nào khác
 * dùng `dark:`, nên nền trang luôn sáng.
 *
 * Hệ quả trên máy bật chế độ tối: `dark:text-slate-200` cho chữ `#e2e8f0` trên
 * nền trắng — tỉ lệ tương phản khoảng 1.2:1, gần như vô hình — và
 * `dark:bg-amber-950/30` biến khối cảnh báo thành một mảng nâu sẫm. Người dùng
 * báo "văn bản pháp lý nhìn không rõ"; đây là nguyên nhân.
 *
 * Đây là kiểu hỏng không bao giờ lộ ra với người phát triển dùng chế độ sáng.
 *
 * Muốn có chủ đề tối thì phải làm cho CẢ ứng dụng cùng lúc, và đặt
 * `darkMode: 'class'` để nó là một LỰA CHỌN chứ không phải một suy đoán từ cài
 * đặt hệ điều hành. Thêm `dark:` vào riêng một tệp là tái lập đúng lỗi này.
 */

const HEADING_CLASS: Record<number, string> = {
  1: "mt-0 mb-4 text-2xl font-semibold tracking-tight",
  2: "mt-8 mb-3 text-xl font-semibold tracking-tight",
  3: "mt-6 mb-2 text-base font-semibold",
};

export default function Markdown({ text }: { text: string }) {
  const lines = (text || "").replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];

  let i = 0;
  let key = 0;
  const push = (node: ReactNode) => blocks.push(<Fragment key={key++}>{node}</Fragment>);

  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) {
      i += 1;
      continue;
    }

    // Đường kẻ ngang. Phải xét TRƯỚC danh sách: `---` cũng bắt đầu bằng `-`.
    if (/^\s*(-{3,}|_{3,}|\*{3,})\s*$/.test(line)) {
      push(<hr className="my-8 border-slate-200" />);
      i += 1;
      continue;
    }

    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) {
      const level = Math.min(heading[1].length, 3);
      const Tag = (`h${level}` as "h1" | "h2" | "h3");
      push(<Tag className={HEADING_CLASS[level]}>{inline(heading[2], `h${key}`)}</Tag>);
      i += 1;
      continue;
    }

    if (/^\s*>\s?/.test(line)) {
      const quoted: string[] = [];
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
        quoted.push(lines[i].replace(/^\s*>\s?/, ""));
        i += 1;
      }
      push(
        <blockquote className="my-4 border-l-4 border-amber-400 bg-amber-50 px-4 py-3 text-sm">
          {inline(quoted.join(" "), `q${key}`)}
        </blockquote>,
      );
      continue;
    }

    // Bảng: một dòng có `|`, theo sau là dòng phân cách `|---|---|`.
    if (line.includes("|") && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(lines[i + 1])) {
      const header = cells(line);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].includes("|") && lines[i].trim()) {
        rows.push(cells(lines[i]));
        i += 1;
      }
      push(
        // Bảng cuộn trong hộp của chính nó: một bảng rộng không được đẩy cả
        // trang trượt ngang trên điện thoại.
        <div className="my-4 overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b-2 border-slate-300">
                {header.map((cell, c) => (
                  <th key={c} className="px-3 py-2 text-left font-semibold">
                    {inline(cell, `th${key}-${c}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, r) => (
                <tr key={r} className="border-b border-slate-200">
                  {row.map((cell, c) => (
                    <td key={c} className="px-3 py-2 align-top">
                      {inline(cell, `td${key}-${r}-${c}`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }

    if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const items: string[] = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*([-*]|\d+\.)\s+/, ""));
        i += 1;
        // Gom PHẦN ĐUÔI của mục vừa rồi: những dòng liền sau nó mà không mở
        // một khối mới. Markdown gọi đây là "lazy continuation".
        //
        // Trước 19/08 vòng lặp dừng ngay khi dòng kế không bắt đầu bằng dấu
        // gạch đầu dòng, nên một mục viết trên hai dòng bị xé làm đôi: nửa đầu
        // thành mục danh sách, nửa sau thành một đoạn văn riêng. Với chữ
        // thường thì chỉ hơi lạ, nhưng một cụm `**đậm**` bắc qua chỗ ngắt sẽ
        // mất dấu đóng ở nửa này và mất dấu mở ở nửa kia — hai dấu sao hiện ra
        // nguyên văn giữa một văn bản pháp lý. Bốn văn bản đã công bố có tám
        // chỗ như vậy.
        while (
          i < lines.length &&
          lines[i].trim() &&
          !/^\s*([-*]|\d+\.)\s+/.test(lines[i]) &&
          !/^\s*(#{1,6}\s|>|-{3,}\s*$|_{3,}\s*$|\*{3,}\s*$)/.test(lines[i])
        ) {
          items[items.length - 1] += ` ${lines[i].trim()}`;
          i += 1;
        }
      }
      const ListTag = ordered ? "ol" : "ul";
      push(
        <ListTag
          className={`my-3 space-y-1 pl-6 ${ordered ? "list-decimal" : "list-disc"}`}
        >
          {items.map((item, n) => (
            <li key={n}>{inline(item, `li${key}-${n}`)}</li>
          ))}
        </ListTag>,
      );
      continue;
    }

    // Đoạn văn: gom các dòng liền nhau cho tới dòng trống hoặc một khối khác.
    const paragraph: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !/^\s*(#{1,6}\s|>|[-*]\s|\d+\.\s|-{3,}$)/.test(lines[i])
    ) {
      paragraph.push(lines[i].trim());
      i += 1;
    }
    if (paragraph.length) {
      push(<p className="my-3 leading-relaxed">{inline(paragraph.join(" "), `p${key}`)}</p>);
    }
  }

  return <div className="text-slate-800">{blocks}</div>;
}
