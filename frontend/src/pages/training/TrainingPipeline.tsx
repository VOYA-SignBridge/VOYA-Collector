/**
 * Training Pipeline Page - Professional UI/UX Design
 * 7-Step Training Workflow with Real-time Feedback
 */

import React, { useEffect, useRef, useState } from 'react';
import { useTrainingAPI, useWebSocketProgress } from '../../hooks/useTrainingAPI';
import type { TrainingJob, TrainingConfig, TrainingMetrics } from '../../hooks/useTrainingAPI';
import PageHeader from '../../components/ui/PageHeader';
import Button from '../../components/ui/Button';
import DatasetInfo from './components/DatasetInfo';
import DataSplitVisualization from './components/DataSplitVisualization';
import AugmentationPreview from './components/AugmentationPreview';
import DialectSelector from './components/DialectSelector';
import TrainingSettings from './components/TrainingSettings';
import TrainingProgress from './components/TrainingProgress';
import ResultsInsights from './components/ResultsInsights';

type Step = 1 | 2 | 3 | 4 | 5 | 6 | 7;

const STEP_LABELS: Record<number, { title: string; icon: string; description: string }> = {
  1: { title: 'Dữ Liệu', icon: '📊', description: 'Xem thông tin dataset' },
  2: { title: 'Chia Tập', icon: '📈', description: 'Phân tách train/val/test' },
  3: { title: 'Tăng Cường', icon: '✨', description: 'Xem trước augmentation' },
  4: { title: 'Chọn Dialect', icon: '🗣️', description: 'Lựa chọn phương ngữ' },
  5: { title: 'Cấu Hình', icon: '⚙️', description: 'Điều chỉnh hyperparameters' },
  6: { title: 'Huấn Luyện', icon: '🚀', description: 'Quá trình training' },
  7: { title: 'Kết Quả', icon: '📋', description: 'Phân tích kết quả' },
};

const TrainingPipeline: React.FC = () => {
  const [currentStep, setCurrentStep] = useState<Step>(1);
  const [job, setJob] = useState<TrainingJob | null>(null);
  const [metrics, setMetrics] = useState<TrainingMetrics[]>([]);
  const [selectedDialects, setSelectedDialects] = useState<string[]>([]);
  const [trainingConfig, setTrainingConfig] = useState<TrainingConfig>({
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
  const { datasetInfo, loading, error, loadDatasetInfo, startTraining, getJobMetrics } = api;

  useEffect(() => {
    loadDatasetInfo();
  }, [loadDatasetInfo]);

  // Setup WebSocket to stream training progress
  useWebSocketProgress(
    job?.id ?? null,
    (metric) => {
      console.log('[METRIC]', metric);
      setMetrics((prev) => [...prev, metric]);
    },
    (updatedJob) => {
      console.log('[STATUS]', updatedJob);
      setJob(updatedJob);
    },
    (msg) => console.error('[WS_ERROR]', msg)
  );

  const handleStartTraining = async () => {
    const config: TrainingConfig = { ...trainingConfig, dialects: selectedDialects };
    const newJob = await startTraining(config);

    if (newJob) {
      setJob(newJob);
      setCurrentStep(6);
    }
  };

  const isTraining = job?.status === 'running';
  const progressRef = useRef<HTMLDivElement>(null);
  const [savedSteps, setSavedSteps] = useState<Set<number>>(new Set());

  // Validation logic for each step
  const isStepValid = (): boolean => {
    switch (currentStep) {
      case 1: // Dataset Info - always valid
        return !!datasetInfo;
      case 2: // Data Split - always valid
        return true;
      case 3: // Augmentation Preview - always valid
        return true;
      case 4: // Dialect Selector - must select at least one
        return selectedDialects.length > 0;
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
        case 4:
          return '⚠️ Chọn Phương Ngữ Trước';
        default:
          return 'Hoàn thành bước này';
      }
    }
    return 'Tiếp theo →';
  };

  const handleSaveStep = () => {
    if (!isStepValid()) {
      return;
    }
    // Mark step as saved
    setSavedSteps(prev => new Set(prev).add(currentStep));
  };

  const handleSaveAndNext = () => {
    if (!isStepValid()) {
      return;
    }
    // Save current step
    setSavedSteps(prev => new Set(prev).add(currentStep));
    // Move to next step
    setCurrentStep((currentStep + 1) as Step);
  };

  const isStepSaved = savedSteps.has(currentStep);

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

  return (
    <div className="space-y-8">
      <PageHeader
        title="Huấn Luyện Mô Hình"
        subtitle="Quy trình 7 bước để huấn luyện mô hình nhận diện ký hiệu với hiệu suất tối ưu"
        breadcrumb={['Dashboard', 'Huấn luyện']}
      />

      {/* Progress Bar - Minimal & Clean */}
      <div ref={progressRef} className="mb-8 space-y-3">
        {/* Progress Bar */}
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <div className="h-3 bg-slate-200 rounded-full overflow-hidden shadow-sm">
              <div
                className="h-full bg-gradient-to-r from-indigo-500 via-cyan-500 to-teal-600 transition-all duration-500 ease-out rounded-full"
                style={{ width: `${(currentStep / 7) * 100}%` }}
              />
            </div>
          </div>
          <button
            onClick={() => {}}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-50 border border-indigo-200 hover:bg-indigo-100 transition-colors flex-shrink-0"
            title="Hiển thị các bước"
          >
            <span className="font-bold text-indigo-600 text-lg">{currentStep}</span>
            <span className="text-slate-500">/</span>
            <span className="text-slate-600">7</span>
          </button>
        </div>

        {/* Step Info Header */}
        <div className="flex items-center gap-3 p-4 bg-gradient-to-r from-indigo-50 to-cyan-50 rounded-xl border border-indigo-100">
          <div className="text-3xl flex-shrink-0">{STEP_LABELS[currentStep].icon}</div>
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
                <div className="font-semibold">⚠️ Lỗi</div>
                <div className="mt-1">{error}</div>
              </div>
            )}

            {currentStep === 1 && <DatasetInfo datasetInfo={datasetInfo} loading={loading} />}
            {currentStep === 2 && <DataSplitVisualization datasetInfo={datasetInfo} />}
            {currentStep === 3 && <AugmentationPreview />}
            {currentStep === 4 && (
              <DialectSelector
                dialects={datasetInfo?.dialects || {}}
                selected={selectedDialects}
                onChange={setSelectedDialects}
              />
            )}
            {currentStep === 5 && (
              <TrainingSettings config={trainingConfig} onChange={setTrainingConfig} />
            )}
            {currentStep === 6 && job && (
              <TrainingProgress
                job={job}
                metrics={metrics}
                onNext={() => setCurrentStep(7)}
              />
            )}
            {currentStep === 7 && <ResultsInsights metrics={metrics} job={job} />}
          </div>

          {/* Action Buttons */}
          <div className="border-t border-slate-100 px-6 py-4 sm:px-8 sm:py-5 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                onClick={() => currentStep > 1 && setCurrentStep((currentStep - 1) as Step)}
                disabled={currentStep === 1}
                size="sm"
              >
                ← Quay lại
              </Button>
            </div>

            <div className="flex items-center gap-2">
              {currentStep < 5 && (
                <>
                  <Button
                    variant="secondary"
                    onClick={handleSaveStep}
                    disabled={!isStepValid()}
                    size="sm"
                    title="Lưu thông tin của bước hiện tại"
                  >
                    {isStepSaved ? '✓ Đã Lưu' : '💾 Lưu'}
                  </Button>
                  <Button
                    variant="primary"
                    onClick={handleSaveAndNext}
                    disabled={!isStepValid()}
                    size="sm"
                    title={!isStepValid() ? 'Vui lòng hoàn thành bước hiện tại' : 'Lưu và chuyển sang bước tiếp theo'}
                  >
                    {getNextButtonText()} ✓
                  </Button>
                </>
              )}

              {currentStep === 5 && (
                <Button
                  variant="primary"
                  onClick={handleStartTraining}
                  disabled={selectedDialects.length === 0 || isTraining}
                  size="sm"
                  title={selectedDialects.length === 0 ? 'Vui lòng chọn ít nhất một phương ngữ' : 'Bắt đầu quá trình huấn luyện'}
                >
                  {isTraining ? '⏳ Đang xử lý...' : '🚀 Bắt Đầu Huấn Luyện'}
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

            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default TrainingPipeline;
