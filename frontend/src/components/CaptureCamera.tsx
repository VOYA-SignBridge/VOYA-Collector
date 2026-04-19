import { useState } from "react";
import type { Sample as SampleT, SessionStats, MediaPipeLandmark, QualityInfo, CameraInfo } from "../types";
import { uploadCamera } from "../api/upload";
import CaptureGuide from "./CaptureGuide";
import SessionPanel from "./SessionPanel";
import SessionSummary from "./SessionSumary";
import FullscreenCaptureModal from "./FullscreenCaptureModal";
import Button from "./ui/Button";
import { TARGET_FRAMES, CAPTURE_COUNT } from "../config/capture";

type Props = {
  onError?: (msg: string) => void;
};

export default function CaptureCamera({ onError }: Props) {
  // Removed frames state - now using only fullscreen capture
  const [label, setLabel] = useState("");
  const [user] = useState("user1");
  const [showGuide, setShowGuide] = useState(false);
  // Removed preview state - using fullscreen capture only
  const [showFullscreen, setShowFullscreen] = useState(false);
  
  // Capture settings are fixed for public uploader — sourced from config
  const targetFrames = TARGET_FRAMES;
  const captureCount = CAPTURE_COUNT;

  const [sessionId] = useState(() => Date.now().toString());
  const [sessionStats, setSessionStats] = useState<SessionStats | null>(null);
  const [samples, setSamples] = useState<SampleT[]>([]);
  const [sampleCounter, setSampleCounter] = useState(1);

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
  }>, capturedLabel: string, capturedUser: string, meta?: { camera_info?: CameraInfo; quality_info?: QualityInfo; dialect?: string }) => {
    console.log(`Parent received capture: ${capturedLabel} with ${capturedFrames.length} frames`);
    
    // Don't set uploading state to avoid blocking the modal
    try {
      // Prepare data for backend API
      const payload: {
        user: string;
        label: string;
        session_id: string;
        dialect?: string;
        frames: Array<{ timestamp: number; landmarks: {
          left_hand?: MediaPipeLandmark[];
          right_hand?: MediaPipeLandmark[];
        } }>;
      } = {
        user: capturedUser,
        label: capturedLabel,
        session_id: sessionId,
        frames: capturedFrames.map((frame, idx) => ({
          timestamp: idx,
          landmarks: frame
        }))
      };
      if (meta?.dialect) payload.dialect = meta.dialect;

      console.log('Uploading payload to backend...');
      // Call real API in background
      uploadCamera(payload).then((result) => {
        if (result.ok) {
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
          
          console.log(`Sample "${capturedLabel}" (${capturedFrames.length} frames) uploaded successfully! Total samples: ${samples.length + 1}`);
        } else {
          console.error('Upload failed:', result.error);
          if (onError) {
            onError(result.error || 'Upload failed. Please try again.');
          }
        }
      }).catch((error) => {
        console.error('Upload failed:', error);
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
    <div className="space-y-6">
      {/* Quick Start Section */}
      <div className="card">
        <div className="text-center py-12">
          <div className="w-24 h-24 bg-gradient-to-br from-green-400 to-blue-500 rounded-3xl flex items-center justify-center mx-auto mb-6 shadow-xl">
            <svg className="w-12 h-12 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </div>
          
          <h2 className="text-2xl font-bold text-gray-900 mb-3">Ghi chuyển động chuyên nghiệp</h2>
          <p className="text-gray-600 mb-8 max-w-2xl mx-auto">
            Mở giao diện chụp toàn màn hình để thu dữ liệu tư thế không bị phân tâm. Tối ưu cho tốc độ và độ chính xác.
          </p>

          {/* Capture settings are fixed for public uploader. Edit src/config/capture.ts to change them. */}

          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-6">
            <Button
              onClick={() => setShowFullscreen(true)}
              className="px-8 py-4 text-lg font-semibold min-w-48"
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
              className="px-6 py-4"
            >
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Xem hướng dẫn
            </Button>
          </div>

          {/* Quick Features */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-4xl mx-auto text-sm">
            <div className="flex items-center justify-center p-4 bg-green-50 rounded-xl">
              <svg className="w-5 h-5 text-green-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              <span className="text-green-800 font-medium">Đếm ngược 3 giây</span>
            </div>
            <div className="flex items-center justify-center p-4 bg-blue-50 rounded-xl">
              <svg className="w-5 h-5 text-blue-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-blue-800 font-medium">Phát hiện bàn tay bằng AI</span>
            </div>
            <div className="flex items-center justify-center p-4 bg-purple-50 rounded-xl">
              <svg className="w-5 h-5 text-purple-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 4V2a1 1 0 011-1h4a1 1 0 011 1v2m-6 0h8m-6 0a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V6a2 2 0 00-2-2m-6 0V4" />
              </svg>
              <span className="text-purple-800 font-medium">Hỗ trợ phím tắt</span>
            </div>
          </div>
        </div>
      </div>

      {/* Productivity Panel (hidden by feature flag during public/simple mode) */}
      {SHOW_ADVANCED && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">📈 Tiến trình thu thập</h3>
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
            <div className="text-center p-3 bg-blue-50 rounded-lg">
              <div className="text-2xl font-bold text-blue-600">{samples.length}</div>
              <div className="text-xs text-blue-600">Số mẫu hôm nay</div>
            </div>
            <div className="text-center p-3 bg-green-50 rounded-lg">
              <div className="text-2xl font-bold text-green-600">
                {samples.length > 0 ? Math.round((samples.length / 60) * 100) / 100 : 0}
              </div>
              <div className="text-xs text-green-600">Mẫu/phút</div>
            </div>
            <div className="text-center p-3 bg-purple-50 rounded-lg">
              <div className="text-2xl font-bold text-purple-600">
                {samples.reduce((sum, s) => sum + (s.frames || 0), 0)}
              </div>
              <div className="text-xs text-purple-600">Tổng khung hình</div>
            </div>
            <div className="text-center p-3 bg-yellow-50 rounded-lg">
              <div className="text-2xl font-bold text-yellow-600">
                {new Set(samples.map(s => s.label)).size}
              </div>
              <div className="text-xs text-yellow-600">Nhãn khác nhau</div>
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
          <h3 className="text-sm font-medium text-gray-700">📋 Thống kê thu thập đơn giản</h3>
          <div className="text-xs text-gray-500">Cập nhật trực tiếp</div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-3">
          <div className="p-3 bg-blue-50 rounded-lg text-center">
            <div className="text-lg font-bold text-blue-600">{samples.length}</div>
            <div className="text-xs text-gray-600">Tổng lượt thu</div>
          </div>
          <div className="p-3 bg-yellow-50 rounded-lg text-center">
            <div className="text-lg font-bold text-yellow-600">{new Set(samples.map(s => s.label)).size}</div>
            <div className="text-xs text-gray-600">Số từ thu được</div>
          </div>
          <div className="p-3 bg-green-50 rounded-lg text-center">
            <div className="text-lg font-bold text-green-600">{samples.reduce((sum, s) => sum + (s.frames || 0), 0)}</div>
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
