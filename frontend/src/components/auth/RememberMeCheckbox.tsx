import { useState } from "react";
import { createPortal } from "react-dom";
import { useI18n } from "../../i18n";
import Button from "../ui/Button";
import Modal from "../ui/Modal";

/**
 * "Ghi nhớ đăng nhập trên thiết bị này".
 *
 * Tắt mặc định, và bật thì phải xác nhận: máy ở trường, quán net hay máy mượn
 * là chuyện thường của người dùng ở đây, và giữ đăng nhập nhiều ngày trên một
 * máy dùng chung là đưa tài khoản cho người dùng máy sau. Tắt thì không hỏi gì.
 */
export default function RememberMeCheckbox({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
}) {
  const { t } = useI18n();
  const [asking, setAsking] = useState(false);

  return (
    <>
      <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => (e.target.checked ? setAsking(true) : onChange(false))}
          className="h-4 w-4 rounded border-slate-300 accent-ctu-blue"
        />
        {t("Ghi nhớ đăng nhập trên thiết bị này")}
      </label>

      {/* Cổng ra `document.body`: ô này nằm TRONG `<form>` đăng nhập, mà `Button`
          và nút đóng của `Modal` không đặt `type`, nên nằm trong form thì mỗi cú bấm
          "Đây là thiết bị của tôi" sẽ gửi luôn biểu mẫu. */}
      {createPortal(
        <Modal
          isOpen={asking}
          onClose={() => setAsking(false)}
          title={t("Ghi nhớ đăng nhập?")}
          size="sm"
        >
          <p className="text-sm text-slate-600">
            {t("Bạn sẽ không phải đăng nhập lại trong một thời gian dài. Chỉ chọn trên thiết bị của riêng bạn, đừng chọn trên máy dùng chung ở trường hay quán net.")}
          </p>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setAsking(false)}>
              {t("Không ghi nhớ")}
            </Button>
            <Button
              variant="primary"
              onClick={() => {
                onChange(true);
                setAsking(false);
              }}
            >
              {t("Đây là thiết bị của tôi")}
            </Button>
          </div>
        </Modal>,
        document.body,
      )}
    </>
  );
}
