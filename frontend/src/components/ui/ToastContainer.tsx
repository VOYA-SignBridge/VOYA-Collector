import { useToast } from "../../hooks/useToast";
import Toast from "./Toast";

export default function ToastContainer() {
  const { toasts, removeToast } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed bottom-4 right-4 z-[9999] flex flex-col-reverse gap-2 pointer-events-none"
      aria-live="polite"
      aria-label="Notifications"
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
