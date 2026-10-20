import { CameraIcon } from "./ui/Icons";
import { useI18n } from "../i18n";

export default function CaptureGuide({ onClose }: { onClose: () => void }) {
  const { t } = useI18n();
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-3 sm:p-4">
      <div className="bg-white rounded-lg p-4 sm:p-6 w-full max-w-[calc(100vw-1.5rem)] sm:max-w-[600px] shadow-lg max-h-[90dvh] overflow-y-auto">
        <h2 className="flex items-center gap-2 text-2xl font-bold mb-4">
          <CameraIcon className="w-6 h-6 text-ctu-blue" aria-hidden="true" />
          {t("Hướng dẫn ghi hình")}
        </h2>
        
        <ul className="list-disc ml-5 space-y-2 text-gray-700">
          <li>{t("Đặt camera ngang tầm mắt, giữ khoảng cách ~1m.")}</li>
          <li>{t("Tay luôn nằm trong khung hình.")}</li>
          <li>{t("Quay trong môi trường đủ sáng, nền đơn giản.")}</li>
          <li>{t("Mỗi mẫu kéo dài ít nhất")} <b>{t("3–5 giây")}</b>.</li>
          <li>{t("Thực hiện động tác chậm rãi, rõ ràng.")}</li>
          <li>{t("Chọn đúng nhãn (label) trước khi bắt đầu quay.")}</li>
          <li>{t("Quay nhiều lần với góc và tốc độ khác nhau.")}</li>
        </ul>

        <button
          className="mt-6 w-full sm:w-auto px-4 py-2 bg-blue-600 text-white rounded"
          onClick={onClose}
        >
          {t("Tôi đã hiểu")}
        </button>
      </div>
    </div>
  );
}
