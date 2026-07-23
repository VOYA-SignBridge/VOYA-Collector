import { useCallback, useEffect, useMemo, useState } from "react";
import type { Sample as SampleT, SessionStats, MediaPipeLandmark, QualityInfo, CameraInfo, CameraUploadPayload } from "../types";
import { uploadCamera } from "../api/upload";
import { qcMessage } from "../utils/qualityMessages";
import CaptureGuide from "./CaptureGuide";
import SessionPanel from "./SessionPanel";
import SessionSummary from "./SessionSumary";
import FullscreenCaptureModal from "./FullscreenCaptureModal";
import Button from "./ui/Button";
import { TARGET_FRAMES, CAPTURE_COUNT } from "../config/capture";
import { createSessionId, NEW_SESSION_EVENT } from "../utils/session";
import { me } from "../api/auth";

type Props = {
  onError?: (msg: string) => void;
  onSuccess?: (msg: string) => void;
};

export default function CaptureCamera({ onError, onSuccess }: Props) {
  // Removed frames state - now using only fullscreen capture
  const [label, setLabel] = useState("");
  const [user, setUser] = useState("");
  const [showGuide, setShowGuide] = useState(false);
  // Removed preview state - using fullscreen capture only
  const [showFullscreen, setShowFullscreen] = useState(false);
  
  const targetFrames = TARGET_FRAMES;
  // Số lượt thu mỗi lần bấm ghi. CAPTURE_COUNT chỉ còn là giá trị mặc định —
  // người thu chỉnh được vì các lượt trong cùng một đợt là mẫu gần trùng nhau,
  // nên nhiều lượt không đồng nghĩa nhiều dữ liệu độc lập hơn.
  const [captureCount, setCaptureCount] = useState<number>(CAPTURE_COUNT);

  const [sessionId, setSessionId] = useState(createSessionId);
  const [sessionStats, setSessionStats] = useState<SessionStats | null>(null);
  const [samples, setSamples] = useState<SampleT[]>([]);
  const [sampleCounter, setSampleCounter] = useState(1);
  const [connectionIssue, setConnectionIssue] = useState<string | null>(null);
  // Thông báo QC hiển thị TRONG modal fullscreen (toast global bị element-fullscreen che).
  // `key` tăng dần để modal re-trigger auto-dismiss cho từng thông báo mới.
  const [qualityNotice, setQualityNotice] = useState<{ kind: "warning" | "error"; message: string; key: number } | null>(null);

  // Số mẫu đã thu thành công theo từng từ, dùng để hiển thị danh sách trong
  // giao diện toàn màn hình (chỉ tính mẫu đã xử lý và lưu lên server).
  const capturedSummary = useMemo(() => {
    return samples.reduce((acc: Record<string, number>, s) => {
      const lbl = s.label || "unknown";
      acc[lbl] = (acc[lbl] || 0) + 1;
      return acc;
    }, {});
  }, [samples]);

  // Bắt đầu một phiên thu mới: cấp session_id mới và xoá tổng kết của phiên cũ.
  // KHÔNG reload trang — mẫu đã thu đều đã lưu lên server, nên reload chỉ làm
  // mất ngữ cảnh nhập liệu mà không đem lại gì, và người dùng không nhận ra
  // được là có chuyện gì vừa xảy ra.
  const handleNewSession = useCallback(() => {
    setSessionId(createSessionId());
    setSamples([]);
    setSampleCounter(1);
    setSessionStats(null);
  }, []);

  // Nút "Phiên mới" ở thanh điều hướng phát sự kiện toàn cục; chỉ nơi đang thu
  // mới biết cách reset đúng.
  useEffect(() => {
    const onRequest = () => handleNewSession();
    window.addEventListener(NEW_SESSION_EVENT, onRequest);
    return () => window.removeEventListener(NEW_SESSION_EVENT, onRequest);
  }, [handleNewSession]);

  // Mất kết nối mạng ở cấp trình duyệt cũng được coi là sự cố — chặn thu tiếp
  // để tránh mất dữ liệu đã ghi.
  useEffect(() => {
    const handleOffline = () => setConnectionIssue("Mất kết nối mạng.");
    const handleOnline = () => setConnectionIssue(null);
    window.addEventListener("offline", handleOffline);
    window.addEventListener("online", handleOnline);
    return () => {
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener("online", handleOnline);
    };
  }, []);

  // Giữ đồng bộ với FullscreenCaptureModal: viết hoa chữ cái đầu mỗi từ
  // (locale vi) để tên người thu nhất quán, tránh biến thể signer trùng người.
  const sanitizeCollectorName = (value: string) =>
    value
      .replace(/[^\p{L}\s]/gu, " ")
      .replace(/\s+/g, " ")
      .split(" ")
      .map((w) => (w ? w.charAt(0).toLocaleUpperCase("vi") + w.slice(1) : w))
      .join(" ")
      .trim();

  useEffect(() => {
    let active = true;

    me()
      .then((currentUser) => {
        if (!active) return;
        const candidate = sanitizeCollectorName(currentUser.username || "");
        if (candidate) {
          setUser(candidate);
        }
      })
      .catch(() => {
        // Keep manual entry available when auth lookup fails.
      });

    return () => {
      active = false;
    };
  }, []);

  // Toggle to temporarily hide advanced/session UI without deleting it
  const SHOW_ADVANCED = false;

  const handleFinish = () => {
    const totalSamples = samples.length;
    const totalFrames = samples.reduce((sum, s) => sum + (s.frames ?? 0), 0);
    const avgFrames = totalSamples > 0 ? totalFrames / totalSamples : 0;

    const labelsCount: Record<string, number> = {};
    samples.forEach((s) => {
      const lbl = s.label ?? 'unknown';
      labelsCount[lbl] = (labelsCount[lbl] || 0) + 1;
    });

    const stats: SessionStats = {
      totalSamples,
      totalFrames,
      avgFrames: Math.round(avgFrames),
      labelsCount,
    };

    setSessionStats(stats);
  };

    

  // Removed handleUpload - now using only fullscreen capture

  const handleDelete = (sampleId: number) => {
    setSamples(prev => prev.filter(s => s.id !== sampleId));
  };

  const handleFullscreenCapture = async (capturedFrames: Array<{
    left_hand: MediaPipeLandmark[];
    right_hand: MediaPipeLandmark[];
  }>, capturedLabel: string, capturedUser: string, meta?: { camera_info?: CameraInfo; quality_info?: QualityInfo; dialect?: string; language?: string; hands_used?: number | null }) => {
    console.log(`Parent received capture: ${capturedLabel} with ${capturedFrames.length} frames`);

    // Don't set uploading state to avoid blocking the modal
    try {
      // Prepare data for backend API
      const payload: CameraUploadPayload = {
        user: capturedUser,
        label: capturedLabel,
        session_id: sessionId,
        frames: capturedFrames.map((frame, idx) => ({
          timestamp: idx,
          landmarks: frame
        }))
      };
      if (meta?.dialect) payload.dialect = meta.dialect;
      if (meta?.language) payload.language = meta.language;
      if (meta?.hands_used === 1 || meta?.hands_used === 2) payload.hands_required = meta.hands_used;
      if (meta?.quality_info) payload.quality_info = meta.quality_info;

      console.log('Uploading payload to backend...');
      // Call real API in background
      uploadCamera(payload).then((result) => {
        // HTTP 200 nhưng success=false (payload lỗi) trước đây bị coi là
        // thành công — giờ xử lý như thất bại.
        if (result.ok && result.data.success !== false) {
          const sample: SampleT = {
            id: sampleCounter,
            session_id: sessionId,
            label: capturedLabel,
            user: capturedUser,
            frames: capturedFrames.length,
            uploaded: true,
            sample_id: result.data.id?.toString(),
          };
          if (meta?.dialect) sample.dialect = meta.dialect;

          setSamples(prev => [...prev, sample]);
          setSampleCounter(prev => prev + 1);
          setConnectionIssue(null);

          const warning = result.data.quality?.warnings?.[0];
          if (warning) {
            // Mẫu được lưu nhưng bị đánh dấu — cảnh báo không chặn phiên quay.
            const message = qcMessage(warning.code, warning.detail);
            setQualityNotice(prev => ({ kind: "warning", message, key: (prev?.key ?? 0) + 1 }));
          } else {
            onSuccess?.(`Đã tải lên mẫu "${capturedLabel}" thành công.`);
          }

          console.log(`Sample "${capturedLabel}" (${capturedFrames.length} frames) uploaded successfully! Total samples: ${samples.length + 1}`);
        } else if (!result.ok && result.errorCode) {
          // QC reject (422): lỗi dữ liệu chứ không phải lỗi mạng — hiện toast
          // đỏ trong modal, KHÔNG set connectionIssue (sẽ đóng băng phiên quay).
          console.error('Upload rejected by QC:', result.errorCode, result.error);
          const message = qcMessage(result.errorCode);
          setQualityNotice(prev => ({ kind: "error", message, key: (prev?.key ?? 0) + 1 }));
        } else {
          const errorMsg = result.ok ? (result.data.message || 'Không thể lưu mẫu lên máy chủ.') : result.error;
          console.error('Upload failed:', errorMsg);
          setConnectionIssue(errorMsg || 'Không thể lưu mẫu lên máy chủ.');
          if (onError) {
            onError(errorMsg || 'Upload failed. Please try again.');
          }
        }
      }).catch((error) => {
        console.error('Upload failed:', error);
        setConnectionIssue('Không thể lưu mẫu lên máy chủ. Vui lòng kiểm tra kết nối.');
        if (onError) {
          onError('Upload failed. Please try again.');
        }
      });
      
    } catch (error) {
      console.error('Upload preparation failed:', error);
      if (onError) {
        onError('Upload failed. Please try again.');
      }
    }
    
    // Don't close fullscreen modal here - let the modal manage its own lifecycle
    console.log('Capture processed, modal should continue if more captures needed');
  };


  return (
    <div className="space-y-6 sm:space-y-8">
      {/* Quick Start Section */}
      <div className="card card-compact">
        <div className="text-center py-8 sm:py-10">
          <div className="w-20 h-20 sm:w-24 sm:h-24 bg-gradient-to-br from-ctu-blue to-ctu-navy rounded-3xl flex items-center justify-center mx-auto mb-5 sm:mb-6 shadow-xl">
            <svg className="w-10 h-10 sm:w-12 sm:h-12 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </div>
          
          <h2 className="text-xl sm:text-2xl font-bold text-gray-900 mb-3">Ghi chuyển động chuyên nghiệp</h2>
          <p className="text-sm sm:text-base text-gray-600 mb-6 sm:mb-8 max-w-2xl mx-auto leading-relaxed">
            Mở giao diện chụp toàn màn hình để thu dữ liệu tư thế không bị phân tâm. Tối ưu cho tốc độ và độ chính xác.
          </p>

          <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center items-stretch sm:items-center mb-5 sm:mb-6">
            <Button
              onClick={() => setShowFullscreen(true)}
              className="w-full sm:w-auto px-5 sm:px-8 py-3.5 sm:py-4 text-base sm:text-lg font-semibold"
              variant="primary"
            >
              <svg className="w-6 h-6 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
              </svg>
              Mở chế độ Toàn màn hình
            </Button>
            
            <Button
              onClick={() => setShowGuide(true)}
              variant="secondary"
              className="w-full sm:w-auto px-5 sm:px-6 py-3.5 sm:py-4"
            >
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Xem hướng dẫn
            </Button>
          </div>
        </div>
      </div>

      {/* Productivity Panel (hidden by feature flag during public/simple mode) */}
      {SHOW_ADVANCED && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Tiến trình thu thập</h3>
            <div className="flex items-center space-x-2">
                <button
                  onClick={() => {
                    // Auto-fill next sample
                    setSampleCounter(prev => prev + 1);
                    setLabel("");
                  }}
                  className="btn btn-ghost text-sm"
                >
                Mẫu tiếp theo
                </button>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-3 bg-ctu-blue/10 rounded-lg">
              <div className="text-2xl font-bold text-ctu-blue">{samples.length}</div>
              <div className="text-xs text-ctu-blue">Số mẫu hôm nay</div>
            </div>
            <div className="text-center p-3 bg-ctu-navy/10 rounded-lg">
              <div className="text-2xl font-bold text-ctu-navy">
                {samples.length > 0 ? Math.round((samples.length / 60) * 100) / 100 : 0}
              </div>
              <div className="text-xs text-ctu-navy">Mẫu/phút</div>
            </div>
            <div className="text-center p-3 bg-ctu-yellow/15 rounded-lg">
              <div className="text-2xl font-bold text-ctu-navy">
                {samples.reduce((sum, s) => sum + (s.frames || 0), 0)}
              </div>
              <div className="text-xs text-ctu-navy">Tổng khung hình</div>
            </div>
            <div className="text-center p-3 bg-ctu-blue/10 rounded-lg">
              <div className="text-2xl font-bold text-ctu-blue">
                {new Set(samples.map(s => s.label)).size}
              </div>
              <div className="text-xs text-ctu-blue">Nhãn khác nhau</div>
            </div>
          </div>

          {/* Quick Actions for Efficiency */}
          <div className="mt-4 pt-4 border-t border-gray-200">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">Hành động nhanh</span>
              <div className="flex space-x-2">
                <button
                  onClick={() => {
                    // Clear all samples
                    if (confirm('Xóa tất cả mẫu trong phiên này?')) {
                      setSamples([]);
                      setSampleCounter(1);
                    }
                  }}
                  className="btn btn-ghost text-xs text-red-600"
                >
                  Xóa phiên
                </button>
                <button
                  onClick={() => {
                    // Duplicate last sample settings
                    const lastSample = samples[samples.length - 1];
                    if (lastSample) {
                      setLabel(lastSample.label || "");
                    }
                  }}
                  className="btn btn-ghost text-xs"
                  disabled={samples.length === 0}
                >
                  Lặp lại mẫu trước
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {SHOW_ADVANCED && (
        <SessionPanel
          sessionId={sessionId}
          samples={samples}
          onFinish={handleFinish}
          onDelete={handleDelete}
        />
      )}

      {/* Fullscreen Modal */}
      {showFullscreen && (
        <FullscreenCaptureModal
          isOpen={showFullscreen}
          onClose={() => setShowFullscreen(false)}
          onSampleCapture={handleFullscreenCapture}
          initialLabel={label}
          initialUser={user}
          targetFrames={targetFrames}
          captureCount={captureCount}
          onCaptureCountChange={setCaptureCount}
          sessionId={sessionId}
          sessionSampleCount={samples.length}
          onNewSession={handleNewSession}
          capturedSummary={capturedSummary}
          connectionIssue={connectionIssue}
          qualityNotice={qualityNotice}
        />
      )}

      {showGuide && <CaptureGuide onClose={() => setShowGuide(false)} />}
      {/* PreviewModal removed - using fullscreen capture only */}
      {sessionStats && (
        <SessionSummary
          sessionId={sessionId}
          stats={sessionStats}
          onClose={() => setSessionStats(null)}
        />
      )}

      {/* Simple collection statistics (always shown for public UI) */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-gray-700">Thống kê thu thập đơn giản</h3>
          <div className="text-xs text-gray-500">Cập nhật trực tiếp</div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-3">
          <div className="p-3 bg-ctu-blue/10 rounded-lg text-center">
            <div className="text-lg font-bold text-ctu-blue">{samples.length}</div>
            <div className="text-xs text-gray-600">Tổng lượt thu</div>
          </div>
          <div className="p-3 bg-ctu-yellow/15 rounded-lg text-center">
            <div className="text-lg font-bold text-ctu-navy">{new Set(samples.map(s => s.label)).size}</div>
            <div className="text-xs text-gray-600">Số từ thu được</div>
          </div>
          <div className="p-3 bg-ctu-navy/10 rounded-lg text-center">
            <div className="text-lg font-bold text-ctu-navy">{samples.reduce((sum, s) => sum + (s.frames || 0), 0)}</div>
            <div className="text-xs text-gray-600">Tổng khung hình</div>
          </div>
        </div>

        <div className="text-sm text-gray-700">
          <div className="font-medium mb-2">Số lần thu theo từ</div>
          {samples.length === 0 ? (
            <div className="text-xs text-gray-500">Chưa có thu nào</div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {Object.entries(samples.reduce((acc: Record<string, number>, s) => {
                const lbl = s.label || 'unknown';
                acc[lbl] = (acc[lbl] || 0) + 1;
                return acc;
              }, {})).map(([labelName, count]) => (
                <div key={labelName} className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded">
                  <div className="text-sm text-gray-800">{labelName}</div>
                  <div className="text-xs text-gray-600">{count}×</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
