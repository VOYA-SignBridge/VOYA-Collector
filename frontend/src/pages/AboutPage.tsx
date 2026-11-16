import { Link } from "react-router-dom";
import CaptionedVideo from "../components/guide/CaptionedVideo";
import PageHeader from "../components/ui/PageHeader";
import { GraduationCapIcon, HandIcon, UploadIcon } from "../components/ui/Icons";
import { useAuth } from "../contexts/AuthContext";
import { useI18n } from "../i18n";

/**
 * Giới thiệu — trang công khai, không cần đăng nhập.
 *
 * Trả lời ba câu của một người mới tới: đây là gì, tôi làm được gì ở đây, và bắt
 * đầu từ đâu. Khách thấy hai nút cuối trang (Đăng ký, Đăng nhập); người đã đăng
 * nhập không cần chúng nên chúng không hiện.
 */
export default function AboutPage() {
  const { t } = useI18n();
  const { user } = useAuth();

  const cards = [
    {
      to: "/learn",
      icon: <GraduationCapIcon className="h-6 w-6" aria-hidden="true" />,
      title: t("Học ký hiệu"),
      text: t("Xem và học các ký hiệu của Ngôn ngữ Ký hiệu Việt Nam. Không cần tài khoản."),
    },
    {
      to: "/upload",
      icon: <UploadIcon className="h-6 w-6" aria-hidden="true" />,
      title: t("Đóng góp dữ liệu"),
      text: t("Ghi hình một ký hiệu bằng camera, hoặc tải video lên, để máy học nhận dạng."),
    },
    {
      to: "/realtime",
      icon: <HandIcon className="h-6 w-6" aria-hidden="true" />,
      title: t("Nhận dạng realtime"),
      text: t("Thử để máy nhận dạng ký hiệu của bạn ngay trước camera."),
    },
  ];

  return (
    <div className="mx-auto w-full max-w-4xl space-y-10">
      <PageHeader
        title={t("Giới thiệu")}
        subtitle={t("Nền tảng thu thập và nhận dạng Ngôn ngữ Ký hiệu Việt Nam (VSL) sử dụng công nghệ AI, phục vụ nghiên cứu và cộng đồng.")}
      />

      <section aria-labelledby="about-what" className="space-y-3">
        <h2 id="about-what" className="text-xl font-semibold text-slate-900">{t("Dự án làm gì")}</h2>
        <p className="text-slate-700">
          {t("CTU.SignBridge là dự án nghiên cứu của Trường Công nghệ Thông tin và Truyền thông, Đại học Cần Thơ. Dự án xây dựng bộ dữ liệu ký hiệu do chính cộng đồng đóng góp, để huấn luyện máy nhận dạng ngôn ngữ ký hiệu và làm cầu nối giao tiếp giữa người khiếm thính và người nghe.")}
        </p>
      </section>

      <section aria-labelledby="about-do" className="space-y-3">
        <h2 id="about-do" className="text-xl font-semibold text-slate-900">{t("Bạn có thể làm gì")}</h2>
        <ul className="grid gap-4 sm:grid-cols-3">
          {cards.map((c) => (
            <li key={c.to}>
              <Link
                to={c.to}
                className="flex h-full flex-col gap-2 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-ctu-blue hover:shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ctu-blue"
              >
                <span className="flex h-10 w-10 items-center justify-center rounded-full bg-ctu-blue/10 text-ctu-blue">{c.icon}</span>
                <span className="font-semibold text-slate-900">{c.title}</span>
                <span className="text-sm text-slate-600">{c.text}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="about-guide" className="space-y-3">
        <h2 id="about-guide" className="text-xl font-semibold text-slate-900">{t("Hướng dẫn nhanh")}</h2>
        <CaptionedVideo name="huong-dan" />
      </section>

      <section aria-labelledby="about-data" className="space-y-3">
        <h2 id="about-data" className="text-xl font-semibold text-slate-900">{t("Dữ liệu của bạn")}</h2>
        <p className="text-slate-700">
          {t("Mỗi bản ghi mới chờ người kiểm duyệt xem xét. Bạn xem, tải về và rút đồng thuận bất cứ lúc nào ở mục Cài đặt.")}
        </p>
        <p className="text-sm text-slate-600">
          <Link to="/legal/terms" className="font-semibold text-ctu-blue hover:underline">{t("Điều khoản sử dụng")}</Link>
          {" · "}
          <Link to="/legal/privacy" className="font-semibold text-ctu-blue hover:underline">{t("Chính sách quyền riêng tư")}</Link>
          {" · "}
          <Link to="/faq" className="font-semibold text-ctu-blue hover:underline">{t("Hỏi đáp")}</Link>
        </p>
      </section>

      {!user && (
        <section className="flex flex-wrap items-center gap-3 rounded-2xl bg-ctu-blue/5 p-5">
          <p className="mr-auto font-medium text-slate-900">{t("Sẵn sàng bắt đầu?")}</p>
          <Link to="/register" className="rounded-xl bg-ctu-blue px-5 py-2.5 text-sm font-semibold text-white hover:bg-ctu-navy">
            {t("Đăng ký")}
          </Link>
          <Link to="/login" className="rounded-xl border border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50">
            {t("Đăng nhập")}
          </Link>
        </section>
      )}
    </div>
  );
}
