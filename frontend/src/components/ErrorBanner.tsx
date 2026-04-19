import { useState, useEffect } from "react";

type Props = {
  message: string;
  onClose?: () => void;
  type?: "error" | "warning" | "info";
  autoClose?: boolean;
  duration?: number;
};

export default function ErrorBanner({ 
  message, 
  onClose, 
  type = "error", 
  autoClose = false, 
  duration = 5000 
}: Props) {
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    if (autoClose) {
      const timer = setTimeout(() => {
        setIsVisible(false);
        setTimeout(() => onClose?.(), 300);
      }, duration);
      return () => clearTimeout(timer);
    }
  }, [autoClose, duration, onClose]);

  const types = {
    error: {
      bg: "bg-red-50",
      border: "border-red-200", 
      text: "text-red-700",
      icon: "❌"
    },
    warning: {
      bg: "bg-yellow-50",
      border: "border-yellow-200",
      text: "text-yellow-700", 
      icon: "⚠️"
    },
    info: {
      bg: "bg-blue-50",
      border: "border-blue-200",
      text: "text-blue-700",
      icon: "ℹ️"
    }
  };

  const config = types[type];

  const handleClose = () => {
    setIsVisible(false);
    setTimeout(() => onClose?.(), 300);
  };

  if (!isVisible) return null;

  return (
    <div className={`
      card mb-6 transition-all duration-300 ease-out animate-fade-in
      ${config.bg} ${config.border} ${config.text}
    `}>
      <div className="flex items-start gap-4">
        <div className="text-xl flex-shrink-0 mt-0.5">{config.icon}</div>
        <div className="flex-1 min-w-0">
          <div className="font-medium text-white text-sm mb-1">
            {type.charAt(0).toUpperCase() + type.slice(1)}
          </div>
          <div className="text-sm leading-relaxed">{message}</div>
        </div>
        {onClose && (
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-white transition-colors p-1 rounded-md hover:bg-white/10"
            aria-label="Close notification"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
