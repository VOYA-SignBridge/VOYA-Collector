import { useEffect } from "react";
import type { ReactNode } from "react";
import { XIcon } from "./Icons";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
}

export default function Modal({ isOpen, onClose, title, children, size = "md" }: ModalProps) {
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "unset";
    }

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };

    if (isOpen) {
      document.addEventListener("keydown", handleEscape);
    }

    return () => {
      document.body.style.overflow = "unset";
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const sizes = {
    sm: "max-w-md",
    md: "max-w-lg", 
    lg: "max-w-2xl",
    xl: "max-w-4xl"
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4">
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-fade-in"
        onClick={onClose}
      />
      <div className={`relative w-full ${sizes[size]} max-h-[calc(100dvh-1.5rem)] sm:max-h-[calc(100dvh-2rem)] animate-fade-in`}>
        <div className="card overflow-y-auto p-4 sm:p-6 max-h-[calc(100dvh-1.5rem)] sm:max-h-[calc(100dvh-2rem)]">
          {title && (
            <div className="flex items-center justify-between mb-4 sm:mb-6">
              <h2 className="text-xl font-semibold text-gray-900">{title}</h2>
              <button
                onClick={onClose}
                className="btn btn-ghost p-2 rounded-full"
                aria-label="Đóng hộp thoại"
              >
                <XIcon className="h-4 w-4" />
              </button>
            </div>
          )}
          {children}
        </div>
      </div>
    </div>
  );
}