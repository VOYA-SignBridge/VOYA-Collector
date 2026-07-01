/**
 * Step 6: Training Progress
 * Real-time progress, metrics, và status
 */

import React, { useEffect, useMemo, useState } from 'react';
import type { TrainingJob, TrainingMetrics } from '../../../hooks/useTrainingAPI';
import LoadingSpinner from '../../../components/ui/LoadingSpinner';

interface Props {
  job: TrainingJob;
  metrics: TrainingMetrics[];
  onNext?: () => void;
}

const TrainingProgress: React.FC<Props> = ({ job, metrics, onNext }) => {
  const [startTime] = useState<Date>(new Date(job.started_at || new Date()));
  const [elapsedTime, setElapsedTime] = useState('0m');
  const [eta, setEta] = useState('Tính toán...');

  // Update elapsed time and ETA
  useEffect(() => {
    const interval = setInterval(() => {
      const now = new Date();
      const elapsed = Math.floor((now.getTime() - startTime.getTime()) / 1000);
      const minutes = Math.floor(elapsed / 60);
      const seconds = elapsed % 60;
      setElapsedTime(`${minutes}m ${seconds}s`);

      if (metrics.length > 0) {
        const last = metrics[metrics.length - 1];
        const avgTimePerEpoch = elapsed / Math.max(1, last.epoch);
        const remainingEpochs = Math.max(0, job.total_epochs - last.epoch);
        const remainingSeconds = Math.ceil(avgTimePerEpoch * remainingEpochs);
        const remainingMinutes = Math.floor(remainingSeconds / 60);
        setEta(`~${remainingMinutes}m`);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [startTime, metrics, job.total_epochs]);

  const trainLossSeries = useMemo(() => metrics.map((m) => m.train_loss), [metrics]);
  const trainAccSeries = useMemo(() => metrics.map((m) => m.train_acc), [metrics]);
  const valAccSeries = useMemo(() => metrics.map((m) => m.val_acc), [metrics]);

  const latestMetric = metrics[metrics.length - 1];
  const progressPercent = latestMetric ? (latestMetric.epoch / Math.max(1, job.total_epochs)) * 100 : 0;

  const renderSparkline = (values: number[], stroke = '#7c3aed') => {
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

  return (
    <div className="space-y-6">
      {/* Header with Timer */}
      <div className="rounded-xl border border-slate-200 bg-gradient-to-br from-slate-50 to-slate-100 p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-slate-900">🚀 Đang Huấn Luyện Mô Hình</h3>
            <p className="mt-1 text-sm text-slate-600">
              Trạng thái: <span className="font-medium text-indigo-600">{job.status}</span>
            </p>
          </div>
          <div className="text-right">
            <div className="text-sm text-slate-600">
              <div>⏱️ Thời gian: <strong>{elapsedTime}</strong></div>
              <div className="text-xs text-slate-500 mt-1">ETA: {eta}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-sm font-semibold text-slate-900">Tiến độ huấn luyện</h4>
          <span className="text-sm font-bold text-indigo-600">
            {latestMetric ? `${latestMetric.epoch}/${job.total_epochs}` : '0/0'} epochs
          </span>
        </div>
        <div className="h-3 w-full bg-slate-200 rounded-full overflow-hidden">
          <div
            className="h-3 bg-gradient-to-r from-indigo-500 to-cyan-500 transition-all duration-300"
            style={{ width: `${Math.max(0, Math.min(100, progressPercent))}%` }}
          />
        </div>
        <p className="mt-1 text-xs text-slate-500">{Math.round(progressPercent)}% hoàn thành</p>
      </div>

      {/* Metrics Cards */}
      {!latestMetric ? (
        <div className="flex items-center justify-center py-12 text-slate-500">
          <LoadingSpinner size="md" />
          <span className="ml-3">Đang chờ epoch đầu tiên...</span>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label="Training Loss"
            value={latestMetric.train_loss.toFixed(4)}
            trend={metrics.length > 1 && metrics[metrics.length - 2].train_loss > latestMetric.train_loss ? '↘️ Giảm' : '↗️ Tăng'}
            sparkline={renderSparkline(trainLossSeries, '#ef4444')}
            color="red"
            description="Mức độ sai lệch trên tập huấn luyện"
          />
          <MetricCard
            label="Train Accuracy"
            value={`${(latestMetric.train_acc * 100).toFixed(1)}%`}
            trend={metrics.length > 1 && metrics[metrics.length - 2].train_acc < latestMetric.train_acc ? '↗️ Tăng' : '↘️ Giảm'}
            sparkline={renderSparkline(trainAccSeries, '#10b981')}
            color="green"
            description="Độ chính xác trên tập huấn luyện"
          />
          <MetricCard
            label="Val Accuracy ⭐"
            value={`${(latestMetric.val_acc * 100).toFixed(1)}%`}
            trend="KPI Chính"
            sparkline={renderSparkline(valAccSeries, '#06b6d4')}
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

      {/* Handedness Breakdown */}
      {latestMetric?.handedness && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h4 className="font-semibold text-slate-900 mb-4">🤚 Độ Chính Xác Theo Tay</h4>
          <div className="grid gap-4 sm:grid-cols-3">
            <HandednessCard
              emoji="👈"
              label="Tay Trái"
              accuracy={latestMetric.handedness.left_only_acc}
              count={latestMetric.handedness.left_only_n}
            />
            <HandednessCard
              emoji="👉"
              label="Tay Phải"
              accuracy={latestMetric.handedness.right_only_acc}
              count={latestMetric.handedness.right_only_n}
            />
            <HandednessCard
              emoji="👐"
              label="Cả Hai Tay"
              accuracy={latestMetric.handedness.both_acc}
              count={latestMetric.handedness.both_n}
            />
          </div>
        </div>
      )}

      {/* Recent Epochs History */}
      {metrics.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h4 className="font-semibold text-slate-900 mb-4">📈 Lịch Sử Metrics (5 Epoch Gần Nhất)</h4>
          <div className="grid gap-3 sm:grid-cols-5">
            {metrics.slice(-5).map((m) => (
              <div key={m.epoch} className="rounded-lg bg-gradient-to-br from-slate-50 to-slate-100 p-3 text-center border border-slate-200">
                <div className="font-semibold text-slate-900">E{m.epoch}</div>
                <div className="mt-2 space-y-1 text-xs">
                  <div>
                    <span className="text-slate-500">Loss:</span> <span className="font-bold text-red-600">{m.train_loss.toFixed(3)}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">Val:</span> <span className="font-bold text-indigo-600">{(m.val_acc * 100).toFixed(1)}%</span>
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
        <div className="rounded-lg bg-blue-50 border border-blue-200 p-4 text-sm text-blue-900">
          ℹ️ Mô hình sẽ được lưu tự động khi huấn luyện hoàn tất.
        </div>

        {/* Manual next button - visible when training is running or completed */}
        {(job?.status === 'running' || job?.status === 'completed') && onNext && (
          <button
            onClick={onNext}
            className="w-full px-6 py-3 bg-gradient-to-r from-indigo-500 to-cyan-500 text-white font-semibold rounded-xl hover:shadow-lg transition-all duration-200 flex items-center justify-center gap-2"
          >
            <span>✓ Lưu &amp; Tiếp Tục</span>
            <span>→</span>
          </button>
        )}
      </div>
    </div>
  );
};

function HandednessCard({
  emoji,
  label,
  accuracy,
  count,
}: {
  emoji: string;
  label: string;
  accuracy: number;
  count: number;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-gradient-to-br from-white to-slate-50 p-4 text-center">
      <div className="text-3xl mb-2">{emoji}</div>
      <h5 className="font-semibold text-slate-900 text-sm">{label}</h5>
      <div className="mt-2">
        <div className="text-2xl font-bold text-indigo-600">{(accuracy * 100).toFixed(1)}%</div>
        <div className="text-xs text-slate-500 mt-1">{count} mẫu</div>
      </div>
    </div>
  );
}

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
    blue: 'border-indigo-200 bg-indigo-50',
    purple: 'border-purple-200 bg-purple-50',
  };

  const valueClasses = {
    red: 'text-red-600',
    green: 'text-emerald-600',
    blue: 'text-indigo-600',
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
