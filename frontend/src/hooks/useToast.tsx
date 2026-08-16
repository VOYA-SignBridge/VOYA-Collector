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

  const { addToast } = ctx;

  // Giữ nguyên identity giữa các lần render. Trước đây object này được tạo mới
  // mỗi render, nên component nào gọi toast bên trong useCallback/useEffect
  // buộc phải bỏ nó khỏi dependency array (sai) hoặc chịu callback tái tạo liên
  // tục. addToast đã là useCallback ổn định nên memo theo nó là đủ.
  const toast = useMemo(
    () => ({
      success: (message: string) => addToast(message, "success"),
      error: (message: string) => addToast(message, "error"),
      warning: (message: string) => addToast(message, "warning"),
      info: (message: string) => addToast(message, "info"),
    }),
    [addToast]
  );

  return {
    toasts: ctx.toasts,
    removeToast: ctx.removeToast,
    toast,
  };
}
