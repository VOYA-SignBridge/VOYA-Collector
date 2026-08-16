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
 */

import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import DocumentViewer from "../components/legal/DocumentViewer";
import { useI18n } from "../i18n";
import {
  LEGAL_KIND_LABEL,
  fetchContent,
  type LegalDocumentContent,
  type LegalKind,
} from "../api/legal";

const KINDS = Object.keys(LEGAL_KIND_LABEL) as LegalKind[];

function isKind(value: string | undefined): value is LegalKind {
  return !!value && (KINDS as string[]).includes(value);
}

export default function LegalDocumentPage() {
  const { t } = useI18n();
  const { kind } = useParams<{ kind: string }>();
  const [params] = useSearchParams();
  const version = params.get("version") ?? undefined;

  const [doc, setDoc] = useState<LegalDocumentContent | null>(null);
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
    fetchContent(kind, version)
      .then((data) => {
        if (!cancelled) setDoc(data);
      })
      .catch(() => {
        if (!cancelled) {
          setError(
            version
              ? t("Không tìm thấy bản {version} của văn bản này.", { version })
              : t("Hệ thống chưa công bố văn bản này."),
          );
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

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <nav className="mb-6 flex flex-wrap gap-x-4 gap-y-2 text-sm">
        {KINDS.map((k) => (
          <Link
            key={k}
            to={`/legal/${k}`}
            className={
              k === kind
                ? "font-semibold text-ctu-blue"
                : "text-slate-500 hover:text-slate-800"
            }
          >
            {t(LEGAL_KIND_LABEL[k])}
          </Link>
        ))}
      </nav>

      <h1 className="mb-2 text-3xl font-bold text-slate-900">{heading}</h1>

      {loading && <p className="text-slate-500">{t("Đang tải…")}</p>}

      {!loading && error && (
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-6">
          <p className="text-slate-700">{error}</p>
          <p className="mt-2 text-sm text-slate-500">
            {t("Nếu bạn cần bản văn này để hoàn tất một thủ tục, hãy liên hệ quản trị viên tổ chức.")}
          </p>
        </div>
      )}

      {!loading && doc && (
        <>
          {/* Dải siêu dữ liệu. Mã băm hiện ra để người đọc đối chiếu được bản
              mình đang xem với bản ghi trong chấp thuận của mình — nếu không,
              "có băm" chỉ là một tính chất trên giấy. */}
          <dl className="mb-8 grid grid-cols-2 gap-x-6 gap-y-2 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-slate-500">{t("Phiên bản")}</dt>
              <dd className="font-medium text-slate-900">{doc.version}</dd>
            </div>
            <div>
              <dt className="text-slate-500">{t("Hiệu lực từ")}</dt>
              <dd className="font-medium text-slate-900">
                {new Date(doc.effective_from).toLocaleDateString("vi-VN")}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">{t("Ngôn ngữ")}</dt>
              <dd className="font-medium text-slate-900">{doc.language}</dd>
            </div>
            <div className="col-span-2 sm:col-span-1">
              <dt className="text-slate-500">{t("Mã băm nội dung")}</dt>
              <dd
                className="truncate font-mono text-xs text-slate-700"
                title={doc.content_hash}
              >
                {doc.content_hash.slice(0, 16)}…
              </dd>
            </div>
          </dl>

          {doc.change_summary && (
            <div className="mb-6 rounded-lg border border-sky-200 bg-sky-50 p-4 text-sm">
              <p className="font-semibold text-sky-900">{t("So với bản trước")}</p>
              <p className="mt-1 text-sky-800">{doc.change_summary}</p>
            </div>
          )}

          {/* Trình đọc tự chọn đường theo `body_format`: PDF nhúng, định dạng
              khác hiện thẻ tải về, markdown dựng như cũ. Xem DocumentViewer. */}
          <DocumentViewer doc={doc} />
        </>
      )}
    </div>
  );
}
