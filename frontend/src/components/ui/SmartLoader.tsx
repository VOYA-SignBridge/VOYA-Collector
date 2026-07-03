import React from "react";

export type SmartLoaderState = "hidden" | "processing" | "paused" | "success";

interface SmartLoaderProps {
  state: SmartLoaderState;
  progress?: { current: number; total: number };
}

const MESSAGES = {
  processing: "Đang nhẹ nhàng dọn dẹp dữ liệu, bạn chờ một xíu nhé... 💖",
  paused: "Hệ thống đang nghỉ mệt nạp chút năng lượng, sẽ tiếp tục ngay thôi ☕",
  success: "Xong rồi nè! Mọi thứ đã gọn gàng sạch sẽ ✨",
};

export const SmartLoader: React.FC<SmartLoaderProps> = ({ state, progress }) => {
  if (state === "hidden") return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-white/80 backdrop-blur-sm transition-all duration-500">
      <div className="flex flex-col items-center justify-center p-8 max-w-md w-full bg-white rounded-3xl shadow-2xl border border-pink-100 transform transition-all scale-100 animate-in fade-in zoom-in-95 duration-300">
        
        {/* Animated Icon Area */}
        <div className="relative h-32 w-32 mb-6 flex items-center justify-center">
          {state === "processing" && (
            <>
              <div className="absolute inset-0 bg-pink-100 rounded-full animate-ping opacity-75"></div>
              <div className="relative flex items-center justify-center bg-pink-500 text-white w-20 h-20 rounded-full shadow-lg shadow-pink-200 animate-bounce">
                <svg className="w-10 h-10 animate-spin-slow" fill="none" viewBox="0 0 24 24">
                  <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 22C6.477 22 2 17.523 2 12S6.477 2 12 2s10 4.477 10 10-4.477 10-10 10zm0-18v6l4 2"></path>
                </svg>
              </div>
            </>
          )}

          {state === "paused" && (
            <div className="relative flex items-center justify-center bg-orange-400 text-white w-24 h-24 rounded-full shadow-lg shadow-orange-200 animate-pulse">
              <span className="text-4xl animate-bounce">☕</span>
            </div>
          )}

          {state === "success" && (
            <div className="relative flex items-center justify-center bg-green-500 text-white w-24 h-24 rounded-full shadow-lg shadow-green-200 transform scale-110 transition-transform duration-500">
              <svg className="w-12 h-12 animate-in zoom-in duration-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7" />
              </svg>
            </div>
          )}
        </div>

        {/* Text Area */}
        <h3 className="text-xl font-bold text-gray-800 mb-2 text-center">
          {state === "processing" && "Đang xử lý..."}
          {state === "paused" && "Tạm nghỉ giải lao..."}
          {state === "success" && "Thành công!"}
        </h3>
        <p className="text-gray-600 text-center text-sm md:text-base leading-relaxed px-4">
          {MESSAGES[state as keyof typeof MESSAGES]}
        </p>

        {/* Progress Bar (Optional) */}
        {state !== "success" && progress && progress.total > 0 && (
          <div className="w-full mt-6">
            <div className="flex justify-between text-xs font-semibold text-pink-500 mb-1 px-1">
              <span>Tiến độ</span>
              <span>{Math.round((progress.current / progress.total) * 100)}%</span>
            </div>
            <div className="w-full bg-pink-100 rounded-full h-2.5 overflow-hidden">
              <div 
                className="bg-pink-500 h-2.5 rounded-full transition-all duration-500 ease-out" 
                style={{ width: `${(progress.current / Math.max(progress.total, 1)) * 100}%` }}
              ></div>
            </div>
            <div className="text-center text-xs text-gray-400 mt-2 font-medium">
              {progress.current} / {progress.total} cụm
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
