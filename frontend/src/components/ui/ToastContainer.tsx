import { useToast } from "../../hooks/useToast";
import Toast from "./Toast";
import { useI18n } from "../../i18n";

export default function ToastContainer() {
  const { t } = useI18n();
  const { toasts, removeToast } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed bottom-4 right-4 z-[9999] flex flex-col-reverse gap-2 pointer-events-none"
      aria-live="polite"
      aria-label={t("Thông báo")}
    >
      {toasts.map((item) => (
        <div key={item.id} className="pointer-events-auto">
          <Toast
            message={item.message}
            type={item.type}
            onClose={() => removeToast(item.id)}
          />
        </div>
      ))}
    </div>
  );
}
