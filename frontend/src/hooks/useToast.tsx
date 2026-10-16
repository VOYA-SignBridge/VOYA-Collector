import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

export type ToastType = "success" | "error" | "warning" | "info";

export interface ToastItem {
  id: string;
  message: string;
  type: ToastType;
}

interface ToastContextValue {
  toasts: ToastItem[];
  addToast: (message: string, type: ToastType) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const addToast = useCallback((message: string, type: ToastType) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    setToasts((prev) => [...prev, { id, message, type }]);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const value = useMemo(
    () => ({ toasts, addToast, removeToast }),
    [toasts, addToast, removeToast]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");

  // `toast` PHẢI ổn định theo `addToast`, không theo `ctx`.
  //
  // Sự cố TEN-02 (13/09/2026): bản trước dựng object `toast` mới ở MỖI render.
  // `ctx` đổi mỗi khi danh sách toast đổi, nên một trang viết
  //
  //     const load = useCallback(async () => { ... toast.error(...) }, [toast]);
  //     useEffect(() => { load(); }, [load]);
  //
  // rơi vào vòng: API lỗi → toast.error → ctx đổi → toast đổi → load đổi →
  // effect chạy lại → API lỗi → … Khi mất kết nối, trang gọi API liên tục và
  // xếp thông báo vô hạn. Có 23 chỗ trên 7 trang đưa `toast` vào deps; sửa ở
  // đây thì cả lớp lỗi hết, không phải đi vá từng chỗ.
  const { addToast } = ctx;
  const toast = useMemo(
    () => ({
      success: (message: string) => addToast(message, "success"),
      error: (message: string) => addToast(message, "error"),
      warning: (message: string) => addToast(message, "warning"),
      info: (message: string) => addToast(message, "info"),
    }),
    [addToast],
  );

  return { toasts: ctx.toasts, removeToast: ctx.removeToast, toast };
}
