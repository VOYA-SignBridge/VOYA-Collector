import { documentFileUrl, type LegalDocumentContent } from "../../api/legal";
import Markdown from "../Markdown";
import { DownloadIcon, ScrollTextIcon } from "../ui/Icons";
import { useI18n } from "../../i18n";

/**
 * Hiển thị một bản văn pháp lý, dù nó được lưu kiểu nào.
 *
 * Ba đường, và việc chọn đường nào KHÔNG dựa vào phỏng đoán
 * ----------------------------------------------------------
 * 1. `body_format === "file"` + PDF → nhúng thẳng bằng `<object>`.
 * 2. `body_format === "file"` + định dạng khác → thẻ siêu dữ liệu + nút tải.
 * 3. Còn lại → markdown, đúng như bốn văn bản đã công bố trước v3.15.
 *
 * Vì sao KHÔNG dựng trình đọc DOCX trong trình duyệt
 * ---------------------------------------------------
 * Không có trình duyệt nào mở được `.docx` một cách tự nhiên. Muốn hiện nó
 * trong trang thì phải hoặc kéo về một thư viện chuyển đổi nặng vài trăm KB,
 * hoặc gửi tệp qua một dịch vụ xem của bên thứ ba. Đường thứ hai là **gửi văn
 * bản pháp lý của tổ chức ra ngoài** — không làm. Đường thứ nhất cho ra một
 * bản dựng GẦN GIỐNG bản gốc, và với một tài liệu người ta sắp ký thì "gần
 * giống" là hướng hỏng tệ nhất: nó trông như bản thật.
 *
 * Nên: nói thẳng đây là tệp gì, bao nhiêu byte, và đưa nút tải. Người đọc mở
 * bằng phần mềm của họ, và thứ họ đọc đúng là thứ tổ chức đã ký.
 *
 * `<object>` chứ không phải `<iframe>`
 * -------------------------------------
 * `<object>` có nội dung dự phòng dựng sẵn: trình duyệt nào không mở được PDF
 * (nhiều trình duyệt di động) sẽ hiển thị phần bên trong thẻ thay vì một khung
 * trắng. Với `<iframe>` thì khung trắng là tất cả những gì người dùng thấy, và
 * không có sự kiện nào báo cho JavaScript biết điều đó.
 */

function formatBytes(n: number | null): string {
  if (!n) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DocumentViewer({ doc }: { doc: LegalDocumentContent }) {
  const { t } = useI18n();

  if (doc.body_format !== "file") {
    return (
      <article className="prose-legal">
        <Markdown text={doc.body} />
      </article>
    );
  }

  const viewUrl = documentFileUrl(doc.kind, { version: doc.version });
  const downloadUrl = documentFileUrl(doc.kind, {
    version: doc.version,
    download: true,
  });
  const isPdf = (doc.file_mime || "").includes("pdf");

  const downloadButton = (
    <a
      href={downloadUrl}
      className="inline-flex items-center gap-2 rounded-xl bg-ctu-blue px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-ctu-navy focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue focus-visible:ring-offset-2"
    >
      <DownloadIcon className="h-4 w-4" aria-hidden="true" />
      {t("Tải bản gốc")}
    </a>
  );

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
        <span className="flex min-w-0 items-center gap-3">
          <ScrollTextIcon className="h-5 w-5 shrink-0 text-slate-400" aria-hidden="true" />
          <span className="min-w-0">
            <span className="block truncate font-medium text-slate-900">
              {doc.file_name || t("Bản văn gốc")}
            </span>
            <span className="block text-xs text-slate-500">
              {formatBytes(doc.file_size)}
              {doc.file_mime ? ` · ${doc.file_mime.split(";")[0]}` : ""}
            </span>
          </span>
        </span>
        {downloadButton}
      </div>

      {isPdf ? (
        <object
          data={viewUrl}
          type="application/pdf"
          aria-label={doc.title || t("Văn bản pháp lý")}
          className="h-[75vh] w-full rounded-xl border border-slate-200 bg-white"
        >
          {/* Nội dung dự phòng: trình duyệt không mở được PDF sẽ dựng phần này
              thay vì một khung trắng không giải thích được. */}
          <div className="p-6 text-sm leading-relaxed text-slate-700">
            <p>
              {t("Trình duyệt của bạn không mở được tệp PDF ngay trong trang.")}
            </p>
            <p className="mt-3">{downloadButton}</p>
          </div>
        </object>
      ) : (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-6 text-sm leading-relaxed text-slate-700">
          <p>
            {t(
              "Bản văn này được lưu dưới định dạng cần mở bằng phần mềm soạn thảo. Tải về để đọc bản gốc đúng như tổ chức đã ban hành.",
            )}
          </p>
          <p className="mt-3">{downloadButton}</p>
        </div>
      )}
    </section>
  );
}
