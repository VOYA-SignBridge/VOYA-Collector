/**
 * Thẻ một ký hiệu — `/learn/:slug`. CÔNG KHAI.
 *
 * Thứ tự theo cách dạy trong tài liệu QIPEDC: xem mẫu → hiểu nghĩa → bắt chước.
 * Video mẫu mở ở trang chính thức của Bộ GD&ĐT (chưa nhúng — chờ văn bản cho
 * phép); ba miền là ba biến thể ngang nhau, không miền nào là "chuẩn".
 *
 * Hai nút nhỏ ở cuối nối sang phần dữ liệu — "Thử ký với camera" và "Đóng góp
 * mẫu" — chứ không kéo cả bộ công cụ thu thập vào đây.
 */

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import Badge from "../../components/ui/Badge";
import { ArrowLeftIcon, HandIcon, PlayCircleIcon, UploadIcon } from "../../components/ui/Icons";
import { useI18n } from "../../i18n";
import { fetchSign, type SignDetail } from "../../api/learn";

export default function SignPage() {
  const { t } = useI18n();
  const { slug = "" } = useParams<{ slug: string }>();
  const [sign, setSign] = useState<SignDetail | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setSign(null);
    fetchSign(slug)
      .then((s) => {
        if (!cancelled) setSign(s);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const status = (err as { response?: { status?: number } })?.response?.status;
        setError(status === 404
          ? t("Không có ký hiệu này trong danh mục.")
          : t("Không tải được. Kiểm tra mạng rồi thử lại."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [slug, t]);

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
      <Link to="/learn" className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-ctu-blue">
        <ArrowLeftIcon className="h-4 w-4" aria-hidden="true" />
        {t("Tất cả ký hiệu")}
      </Link>

      {loading && <p className="text-slate-500">{t("Đang tải…")}</p>}
      {!loading && error && (
        <div role="alert" className="rounded-xl border border-slate-200 bg-slate-50 p-5 text-slate-700">{error}</div>
      )}

      {sign && (
        <>
          <header>
            <h1 className="text-3xl font-bold text-slate-900">{sign.word}</h1>
            <p className="mt-1 text-sm text-slate-500">
              {sign.pos || t("ký hiệu")}
              {sign.own_sample_count > 0 && (
                <>
                  {" · "}
                  <Badge variant="success" size="sm">{t("hệ thống nhận dạng được")}</Badge>
                </>
              )}
            </p>
          </header>

          {/* 1. Xem mẫu — mỗi miền một nút, mở trang chính thức. */}
          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-base font-semibold text-slate-900">{t("Xem cách ký")}</h2>
            <p className="mt-1 text-sm text-slate-600">
              {sign.variants.length > 1
                ? t("Ký hiệu này có cách thể hiện khác nhau theo miền. Cả ba đều đúng — hãy xem miền của bạn.")
                : t("Video mẫu do người Điếc thể hiện, mở tại trang của Bộ Giáo dục và Đào tạo.")}
            </p>
            <ul className="mt-3 flex flex-wrap gap-2">
              {sign.variants.map((v) => (
                <li key={v.code}>
                  <a
                    href={v.video_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 rounded-lg bg-ctu-blue px-4 py-2.5 text-sm font-semibold text-white hover:bg-ctu-navy focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue focus-visible:ring-offset-2"
                  >
                    <PlayCircleIcon className="h-5 w-5" aria-hidden="true" />
                    {sign.variants.length > 1 ? t("Xem video — {mien}", { mien: v.region_name }) : t("Xem video mẫu")}
                  </a>
                </li>
              ))}
            </ul>
          </section>

          {/* 2. Nghĩa — có thì hiện, không thì nói không, không để trống. */}
          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-base font-semibold text-slate-900">{t("Nghĩa của từ")}</h2>
            <p className="mt-1 text-base leading-relaxed text-slate-700">
              {sign.definition || t("Danh mục chưa có phần giải nghĩa cho từ này.")}
            </p>
          </section>

          {/* 3. Thực hành & đóng góp — hai nút nhỏ, không phải một bộ công cụ. */}
          <section className="rounded-xl border border-slate-200 bg-slate-50 p-5">
            <h2 className="text-base font-semibold text-slate-900">{t("Tự thử")}</h2>
            <p className="mt-1 text-sm text-slate-600">
              {sign.own_sample_count > 0
                ? t("Hệ thống đã học ký hiệu này từ {n} mẫu. Bật camera và làm theo video — máy chỉ gợi ý, không chấm điểm.", { n: sign.own_sample_count })
                : t("Hệ thống chưa có mẫu cho ký hiệu này nên chưa nhận dạng được. Bạn có thể là người đóng góp mẫu đầu tiên.")}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {sign.own_sample_count > 0 && (
                <Link
                  to="/realtime"
                  className="inline-flex items-center gap-2 rounded-lg border border-ctu-blue bg-white px-4 py-2 text-sm font-semibold text-ctu-blue hover:bg-ctu-blue/5"
                >
                  <HandIcon className="h-4 w-4" aria-hidden="true" />
                  {t("Thử ký với camera")}
                </Link>
              )}
              <Link
                to="/upload"
                className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                <UploadIcon className="h-4 w-4" aria-hidden="true" />
                {t("Đóng góp mẫu cho ký hiệu này")}
              </Link>
            </div>
          </section>

          <p className="text-xs leading-relaxed text-slate-500">{sign.attribution}</p>
        </>
      )}
    </div>
  );
}
