import { useState, Suspense, lazy, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import UploadVideoForm from "../components/UploadVideoForm";
import ErrorBanner from "../components/ErrorBanner";
import PageHeader from "../components/ui/PageHeader";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import LoadingScreen from "../components/LoadingScreen";
import { useAuth } from "../hooks/useAuth";
import { LightbulbIcon, TagIcon } from "../components/ui/Icons";
import { useI18n } from "../i18n";
const CaptureCamera = lazy(() => import("../components/CaptureCamera"));

type Feedback = {
  type: 'error' | 'warning' | 'info' | 'success';
  message: string;
};

export default function UploadPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { loading: authLoading, isAuthenticated } = useAuth();
  const [tab, setTab] = useState<"video" | "camera">("camera");
  // Start with camera for faster data collection
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [quickLabels] = useState([
    "walking", "running", "sitting", "standing", 
    "jumping", "waving", "pointing", "clapping"
  ]);
  // Feature flag to hide quick label suggestions temporarily
  const SHOW_QUICK_LABELS = false;

  useEffect(() => {
    if (!feedback) return;
    if (feedback.type !== 'success' && feedback.type !== 'info') return;
    const timer = window.setTimeout(() => setFeedback(null), 2500);
    return () => window.clearTimeout(timer);
  }, [feedback]);

  // Show loading while auth is fetching
  if (authLoading) {
    return <LoadingScreen />;
  }

  return (
    <div className="space-y-6">
      <PageHeader 
        title={t("Trung tâm Thu thập Dữ liệu")}
        subtitle={t("Quy trình gọn nhẹ để tạo bộ dữ liệu hiệu quả")}
      />

      {error && (
        <ErrorBanner 
          message={error} 
          onClose={() => setError(null)} 
          type="error"
          autoClose={false}
        />
      )}

      {feedback && !error && (
        <ErrorBanner
          message={feedback.message}
          onClose={() => setFeedback(null)}
          type={feedback.type}
          autoClose={feedback.type === 'success' || feedback.type === 'info'}
          duration={2500}
        />
      )}

      {/* Method Selection with Quick Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div
          className={`card card-compact cursor-pointer transition-all duration-200 ${
            tab === "camera"
              ? "ring-2 ring-ctu-blue bg-ctu-blue/5"
              : "hover:shadow-md"
          }`}
          onClick={() => setTab("camera")}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <div className="w-10 h-10 sm:w-12 sm:h-12 bg-ctu-blue/10 rounded-xl flex items-center justify-center mr-3 sm:mr-4 shrink-0">
                <svg className="w-5 h-5 sm:w-6 sm:h-6 text-ctu-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </div>
              <div>
                <h3 className="text-base sm:text-lg font-semibold text-gray-900">{t("Ghi hình trực tiếp")}</h3>
                <p className="text-gray-600 text-xs sm:text-sm leading-relaxed">{t("Thu thập nhanh theo lô với phản hồi tức thì")}</p>
              </div>
            </div>
            {tab === "camera" && (
              <div className="text-ctu-blue">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
            )}
          </div>
        </div>

        <div
          className={`card card-compact cursor-pointer transition-all duration-200 ${
            tab === "video"
              ? "ring-2 ring-ctu-navy bg-ctu-navy/5"
              : "hover:shadow-md"
          }`}
          onClick={() => setTab("video")}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <div className="w-10 h-10 sm:w-12 sm:h-12 bg-ctu-navy/10 rounded-xl flex items-center justify-center mr-3 sm:mr-4 shrink-0">
                <svg className="w-5 h-5 sm:w-6 sm:h-6 text-ctu-navy" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <div>
                <h3 className="text-base sm:text-lg font-semibold text-gray-900">{t("Tải video lên")}</h3>
                <p className="text-gray-600 text-xs sm:text-sm leading-relaxed">{t("Xử lý các tệp video có sẵn")}</p>
              </div>
            </div>
            {tab === "video" && (
              <div className="text-ctu-navy">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Quick Label Suggestions (hidden by flag) */}
      {SHOW_QUICK_LABELS && tab === "camera" && (
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h3 className="flex items-center gap-1.5 text-sm font-medium text-gray-700">
                <TagIcon className="h-4 w-4"  aria-hidden="true" />
                {t("Gợi ý nhãn nhanh")}
              </h3>
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <span>{t("Được dùng nhiều hôm nay:")}</span>
              <Badge variant="info" size="sm">{t("xin chào (12)")}</Badge>
              <Badge variant="success" size="sm">{t("cảm ơn (8)")}</Badge>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {quickLabels.map((label) => (
              <button
                key={label}
                className="px-3 py-1 text-sm bg-gray-100 hover:bg-blue-100 text-gray-700 hover:text-blue-700 rounded-full transition-colors relative group"
                onClick={() => {
                  // This will be handled by the CaptureCamera component
                  const event = new CustomEvent('quickLabel', { detail: label });
                  window.dispatchEvent(event);
                }}
              >
                {label}
                <span className="absolute -top-1 -right-1 w-4 h-4 bg-blue-500 text-white text-xs rounded-full opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                  +
                </span>
              </button>
            ))}
          </div>
          <div className="mt-2 text-xs text-gray-500">
            <LightbulbIcon className="inline h-3.5 w-3.5 mr-1 -mt-0.5"  aria-hidden="true" />
            {t("Nhấp để tự động điền nhãn giúp thu dữ liệu nhanh hơn")}
          </div>
        </div>
      )}

      {/* Content Area */}
      {!isAuthenticated && (
        <div className="card p-6 text-center">
          <h2 className="text-xl font-semibold mb-4">{t("Cần đăng nhập để tải lên")}</h2>
          <p className="text-gray-600 mb-6">
            {t("Vui lòng đăng nhập bằng tài khoản của bạn để bắt đầu gửi dữ liệu ký hiệu tay.")}
          </p>
          <Button
            variant="primary"
            onClick={() => navigate('/login')}
          >
            {t("Đăng nhập")}
          </Button>
        </div>
      )}

      {isAuthenticated && (
        <>
          {tab === "video" && <UploadVideoForm onError={(m) => setError(m)} />}
          {tab === "camera" && (
            <Suspense fallback={
              <div className="card">
                <div className="flex items-center justify-center py-12">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                  <span className="ml-3 text-gray-600">{t("Đang tải giao diện camera...")}</span>
                </div>
              </div>
            }>
              <CaptureCamera
                onError={(m: string) => setError(m)}
                onSuccess={(m: string) => setFeedback({ type: 'success', message: m })}
              />
            </Suspense>
          )}
        </>
      )}
    </div>
  );
}
