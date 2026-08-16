/**
 * Training Pipeline Page - Professional UI/UX Design
 * 7-Step Training Workflow with Real-time Feedback
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useTrainingAPI, useWebSocketProgress } from '../../hooks/useTrainingAPI';
import type { TrainingJob, TrainingConfig, TrainingJobListItem, TrainingMetrics } from '../../hooks/useTrainingAPI';
import TrainingHistory from './components/TrainingHistory';
import PageHeader from '../../components/ui/PageHeader';
import Button from '../../components/ui/Button';
import {
  ChipIcon,
  AlertTriangleIcon,
  ClipboardCheckIcon,
  HistoryIcon,
  DatabaseIcon,
  GearIcon,
  GlobeIcon,
  SparkleIcon,
  SplitIcon,
} from '../../components/ui/Icons';
import DataSplitVisualization from './components/DataSplitVisualization';
import DatasetPreparationPage from './DatasetPreparationPage';
import AugmentationPreview from './components/AugmentationPreview';
import DialectSelector from './components/DialectSelector';
import TrainingSettings from './components/TrainingSettings';
import TrainingProgress from './components/TrainingProgress';
import ResultsInsights from './components/ResultsInsights';
import { useToast } from '../../hooks/useToast';

type Step = 1 | 2 | 3 | 4 | 5 | 6 | 7;

const STEP_ICON_CLASS = 'h-6 w-6 sm:h-7 sm:w-7';

const STEP_LABELS: Record<number, { title: string; icon: ReactNode; description: string }> = {
  1: { title: 'Chọn Phương Ngữ', icon: <GlobeIcon className={STEP_ICON_CLASS} />, description: 'Lựa chọn phương ngữ đưa vào huấn luyện' },
  2: { title: 'Chuẩn Bị Dữ Liệu', icon: <DatabaseIcon className={STEP_ICON_CLASS} />, description: 'Tạo bộ dữ liệu chuẩn từ video đã thu' },
  3: { title: 'Chia Tập', icon: <SplitIcon className={STEP_ICON_CLASS} />, description: 'Xem cách chia của phương ngữ đã chọn' },
  4: { title: 'Tăng Cường', icon: <SparkleIcon className={STEP_ICON_CLASS} />, description: 'Xem trước augmentation' },
  5: { title: 'Cấu Hình', icon: <GearIcon className={STEP_ICON_CLASS} />, description: 'Điều chỉnh hyperparameters' },
  6: { title: 'Huấn Luyện', icon: <ChipIcon className={STEP_ICON_CLASS} />, description: 'Quá trình training' },
  7: { title: 'Kết Quả', icon: <ClipboardCheckIcon className={STEP_ICON_CLASS} />, description: 'Phân tích kết quả' },
};

type View = 'landing' | 'wizard';

const TrainingPipeline: React.FC = () => {
  const [view, setView] = useState<View>('landing');
  const [historyJobs, setHistoryJobs] = useState<TrainingJobListItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState<Step>(1);
  const [job, setJob] = useState<TrainingJob | null>(null);
  const [metrics, setMetrics] = useState<TrainingMetrics[]>([]);
  const [wsError, setWsError] = useState<string | null>(null);
  // Bước 2 báo lên: đã có bộ dữ liệu chuẩn hoá để đi tiếp hay chưa.
  const [datasetReady, setDatasetReady] = useState(false);
  const [selectedDialects, setSelectedDialects] = useState<string[]>([]);
  const [trainingConfig, setTrainingConfig] = useState<TrainingConfig>({
    model_type: 'tcn',
    dialects: [],
    languages: [],
    epochs: 80,
    batch_size: 32,
    learning_rate: 0.001,
    dropout: 0.3,
    channels: 64,
    levels: 3,
    kernel_size: 5,
  });

  const api = useTrainingAPI();
  const { toast } = useToast();
  // `loading` không còn dùng: bước 1 giờ là DialectSelector, không phải
  // DatasetInfo (component duy nhất từng nhận cờ này).
  const { datasetInfo, error, loadDatasetInfo, startTraining, getJobMetrics, listJobs } = api;

  // Bước 3 mô tả phân hoạch của ĐÚNG phương ngữ đang chọn. Backend phân giải
  // split theo tham số `dialect`; nếu không gửi, nó rơi về split gốc và bước
  // chia tập sẽ mô tả một phân hoạch khác với phân hoạch job thực sự đọc.
  useEffect(() => {
    // Nhiều phương ngữ thì không có split triển khai nào phủ hết, backend trả về
    // split gốc — phải hỏi lại không kèm tham số, nếu không màn hình vẫn giữ số
    // liệu của phương ngữ chọn trước đó.
    // Đổi phương ngữ là đổi phạm vi dữ liệu, nên tình trạng chuẩn hoá của
    // phương ngữ trước không còn đúng — hạ cờ và để bước 2 báo lại.
    setDatasetReady(false);
    loadDatasetInfo(selectedDialects.length === 1 ? selectedDialects[0] : undefined);
  }, [selectedDialects, loadDatasetInfo]);

  // Load lịch sử jobs khi ở landing view
  const refreshHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      setHistoryJobs(await listJobs());
    } finally {
      setHistoryLoading(false);
    }
  }, [listJobs]);

  useEffect(() => {
    if (view === 'landing') {
      refreshHistory();
    }
  }, [view, refreshHistory]);

  // Xóa job khỏi lịch sử huấn luyện (chỉ job đã kết thúc)
  const handleDeleteJob = async (item: TrainingJobListItem) => {
    const ok = await api.deleteJob(item.id);
    if (!ok) {
      // Dùng toast chung của app thay vì window.alert — alert của trình duyệt
      // chặn cả trang và trông lạc lõng giữa giao diện.
      toast.error(api.error || 'Không thể xóa phiên huấn luyện này.');
      return;
    }
    toast.success('Đã xóa phiên huấn luyện khỏi lịch sử');
    await refreshHistory();
  };

  // Mở một job từ lịch sử: completed → Kết Quả (7); còn lại → Tiến Độ (6)
  const handleOpenJob = (item: TrainingJobListItem) => {
    setJob(item);
    setMetrics([]);
    setCurrentStep(item.status === 'completed' ? 7 : 6);
    setView('wizard');
  };

  // Bắt đầu run mới: reset toàn bộ state wizard
  const handleNewTraining = () => {
    setJob(null);
    setMetrics([]);
    setDatasetReady(false);
    setSelectedDialects([]);
    setCurrentStep(1);
    setView('wizard');
  };

  // Setup WebSocket to stream training progress.
  // Dedupe theo epoch: server replay toàn bộ lịch sử mỗi khi (re)connect,
  // nên chỉ thêm epoch chưa có — không bao giờ nhân bản card metrics.
  // Các callback phải ổn định (useCallback): useWebSocketProgress nhận chúng
  // làm dependency, nên arrow inline sẽ mở/đóng lại socket mỗi lần render.
  const handleWsMetric = useCallback((metric: TrainingMetrics) => {
    setWsError(null);
    setMetrics((prev) =>
      prev.some((m) => m.epoch === metric.epoch) ? prev : [...prev, metric]
    );
  }, []);

  const handleWsStatus = useCallback((updatedJob: TrainingJob) => {
    setWsError(null);
    setJob(updatedJob);
  }, []);

  // Mất WebSocket nghĩa là tiến độ ngừng cập nhật — phải nói ra, nếu không màn
  // hình đứng ở "Đang chờ epoch đầu tiên..." và trông như hệ thống treo.
  const handleWsError = useCallback(() => {
    setWsError(
      'Mất kết nối theo dõi tiến độ. Quá trình huấn luyện vẫn chạy trên máy chủ — ' +
        'hãy tải lại trang hoặc mở lại phiên này từ Lịch sử để xem tiến độ mới nhất.'
    );
  }, []);

  useWebSocketProgress(job?.id ?? null, handleWsMetric, handleWsStatus, handleWsError);

  const handleStartTraining = async () => {
    const config: TrainingConfig = { ...trainingConfig, dialects: selectedDialects };
    const newJob = await startTraining(config);

    if (newJob) {
      setJob(newJob);
      setCurrentStep(6);
    }
  };

  // Máy chủ đã có sẵn bộ chia RIÊNG cho phương ngữ đang chọn hay chưa.
  // `datasetInfo` được nạp lại mỗi khi đổi phương ngữ, nên cờ này bám đúng
  // phạm vi hiện tại. Phải đọc is_deployment_split, KHÔNG được suy từ
  // counts: khi không có split riêng, backend rơi về split gốc dùng chung
  // cho mọi phương ngữ — split đó luôn có counts > 0 nên tổng counts luôn
  // dương bất kể phương ngữ đang chọn đã từng được chuẩn bị hay chưa. Đây
  // chính là lỗi khiến "đã chuẩn hoá" hiện sai cho mọi lựa chọn.
  const hasExistingSplit = datasetInfo?.split_provenance?.is_deployment_split === true;

  const isTraining = job?.status === 'running';
  const progressRef = useRef<HTMLDivElement>(null);

  // Validation logic for each step
  const isStepValid = (): boolean => {
    switch (currentStep) {
      case 1: // Chọn phương ngữ — phải chọn ít nhất một
        return selectedDialects.length > 0;
      case 2: // Chuẩn bị dữ liệu — phải có bộ chia thì mới đi tiếp được
        return datasetReady;
      case 3: // Chia tập — chỉ hiển thị
        return true;
      case 4: // Augmentation Preview - always valid
        return true;
      case 5: // Training Settings - always valid
        return selectedDialects.length > 0;
      case 6: // Training Progress - automatic
        return true;
      case 7: // Results - automatic
        return true;
      default:
        return true;
    }
  };

  const getNextButtonText = (): string => {
    if (!isStepValid()) {
      switch (currentStep) {
        case 1:
          return 'Chọn phương ngữ trước';
        case 2:
          return 'Chuẩn hoá dữ liệu trước';
        default:
          return 'Hoàn thành bước này';
      }
    }
    return 'Tiếp theo →';
  };

  const handleNext = () => {
    if (!isStepValid()) {
      return;
    }
    setCurrentStep((currentStep + 1) as Step);
  };

  // Scroll to top when step changes
  useEffect(() => {
    if (progressRef.current) {
      progressRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [currentStep]);

  // Auto-advance to results when training completes
  useEffect(() => {
    if (job?.status === 'completed' && currentStep === 6) {
      setCurrentStep(7);
    }
  }, [job?.status, currentStep]);

  // Fetch metrics when entering Step 7 (always refresh to get latest)
  useEffect(() => {
    if (currentStep === 7 && job?.id) {
      getJobMetrics(job.id).then((freshMetrics) => {
        if (freshMetrics && freshMetrics.length > 0) {
          setMetrics(freshMetrics);
        }
      });
    }
  }, [currentStep, job?.id, getJobMetrics]);

  if (view === 'landing') {
    return (
      <div className="space-y-8">
        <PageHeader
          title="Huấn Luyện Mô Hình"
          subtitle="Lịch sử các lần huấn luyện, so sánh model và bắt đầu run mới"
          breadcrumb={['Trang chủ', 'Huấn luyện']}
        />

        <div className="flex justify-end">
          <Button variant="primary" onClick={handleNewTraining}>
            Bắt đầu huấn luyện mới
          </Button>
        </div>

        <TrainingHistory
          jobs={historyJobs}
          loading={historyLoading}
          onOpenJob={handleOpenJob}
          onRefresh={refreshHistory}
          onDeleteJob={handleDeleteJob}
        />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Huấn Luyện Mô Hình"
        subtitle="Quy trình 7 bước để huấn luyện mô hình nhận diện ký hiệu với hiệu suất tối ưu"
        breadcrumb={['Trang chủ', 'Huấn luyện']}
      />

      {/* Progress Bar - Minimal & Clean */}
      <div ref={progressRef} className="mb-8 space-y-3">
        {/* Progress Bar */}
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <div className="h-3 bg-slate-200 rounded-full overflow-hidden shadow-sm">
              <div
                className="h-full bg-gradient-to-r from-ctu-navy via-ctu-blue to-ctu-blue-light transition-all duration-500 ease-out rounded-full"
                style={{ width: `${(currentStep / 7) * 100}%` }}
              />
            </div>
          </div>
          {/* Chỉ báo bước — không phải nút bấm. Trước đây đây là <button> với
              onClick rỗng nên trông bấm được mà không làm gì. */}
          <div
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-ctu-blue/10 border border-ctu-blue/30 flex-shrink-0"
            aria-label={`Bước ${currentStep} trên 7`}
          >
            <span className="font-bold text-ctu-blue text-lg">{currentStep}</span>
            <span className="text-slate-500">/</span>
            <span className="text-slate-600">7</span>
          </div>
        </div>

        {/* Step Info Header */}
        <div className="flex items-center gap-3 p-4 bg-gradient-to-r from-ctu-blue/5 to-ctu-navy/5 rounded-xl border border-ctu-blue/20">
          <div className="flex-shrink-0 text-ctu-blue">{STEP_LABELS[currentStep].icon}</div>
          <div className="flex-1 min-w-0">
            <h2 className="text-lg sm:text-xl font-bold text-slate-900">
              {STEP_LABELS[currentStep].title}
            </h2>
            <p className="text-sm text-slate-600 line-clamp-1 sm:line-clamp-2">
              {STEP_LABELS[currentStep].description}
            </p>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main>
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
          {/* Content Area */}
          <div className="px-6 py-6 sm:px-8 sm:py-8 min-h-[500px]">
            {error && (
              <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-800">
                <div className="flex items-center gap-1.5 font-semibold">
                  <AlertTriangleIcon className="h-4 w-4 shrink-0" />
                  Lỗi
                </div>
                <div className="mt-1">{error}</div>
              </div>
            )}

            {wsError && currentStep === 6 && (
              <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-900">
                <div className="flex items-center gap-1.5 font-semibold">
                  <AlertTriangleIcon className="h-4 w-4 shrink-0" />
                  Mất kết nối theo dõi
                </div>
                <div className="mt-1">{wsError}</div>
              </div>
            )}

            {currentStep === 1 && (
              <DialectSelector
                dialects={datasetInfo?.dialects || {}}
                selected={selectedDialects}
                onChange={setSelectedDialects}
              />
            )}
            {currentStep === 2 && (
              <DatasetPreparationPage
                embedded
                dialects={selectedDialects}
                alreadyPrepared={hasExistingSplit}
                onReadyChange={setDatasetReady}
              />
            )}
            {currentStep === 3 && (
              <DataSplitVisualization datasetInfo={datasetInfo} selectedDialects={selectedDialects} />
            )}
            {currentStep === 4 && <AugmentationPreview />}
            {currentStep === 5 && (
              <TrainingSettings config={trainingConfig} onChange={setTrainingConfig} />
            )}
            {currentStep === 6 && job && (
              <TrainingProgress
                job={job}
                metrics={metrics}
                onCancel={async () => {
                  const cancelled = await api.cancelTraining(job.id);
                  if (cancelled) setJob(cancelled);
                }}
              />
            )}
            {currentStep === 7 && (
              <ResultsInsights
                metrics={metrics}
                job={job}
                onPromote={async () => {
                  if (!job) return null;
                  const res = await api.promoteJob(job.id);
                  if (res?.job) setJob(res.job);
                  return res;
                }}
              />
            )}
          </div>

          {/* Action Buttons */}
          <div className="border-t border-slate-100 px-6 py-4 sm:px-8 sm:py-5 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                onClick={() => setView('landing')}
                size="sm"
                title="Quay về danh sách lịch sử training"
              >
                <HistoryIcon className="h-4 w-4" />
                Lịch sử
              </Button>
              <Button
                variant="secondary"
                onClick={() => currentStep > 1 && setCurrentStep((currentStep - 1) as Step)}
                disabled={currentStep === 1 || currentStep >= 6}
                size="sm"
              >
                ← Quay lại
              </Button>
            </div>

            <div className="flex items-center gap-2">
              {/* Bước 2 ẩn hẳn nút thay vì để mờ: chưa chuẩn hoá thì không có
                  gì để đi tiếp, và chính bước đó đã có nút "Bắt đầu" cùng dòng
                  giải thích nên người dùng không bị kẹt. */}
              {currentStep < 5 && !(currentStep === 2 && !datasetReady) && (
                <Button
                  variant="primary"
                  onClick={handleNext}
                  disabled={!isStepValid()}
                  size="sm"
                  title={!isStepValid() ? 'Vui lòng hoàn thành bước hiện tại' : 'Chuyển sang bước tiếp theo'}
                >
                  {getNextButtonText()}
                </Button>
              )}

              {currentStep === 5 && (
                <Button
                  variant="primary"
                  onClick={handleStartTraining}
                  disabled={selectedDialects.length === 0 || isTraining}
                  size="sm"
                  title={selectedDialects.length === 0 ? 'Vui lòng chọn ít nhất một phương ngữ' : 'Bắt đầu quá trình huấn luyện'}
                >
                  {isTraining ? 'Đang xử lý...' : 'Bắt đầu huấn luyện'}
                </Button>
              )}

              {currentStep === 6 && job?.status === 'completed' && (
                <Button
                  variant="primary"
                  onClick={() => setCurrentStep(7)}
                  size="sm"
                  title="Xem kết quả chi tiết của huấn luyện"
                >
                  Xem Kết Quả →
                </Button>
              )}

              {currentStep === 7 && (
                <Button
                  variant="primary"
                  onClick={() => setView('landing')}
                  size="sm"
                  title="Hoàn tất và quay về màn hình chính"
                >
                  Hoàn tất
                </Button>
              )}

            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default TrainingPipeline;
