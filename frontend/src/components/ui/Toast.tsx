import { useEffect, useState } from "react";

export interface ToastProps {
  id?: string;
  message: string;
  type?: "success" | "error" | "warning" | "info";
  duration?: number;
  onClose?: () => void;
}

export default function Toast({ message, type = "info", duration = 4000, onClose }: ToastProps) {
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(false);
      setTimeout(() => onClose?.(), 300);
    }, duration);

    return () => clearTimeout(timer);
  }, [duration, onClose]);

  const typeStyles = {
    success: "border-green-200 bg-green-50 text-green-700",
    error: "border-red-200 bg-red-50 text-red-700", 
    warning: "border-yellow-200 bg-yellow-50 text-yellow-700",
    info: "border-blue-200 bg-blue-50 text-blue-700"
  };

  const icons = {
    success: "✓",
    error: "✕", 
    warning: "⚠",
    info: "ⓘ"
  };

  return (
    <div className={`
      ${isVisible ? "animate-fade-in" : "opacity-0 translate-x-full"}
      transition-all duration-300 ease-out
      flex items-center gap-3 p-4 rounded-lg border backdrop-blur-sm
      ${typeStyles[type]}
      max-w-sm shadow-lg
    `}>
      <div className="text-lg">{icons[type]}</div>
      <div className="flex-1 text-sm font-medium">{message}</div>
      <button
        onClick={() => {
          setIsVisible(false);
          setTimeout(() => onClose?.(), 300);
        }}
        className="text-current opacity-60 hover:opacity-100 transition-opacity"
      >
        ✕
      </button>
    </div>
  );
}