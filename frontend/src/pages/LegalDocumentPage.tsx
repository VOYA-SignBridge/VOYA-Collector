/**
 * Đọc một văn bản pháp lý. CÔNG KHAI — không cần đăng nhập.
 *
 * Trang này phải đọc được trước khi có tài khoản, vì ô "Tôi đồng ý" ở biểu mẫu
 * đăng ký chẳng có nghĩa gì nếu không mở ra được bản văn. Trước đây `url` trong
 * bản ghi trỏ tới một file tĩnh chưa từng tồn tại, nên đường dẫn ấy là 404 và
 * ô tích kia là một lời hứa suông.
 *
 * `?version=` cho phép mở đúng bản MÌNH đã ký. Đó là mục đích cuối cùng của cả
 * chuỗi phiên bản — bản ghi chấp thuận trỏ tới `(loại, số hiệu)`, và nếu số
 * hiệu ấy không mở ra được gì thì bản ghi chỉ là một con số.
 *
 * Bố cục (Đợt 2 kế hoạch UX 13/09/2026) — đọc như một TÀI LIỆU, không như form
 * -------------------------------------------------------------------------
 * Người đọc trả lời được ba câu trong vài giây: đây là văn bản gì, bản này có
 * còn áp dụng không, và có gì thay đổi. Nên thứ tự là: tên → một dòng trạng
 * thái bằng chữ thường ("Đang áp dụng · Hiệu lực từ 8 tháng 8, 2026 · Tiếng
 * Việt") → "Có gì thay đổi?" → mục lục → nội dung → lựa chọn của tôi / hỗ trợ.
 * Mã băm, số hiệu kỹ thuật, mã ngôn ngữ `vi` không xuất hiện: chúng là dữ liệu
 * cho API, không phải cho người đọc điều khoản.
 *
 * Mục lục chỉ có với văn bản markdown (tệp PDF tự có mục lục của nó). Trên máy
 * tính nó dính bên trái; trên điện thoại gấp thành một nút "Mục lục" để nội
 * dung không bị đẩy xuống sau một cột dài — như cách Stripe/Apple trình bày
 * trang điều khoản.
 */

import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import DocumentViewer from "../components/legal/DocumentViewer";
import Badge from "../components/ui/Badge";
import { DownloadIcon, PrinterIcon } from "../components/ui/Icons";
import { useI18n } from "../i18n";
import {
  LEGAL_KIND_LABEL,
  documentFileUrl,
  fetchContent,
  fetchDocumentOrNull,
  type LegalDocument,
  type LegalDocumentContent,
  type LegalKind,
} from "../api/legal";
import { extractHeadings } from "../utils/markdownOutline";

const KINDS = Object.keys(LEGAL_KIND_LABEL) as LegalKind[];

/**
 * Một câu "văn bản này nói về điều gì" — cho người chưa từng đọc điều khoản.
 *
 * @i18n-key-table — giá trị là KHOÁ từ điển, dịch ở chỗ dựng bằng `t(KIND_BLURB[kind])`;
 * bản EN nằm trong vùng `@i18n-dynamic` của `i18n/en.ts`.
 */
const KIND_BLURB: Record<LegalKind, string> = {
  terms: "Quy định khi bạn dùng hệ thống: tài khoản, trách nhiệm, điều gì được và không được làm.",
  privacy: "Hệ thống thu thập những dữ liệu nào của bạn, dùng vào việc gì, giữ bao lâu và bạn có quyền gì.",
  data_contribution: "Khi bạn đóng góp video ký hiệu: dữ liệu đó được dùng ở đâu, ai xem được, và cách rút lại.",
  guardian: "Dành cho người giám hộ đồng ý thay người dưới 18 tuổi hoặc người cần hỗ trợ quyết định.",
};

// Tên ngôn ngữ hiện bằng CHÍNH ngôn ngữ đó (như mọi bộ chọn ngôn ngữ), nên không dịch.
// i18n-ignore-next-line
const LANGUAGE_NAME: Record<string, string> = { vi: "Tiếng Việt", en: "English" };

function isKind(value: string | undefined): value is LegalKind {
  return !!value && (KINDS as string[]).includes(value);
}

function formatDate(iso: string, locale: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(locale, { day: "numeric", month: "long", year: "numeric" }).format(d);
}

export default function LegalDocumentPage() {
  const { t, lang } = useI18n();
  const { kind } = useParams<{ kind: string }>();
  const [params] = useSearchParams();
  const version = params.get("version") ?? undefined;
  const locale = lang === "en" ? "en-GB" : "vi-VN";

  const [doc, setDoc] = useState<LegalDocumentContent | null>(null);
  /** Bản ĐANG áp dụng của loại này — để nói "bản bạn đang đọc là bản cũ". */
  const [current, setCurrent] = useState<LegalDocument | null>(null);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isKind(kind)) {
      setError(t("Không có loại văn bản này."));
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    // Xoá bản đang hiện TRƯỚC khi tải bản mới. Bản trước chỉ ghi `doc` khi
    // thành công, nên đọc A rồi mở B lỗi thì thân của A nằm dưới tiêu đề B —
    // với một văn bản người ta sắp ký, đó là hướng hỏng tệ nhất (LEG-03).
    setDoc(null);
    setCurrent(null);
    void fetchDocumentOrNull(kind).then((c) => {
      if (!cancelled) setCurrent(c);
    });
    fetchContent(kind, version)
      .then((data) => {
        if (!cancelled) setDoc(data);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        // Ba nguyên nhân, ba câu: "chưa có" (404), "bạn không được xem"
        // (401/403) và "không kết nối được" (không có phản hồi). Gộp làm một
        // thì người mất mạng tưởng hệ thống chưa công bố gì.
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 404) {
          setError(
            version
              ? t("Không tìm thấy bản {version} của văn bản này.", { version })
              : t("Hệ thống chưa công bố văn bản này."),
          );
        } else if (status === 401 || status === 403) {
          setError(t("Bạn không có quyền xem bản này."));
        } else {
          setError(t("Không kết nối được với máy chủ. Kiểm tra mạng rồi tải lại trang."));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [kind, version]);

  const heading = isKind(kind) ? t(LEGAL_KIND_LABEL[kind]) : t("Văn bản pháp lý");
  const outline = useMemo(
    () => (doc && doc.body_format !== "file" ? extractHeadings(doc.body).filter((h) => h.level <= 2) : []),
    [doc],
  );
  const isCurrent = !!doc && !!current && doc.version === current.version;
  const isOld = !!doc && !!current && doc.version !== current.version;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:py-10">
      <p className="mb-1 text-sm font-medium uppercase tracking-wide text-slate-500">
        {t("Quyền riêng tư & điều khoản")}
      </p>

      {/* Bốn loại văn bản: nút tròn, xuống dòng được trên điện thoại. */}
      <nav aria-label={t("Loại văn bản")} className="mb-6 flex flex-wrap gap-2">
        {KINDS.map((k) => (
          <Link
            key={k}
            to={`/legal/${k}`}
            aria-current={k === kind ? "page" : undefined}
            className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
              k === kind
                ? "border-ctu-blue bg-ctu-blue text-white"
                : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900"
            }`}
          >
            {t(LEGAL_KIND_LABEL[k])}
          </Link>
        ))}
      </nav>

      <header className="mb-6">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">{heading}</h1>
        {isKind(kind) && (
          <p className="mt-2 max-w-2xl text-base leading-relaxed text-slate-600">{t(KIND_BLURB[kind])}</p>
        )}

        {doc && (
          <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-slate-600">
            {isCurrent && <Badge variant="success" size="sm">{t("Đang áp dụng")}</Badge>}
            {isOld && <Badge variant="neutral" size="sm">{t("Bản cũ")}</Badge>}
            <span>{t("Hiệu lực từ {date}", { date: formatDate(doc.effective_from, locale) })}</span>
            <span aria-hidden="true">·</span>
            <span>{LANGUAGE_NAME[doc.language] ?? doc.language}</span>
            <span aria-hidden="true">·</span>
            <span className="text-slate-500">{t("Bản {v}", { v: doc.version })}</span>
          </div>
        )}

        {isOld && current && (
          <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            {t("Bạn đang đọc một bản cũ. Bản đang áp dụng là bản {v}.", { v: current.version })}{" "}
            <Link to={`/legal/${kind}`} className="font-medium underline">
              {t("Mở bản đang áp dụng")}
            </Link>
          </p>
        )}
      </header>

      {loading && <p className="text-slate-500">{t("Đang tải…")}</p>}

      {!loading && error && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-6">
          <p className="text-slate-700">{error}</p>
          <p className="mt-2 text-sm text-slate-500">
            {t("Nếu bạn cần bản văn này để hoàn tất một thủ tục, hãy liên hệ quản trị viên tổ chức.")}
          </p>
        </div>
      )}

      {!loading && doc && (
        <>
          {doc.change_summary && (
            <section className="mb-6 rounded-xl border border-ctu-blue/20 bg-ctu-blue/5 p-4">
              <h2 className="text-sm font-semibold text-slate-900">{t("Có gì thay đổi so với bản trước?")}</h2>
              <p className="mt-1 text-sm leading-relaxed text-slate-700">{doc.change_summary}</p>
            </section>
          )}

          <div className={outline.length > 1 ? "lg:grid lg:grid-cols-[220px_1fr] lg:gap-10" : ""}>
            {outline.length > 1 && (
              <>
                {/* Điện thoại: gấp. Máy tính: dính bên trái. Cùng một danh sách. */}
                <details className="mb-4 rounded-lg border border-slate-200 bg-white lg:hidden">
                  <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium text-slate-800">
                    {t("Mục lục")}
                  </summary>
                  <TocList outline={outline} className="px-4 pb-3" />
                </details>
                <nav aria-label={t("Mục lục")} className="hidden lg:block lg:sticky lg:top-6 lg:self-start">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{t("Mục lục")}</p>
                  <TocList outline={outline} />
                </nav>
              </>
            )}

            <div className="min-w-0">
              {/* Trình đọc tự chọn đường theo `body_format`: PDF nhúng, định dạng
                  khác hiện thẻ tải về, markdown dựng như cũ. Xem DocumentViewer. */}
              <DocumentViewer doc={doc} />

              {doc.body_format !== "file" && (
                <div className="mt-6 flex flex-wrap gap-2 print:hidden">
                  <button
                    type="button"
                    onClick={() => window.print()}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    <PrinterIcon className="h-4 w-4" aria-hidden="true" />
                    {t("In")}
                  </button>
                  {doc.has_file && (
                    <a
                      href={documentFileUrl(doc.kind, { version: doc.version, download: true })}
                      className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                    >
                      <DownloadIcon className="h-4 w-4" aria-hidden="true" />
                      {t("Tải bản gốc")}
                    </a>
                  )}
                </div>
              )}

              {/* Hành động theo trạng thái — không phải ô tích. Việc ký/rút nằm ở
                  trang tài khoản, nơi có đăng nhập và có đủ ngữ cảnh; ở đây chỉ dẫn tới. */}
              <section className="mt-10 rounded-xl border border-slate-200 bg-slate-50 p-5 print:hidden">
                <h2 className="text-base font-semibold text-slate-900">{t("Lựa chọn của bạn")}</h2>
                <p className="mt-1 text-sm leading-relaxed text-slate-600">
                  {t("Xem bạn đã đồng ý bản nào, và thay đổi lựa chọn khi chính sách cho phép. Việc rút lại không ảnh hưởng tới phần còn lại của tài khoản.")}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Link
                    to="/settings/consents"
                    className="inline-flex items-center rounded-lg bg-ctu-blue px-4 py-2 text-sm font-semibold text-white hover:bg-ctu-navy"
                  >
                    {t("Xem lựa chọn của tôi")}
                  </Link>
                  <Link
                    to="/settings/support"
                    className="inline-flex items-center rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    {t("Cần hỗ trợ? Gửi yêu cầu bằng văn bản")}
                  </Link>
                </div>
              </section>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function TocList({ outline, className = "" }: { outline: { level: number; text: string; id: string }[]; className?: string }) {
  return (
    <ol className={`space-y-1 text-sm ${className}`}>
      {outline.map((h) => (
        <li key={h.id} className={h.level === 2 ? "pl-3" : ""}>
          <a href={`#${h.id}`} className="block py-0.5 text-slate-600 hover:text-ctu-blue">
            {h.text}
          </a>
        </li>
      ))}
    </ol>
  );
}
