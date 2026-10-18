/**
 * Thẻ một ký hiệu — `/learn/:slug`. CÔNG KHAI.
 *
 * Thứ tự theo cách dạy trong tài liệu QIPEDC: xem mẫu → hiểu nghĩa → bắt chước.
 * Video nhúng thẳng từ máy chủ QIPEDC (chủ dự án chốt 15/09/2026); ba miền là
 * ba biến thể ngang nhau, không miền nào là "chuẩn".
 *
 * Hai nút nhỏ ở cuối nối sang phần dữ liệu — "Thử ký với camera" và "Đóng góp
 * mẫu" — chứ không kéo cả bộ công cụ thu thập vào đây.
 *
 * Nút "Tất cả ký hiệu" mang theo chuỗi truy vấn của trang danh sách (nếu có)
 * để người xem quay về đúng trang, đúng bộ lọc đang xem.
 */

import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import Badge from "../../components/ui/Badge";
import {
  ArrowLeftIcon,
  FilmIcon,
  HandIcon,
  LightbulbIcon,
  PlayCircleIcon,
  UploadIcon,
} from "../../components/ui/Icons";
import { useI18n } from "../../i18n";
import { KIND_LABEL, fetchSign, type SignDetail } from "../../api/learn";

export default function SignPage() {
  const { t } = useI18n();
  const { slug = "" } = useParams<{ slug: string }>();
  const location = useLocation();
  const backTo = `/learn${location.search || ""}`;
  const [sign, setSign] = useState<SignDetail | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  // Miền đang xem khi một ký hiệu có nhiều biến thể; mặc định biến thể đầu.
  const [variantIdx, setVariantIdx] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setSign(null);
    setVariantIdx(0);
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

  const variant = sign ? sign.variants[Math.min(variantIdx, sign.variants.length - 1)] : undefined;
  const regionNames = sign ? sign.variants.filter((v) => v.region !== "khong_ghi").map((v) => v.region_name) : [];

  return (
    <div className="mx-auto max-w-4xl space-y-5 px-4 py-6">
      <Link to={backTo} className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-ctu-blue">
        <ArrowLeftIcon className="h-4 w-4" aria-hidden="true" />
        {t("Tất cả ký hiệu")}
      </Link>

      {loading && (
        <div className="animate-pulse space-y-4" aria-hidden="true">
          <div className="h-9 w-1/3 rounded bg-slate-200" />
          <div className="aspect-video w-full rounded-2xl bg-slate-200" />
          <div className="h-24 rounded-2xl bg-slate-100" />
        </div>
      )}
      {!loading && error && (
        <div role="alert" className="rounded-2xl border border-slate-200 bg-slate-50 p-6 text-slate-700">
          <p className="font-medium">{error}</p>
          <Link to="/learn" className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-ctu-blue hover:underline">
            <ArrowLeftIcon className="h-4 w-4" aria-hidden="true" />
            {t("Về trang tra cứu")}
          </Link>
        </div>
      )}

      {sign && (
        <>
          {/* Đầu thẻ: từ, từ loại, ba miền có sẵn, và "thử được" nếu có. */}
          <header className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">{sign.word}</h1>
                <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-slate-500">
                  <span>{sign.pos || t("ký hiệu")}</span>
                  {sign.kind !== "tu_thuong" && KIND_LABEL[sign.kind] && (
                    <>
                      <span aria-hidden="true">·</span>
                      <span>{t(KIND_LABEL[sign.kind])}</span>
                    </>
                  )}
                  {regionNames.length > 0 && (
                    <>
                      <span aria-hidden="true">·</span>
                      <span>{t("Có video: {r}", { r: regionNames.join(", ") })}</span>
                    </>
                  )}
                </p>
              </div>
              {sign.own_sample_count > 0 && (
                <Badge variant="success">{t("hệ thống nhận dạng được")}</Badge>
              )}
            </div>
          </header>

          {/* 1. Xem mẫu — video nhúng thẳng (máy chủ QIPEDC hỗ trợ tải theo
              đoạn nên tua được). Nhiều miền thì một hàng nút đổi video, không
              mở ba trang. Vẫn giữ liên kết về trang gốc để người xem biết nguồn. */}
          <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
              <div>
                <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
                  <FilmIcon className="h-5 w-5 text-ctu-blue" aria-hidden="true" />
                  {t("Xem cách ký")}
                </h2>
                <p className="mt-0.5 text-sm text-slate-600">
                  {sign.variants.length > 1
                    ? t("Ký hiệu này có cách thể hiện khác nhau theo miền. Cả ba đều đúng — hãy xem miền của bạn.")
                    : t("Video mẫu được trích từ dự án QIPEDC.")}
                </p>
              </div>
              {sign.variants.length > 1 && (
                <div className="flex flex-wrap gap-1 rounded-xl bg-slate-100 p-1" role="tablist" aria-label={t("Chọn miền")}>
                  {sign.variants.map((v, i) => (
                    <button
                      key={v.code}
                      type="button"
                      role="tab"
                      aria-selected={i === variantIdx}
                      onClick={() => setVariantIdx(i)}
                      className={`rounded-lg px-4 py-1.5 text-sm font-semibold transition-colors ${
                        i === variantIdx
                          ? "bg-white text-ctu-blue shadow-sm"
                          : "text-slate-600 hover:text-slate-900"
                      }`}
                    >
                      {v.region_name}
                    </button>
                  ))}
                </div>
              )}
            </div>
            {variant && (
              <div className="bg-slate-950 p-3 sm:p-4">
                <video
                  key={variant.code}
                  controls
                  playsInline
                  preload="metadata"
                  src={variant.video_url}
                  className="mx-auto aspect-video w-full max-w-3xl rounded-lg bg-black"
                  data-testid="sign-video"
                >
                  {t("Trình duyệt không phát được video này.")}
                </video>
              </div>
            )}
            {variant && (
              <div className="flex flex-wrap items-center justify-between gap-2 px-5 py-3 text-xs text-slate-500">
                <span>{t("Mã mục: {code}", { code: variant.code })}</span>
                <a
                  href={variant.video_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 font-medium text-ctu-blue hover:underline"
                >
                  <PlayCircleIcon className="h-4 w-4" aria-hidden="true" />
                  {t("Mở video gốc tại qipedc.moet.gov.vn")}
                </a>
              </div>
            )}
          </section>

          {/* 2. Nghĩa — có thì hiện, không thì nói không, không để trống. */}
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
            <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
              <LightbulbIcon className="h-5 w-5 text-ctu-blue" aria-hidden="true" />
              {t("Nghĩa của từ")}
            </h2>
            <p className={`mt-2 text-base leading-relaxed ${sign.definition ? "text-slate-700" : "text-slate-500"}`}>
              {sign.definition || t("Danh mục chưa có phần giải nghĩa cho từ này.")}
            </p>
          </section>

          {/* 3. Thực hành & đóng góp — hai nút nhỏ, không phải một bộ công cụ. */}
          <section className="rounded-2xl border border-ctu-blue/20 bg-ctu-blue/5 p-5 sm:p-6">
            <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
              <HandIcon className="h-5 w-5 text-ctu-blue" aria-hidden="true" />
              {t("Tự thử")}
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              {sign.own_sample_count > 0
                ? t("Hệ thống đã học ký hiệu này từ {n} mẫu. Bật camera và làm theo video — máy chỉ gợi ý, không chấm điểm.", { n: sign.own_sample_count })
                : t("Hệ thống chưa có mẫu cho ký hiệu này nên chưa nhận dạng được. Bạn có thể là người đóng góp mẫu đầu tiên.")}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {sign.own_sample_count > 0 && (
                <Link
                  to="/realtime"
                  className="inline-flex items-center gap-2 rounded-lg bg-ctu-blue px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-ctu-navy-mid"
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
