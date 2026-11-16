import { useI18n } from "../../i18n";
import MyDataDownloadsPanel from "../MyDataDownloadsPanel";

/**
 * Dữ liệu của tôi — `/settings/data`.
 *
 * Quyền của chủ dữ liệu: tải về những gì chính mình đã đóng góp. Trước đây nằm làm
 * một tab trong trang Đóng góp dữ liệu, lẫn với việc thu; nhưng đây là việc của
 * "tài khoản của tôi", làm thỉnh thoảng, nên ở Cài đặt cùng chỗ với Đồng thuận.
 */
export default function MyDataPage() {
  const { t } = useI18n();
  return (
    <section className="space-y-6">
      <header>
        <h2 className="text-xl font-semibold text-slate-900">{t("Dữ liệu của tôi")}</h2>
        <p className="mt-1 text-sm text-slate-600">
          {t("Tải về những mẫu bạn đã đóng góp: bảng thông tin và các tệp dữ liệu.")}
        </p>
      </header>
      <MyDataDownloadsPanel />
    </section>
  );
}
