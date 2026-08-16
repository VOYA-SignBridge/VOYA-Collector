import { VideoIcon } from "./ui/Icons";

export default function CaptureGuide({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-3 sm:p-4">
      <div className="bg-white rounded-lg p-4 sm:p-6 w-full max-w-[calc(100vw-1.5rem)] sm:max-w-[600px] shadow-lg max-h-[90dvh] overflow-y-auto">
        <h2 className="mb-4 flex items-center gap-2 text-2xl font-bold"><VideoIcon className="h-6 w-6 text-ctu-blue" /> Hướng dẫn ghi hình</h2>
        
        <ul className="list-disc ml-5 space-y-2 text-gray-700">
          <li>Đặt camera ngang tầm mắt, giữ khoảng cách ~1m.</li>
          <li>Tay luôn nằm trong khung hình.</li>
          <li>Quay trong môi trường đủ sáng, nền đơn giản.</li>
          <li>Mỗi mẫu kéo dài ít nhất <b>3–5 giây</b>.</li>
          <li>Thực hiện động tác chậm rãi, rõ ràng.</li>
          <li>Chọn đúng nhãn (label) trước khi bắt đầu quay.</li>
          <li>Quay nhiều lần với góc và tốc độ khác nhau.</li>
        </ul>

        <button
          className="mt-6 w-full sm:w-auto px-4 py-2 bg-blue-600 text-white rounded"
          onClick={onClose}
        >
          Tôi đã hiểu
        </button>
      </div>
    </div>
  );
}
