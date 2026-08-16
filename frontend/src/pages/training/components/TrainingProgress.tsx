/**
 * Step 6: Training Progress
 * Real-time progress, metrics, và status
 */

import React, { useEffect, useMemo, useState } from 'react';
import type { TrainingJob, TrainingMetrics } from '../../../hooks/useTrainingAPI';
import LoadingSpinner from '../../../components/ui/LoadingSpinner';
import Button from '../../../components/ui/Button';
import {
  ClockIcon,
  InfoCircleIcon,
  StopCircleIcon,
  XCircleIcon,
} from '../../../components/ui/Icons';
import { jobStatusBadge } from '../jobStatus';
import { formatDuration } from '../jobTiming';

interface Props {
  job: TrainingJob;
  metrics: TrainingMetrics[];
  onCancel?: () => Promise<void> | void;
}

// Job đã kết thúc thì mọi thứ "đang chạy" (đồng hồ, ETA, nút Hủy) đều vô nghĩa.
const isLive = (status: string) => status === 'running' || status === 'pending' || status === 'queued';

const TrainingProgress: React.FC<Props> = ({ job, metrics, onCancel }) => {
  const [cancelling, setCancelling] = useState(false);
  const [startTime] = useState<Date>(new Date(job.started_at || new Date()));
  const [elapsedTime, setElapsedTime] = useState('0m 0s');
  const [eta, setEta] = useState('Tính toán...');

  const live = isLive(job.status);

  // Đồng hồ + ETA chỉ chạy khi job còn sống. Mở lại một job đã thất bại từ Lịch
  // sử trước đây làm đồng hồ đếm từ started_at cũ (ra hàng nghìn phút và vẫn
  // tăng); giờ chốt ở khoảng thời gian thực tế đã chạy.
  useEffect(() => {
    const tick = () => {
      const end = live ? new Date() : new Date(job.completed_at || job.started_at || Date.now());
      const elapsed = Math.floor((end.getTime() - startTime.getTime()) / 1000);
      setElapsedTime(formatDuration(elapsed));

      if (live && metrics.length > 0) {
        const last = metrics[metrics.length - 1];
        const avgTimePerEpoch = elapsed / Math.max(1, last.epoch);
        const remainingEpochs = Math.max(0, job.total_epochs - last.epoch);
        const remainingSeconds = Math.ceil(avgTimePerEpoch * remainingEpochs);
        setEta(remainingSeconds < 60 ? '< 1m' : `~${Math.round(remainingSeconds / 60)}m`);
      }
    };

    tick();
    if (!live) return;

    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [startTime, metrics, job.total_epochs, job.completed_at, job.started_at, live]);

  const trainLossSeries = useMemo(() => metrics.map((m) => m.train_loss), [metrics]);
  const trainAccSeries = useMemo(() => metrics.map((m) => m.train_acc), [metrics]);
  const valAccSeries = useMemo(() => metrics.map((m) => m.val_acc), [metrics]);

  const latestMetric = metrics[metrics.length - 1];
  const progressPercent = latestMetric ? (latestMetric.epoch / Math.max(1, job.total_epochs)) * 100 : 0;

  const renderSparkline = (values: number[], stroke = '#1b2a57') => {
    if (!values || values.length === 0) return null;
    const w = 80;
    const h = 28;
    const max = Math.max(...values);
    const min = Math.min(...values);
    const range = max - min || 1;
    const step = w / Math.max(1, values.length - 1);
    const points = values.map((v, i) => `${i * step},${h - ((v - min) / range) * h}`).join(' ');
    return (
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="inline-block align-middle">
        <polyline fill="none" stroke={stroke} strokeWidth={2} points={points} strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  };

  const badge = jobStatusBadge(job.status);
  // Tiêu đề trước đây luôn là "Đang Huấn Luyện Mô Hình", kể cả khi mở lại một
  // job đã thất bại/bị hủy từ Lịch sử — mâu thuẫn thẳng với dòng trạng thái ngay dưới.
  const headerTitle =
    job.status === 'failed'
      ? 'Huấn luyện thất bại'
      : job.status === 'cancelled'
      ? 'Huấn luyện đã bị hủy'
      : job.status === 'completed'
      ? 'Huấn luyện hoàn tất'
      : live && job.status === 'running'
      ? 'Đang huấn luyện mô hình'
      : 'Phiên huấn luyện đang chờ';

  return (
    <div className="space-y-6">
      {/* Header with Timer */}
      <div className="rounded-xl border border-slate-200 bg-gradient-to-br from-slate-50 to-slate-100 p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-slate-900">{headerTitle}</h3>
            <p className="mt-1 text-sm text-slate-600">
              Trạng thái:{' '}
              <span className={`ml-1 rounded-full px-2 py-0.5 text-xs font-medium ${badge.cls}`}>
                {badge.text}
              </span>
            </p>
            {job.error_message && (
              <p className="mt-2 text-sm text-red-700">{job.error_message}</p>
            )}
          </div>
          <div className="text-right">
            <div className="text-sm text-slate-600">
              <div className="flex items-center justify-end gap-1.5">
                <ClockIcon className="h-4 w-4" />
                Thời gian: <strong>{elapsedTime}</strong>
              </div>
              {live && <div className="text-xs text-slate-500 mt-1">Dự kiến còn: {eta}</div>}
            </div>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-sm font-semibold text-slate-900">Tiến độ huấn luyện</h4>
          <span className="text-sm font-bold text-ctu-blue">
            {latestMetric ? `${latestMetric.epoch}/${job.total_epochs}` : '0/0'} epochs
          </span>
        </div>
        <div className="h-3 w-full bg-slate-200 rounded-full overflow-hidden">
          <div
            className="h-3 bg-gradient-to-r from-ctu-navy to-ctu-blue transition-all duration-300"
            style={{ width: `${Math.max(0, Math.min(100, progressPercent))}%` }}
          />
        </div>
        <p className="mt-1 text-xs text-slate-500">{Math.round(progressPercent)}% hoàn thành</p>
      </div>

      {/* Metrics Cards */}
      {!latestMetric ? (
        <div className="flex items-center justify-center py-12 text-slate-500">
          <LoadingSpinner size="md" label="Đang chờ epoch đầu tiên..." />
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label="Training Loss"
            value={latestMetric.train_loss.toFixed(4)}
            trend={metrics.length > 1 && metrics[metrics.length - 2].train_loss > latestMetric.train_loss ? 'Giảm' : 'Tăng'}
            sparkline={renderSparkline(trainLossSeries, '#ef4444')}
            color="red"
            description="Mức độ sai lệch trên tập huấn luyện"
          />
          <MetricCard
            label="Train Accuracy"
            value={`${(latestMetric.train_acc * 100).toFixed(1)}%`}
            trend={metrics.length > 1 && metrics[metrics.length - 2].train_acc < latestMetric.train_acc ? 'Tăng' : 'Giảm'}
            sparkline={renderSparkline(trainAccSeries, '#10b981')}
            color="green"
            description="Độ chính xác trên tập huấn luyện"
          />
          <MetricCard
            label="Độ chính xác kiểm định"
            value={`${(latestMetric.val_acc * 100).toFixed(1)}%`}
            trend="KPI Chính"
            sparkline={renderSparkline(valAccSeries, '#0e7bc2')}
            color="blue"
            description="Độ chính xác trên tập kiểm tra"
          />
          <MetricCard
            label="F1 Score"
            value={latestMetric.val_f1.toFixed(3)}
            trend="Cân bằng"
            sparkline={renderSparkline(trainLossSeries, '#8b5cf6')}
            color="purple"
            description="Precision/Recall cân bằng"
          />
        </div>
      )}

      {/* Recent Epochs History */}
      {metrics.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h4 className="font-semibold text-slate-900 mb-4">Lịch Sử Metrics (5 Epoch Gần Nhất)</h4>
          <div className="grid gap-3 sm:grid-cols-5">
            {metrics.slice(-5).map((m) => (
              <div key={m.epoch} className="rounded-lg bg-gradient-to-br from-slate-50 to-slate-100 p-3 text-center border border-slate-200">
                <div className="font-semibold text-slate-900">E{m.epoch}</div>
                <div className="mt-2 space-y-1 text-xs">
                  <div>
                    <span className="text-slate-500">Loss:</span> <span className="font-bold text-red-600">{m.train_loss.toFixed(3)}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">Val:</span> <span className="font-bold text-ctu-blue">{(m.val_acc * 100).toFixed(1)}%</span>
                  </div>
                  <div>
                    <span className="text-slate-500">F1:</span> <span className="font-bold text-emerald-600">{m.val_f1.toFixed(3)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-4">
        {(job?.status === 'cancelled' || job?.status === 'failed') ? (
          <div className={`rounded-lg border p-4 text-sm ${
            job.status === 'cancelled'
              ? 'bg-amber-50 border-amber-300 text-amber-900'
              : 'bg-red-50 border-red-300 text-red-900'
          }`}>
            {job.status === 'cancelled' ? (
              <StopCircleIcon className="h-4 w-4 shrink-0" />
            ) : (
              <XCircleIcon className="h-4 w-4 shrink-0" />
            )}
            {job.status === 'cancelled' ? 'Huấn luyện đã bị hủy' : 'Huấn luyện thất bại'}
            {job.error_message ? ` — ${job.error_message}` : ''}
          </div>
        ) : (
          <div className="rounded-lg bg-ctu-blue/10 border border-ctu-blue/30 p-4 text-sm text-ctu-navy">
            <InfoCircleIcon className="h-4 w-4 shrink-0" />
            Mô hình sẽ được lưu tự động khi huấn luyện xong.
          </div>
        )}

        {/* Cancel button - visible while queued/running */}
        {(job?.status === 'running' || job?.status === 'queued') && onCancel && (
          <Button
            variant="danger"
            size="lg"
            disabled={cancelling}
            className="w-full"
            onClick={async () => {
              if (!window.confirm('Bạn có chắc muốn hủy huấn luyện này?')) return;
              setCancelling(true);
              try {
                await onCancel();
              } finally {
                setCancelling(false);
              }
            }}
          >
            <StopCircleIcon className="h-4 w-4" />
            {cancelling ? 'Đang hủy...' : 'Hủy huấn luyện'}
          </Button>
        )}
      </div>
    </div>
  );
};

function MetricCard({
  label,
  value,
  trend,
  sparkline,
  color,
  description,
}: {
  label: string;
  value: string | number;
  trend: string;
  sparkline: React.ReactNode;
  color: 'red' | 'green' | 'blue' | 'purple';
  description: string;
}) {
  const colorClasses = {
    red: 'border-red-200 bg-red-50',
    green: 'border-emerald-200 bg-emerald-50',
    blue: 'border-ctu-blue/30 bg-ctu-blue/5',
    purple: 'border-purple-200 bg-purple-50',
  };

  const valueClasses = {
    red: 'text-red-600',
    green: 'text-emerald-600',
    blue: 'text-ctu-blue',
    purple: 'text-purple-600',
  };

  return (
    <div className={`rounded-xl border p-4 ${colorClasses[color]}`}>
      <div className="flex items-start justify-between mb-2">
        <h4 className="text-sm font-semibold text-slate-900">{label}</h4>
        <span className="text-xs text-slate-600">{trend}</span>
      </div>
      <div className="flex items-end justify-between">
        <div className={`text-2xl font-bold ${valueClasses[color]}`}>{value}</div>
        <div className="opacity-60">{sparkline}</div>
      </div>
      <p className="mt-2 text-xs text-slate-600">{description}</p>
    </div>
  );
}

export default TrainingProgress;
