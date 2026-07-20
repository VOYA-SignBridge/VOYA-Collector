/**
 * Step 7: Results & Insights - Professional Layout
 * Displays final training results and recommendations
 */

import React, { useEffect, useState } from 'react';
import { useTrainingAPI } from '../../../hooks/useTrainingAPI';
import type { JobEvaluation, PromoteResponse, TrainingJob, TrainingMetrics } from '../../../hooks/useTrainingAPI';
import TestTrainedModelModal from './TestTrainedModelModal';
import {
  ClipboardCheckIcon,
  CheckCircleIcon,
  AlertTriangleIcon,
  InfoCircleIcon,
  CopyIcon,
  PlayCircleIcon,
  ArrowUpCircleIcon,
} from '../../../components/ui/Icons';
import { useAuth } from '../../../hooks/useAuth';

interface Props {
  metrics: TrainingMetrics[];
  job: TrainingJob | null;
  onPromote?: () => Promise<PromoteResponse | null>;
}

/** "vn/hoa-de/rang-muoi" → "rang-muoi" */
const prettyLabel = (labelKey: string): string => {
  const parts = String(labelKey || '').replace(/\\/g, '/').split('/');
  return parts[parts.length - 1] || labelKey;
};

const ResultsInsights: React.FC<Props> = ({ metrics, job, onPromote }) => {
  const [showTestModal, setShowTestModal] = useState(false);
  const { isAdmin } = useAuth();
  const { getJobEvaluation } = useTrainingAPI();
  const [promoting, setPromoting] = useState(false);
  const [promoteMessage, setPromoteMessage] = useState<string | null>(null);
  const [evaluation, setEvaluation] = useState<JobEvaluation | null>(null);

  useEffect(() => {
    let stale = false;
    if (job?.id && job.status === 'completed') {
      getJobEvaluation(job.id).then((ev) => {
        if (!stale && ev?.available) setEvaluation(ev);
      });
    }
    return () => {
      stale = true;
    };
  }, [job?.id, job?.status, getJobEvaluation]);

  if (!metrics || metrics.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <ClipboardCheckIcon className="h-12 w-12 mb-4 text-slate-300" />
        <p className="text-slate-600">Chưa có dữ liệu kết quả. Bắt đầu huấn luyện để xem kết quả.</p>
      </div>
    );
  }

  const finalMetric = metrics[metrics.length - 1];
  const bestMetric = metrics.reduce((best, m) => (m.val_f1 > best.val_f1 ? m : best), metrics[0]);

  // Use test metrics from job (loaded from checkpoint), fallback to final validation metrics
  const accuracy = job?.test_acc ?? finalMetric.val_acc ?? 0;
  const f1 = job?.test_f1 ?? finalMetric.val_f1 ?? 0;
  const isTestMetrics = !!job?.test_acc;

  const getQualityLevel = (acc: number) => {
    if (acc >= 0.95)
      return { level: 'Xuất sắc', iconBg: 'bg-emerald-100', iconColor: 'text-emerald-600', badgeBg: 'bg-emerald-50', badgeText: 'text-emerald-700' };
    if (acc >= 0.90)
      return { level: 'Rất tốt', iconBg: 'bg-ctu-blue/10', iconColor: 'text-ctu-blue', badgeBg: 'bg-ctu-blue/5', badgeText: 'text-ctu-navy' };
    if (acc >= 0.80)
      return { level: 'Tốt', iconBg: 'bg-amber-100', iconColor: 'text-amber-600', badgeBg: 'bg-amber-50', badgeText: 'text-amber-700' };
    return { level: 'Cần cải thiện', iconBg: 'bg-orange-100', iconColor: 'text-orange-600', badgeBg: 'bg-orange-50', badgeText: 'text-orange-700' };
  };

  const quality = getQualityLevel(accuracy);

  const getRecommendations = () => {
    const recs: Array<{ type: 'success' | 'warning' | 'info'; text: string }> = [];

    if (metrics.length > 5) {
      const recentMetrics = metrics.slice(-5);
      const recentImprovement =
        recentMetrics[recentMetrics.length - 1].val_f1 - recentMetrics[0].val_f1;
      if (recentImprovement > 0.02) {
        recs.push({
          type: 'success',
          text: 'Model đang cải thiện tốt trong các epoch gần đây',
        });
      } else if (recentImprovement < -0.02) {
        recs.push({
          type: 'warning',
          text: 'Model có dấu hiệu overfitting — xem xét giảm số epoch hoặc thêm regularization',
        });
      }
    }

    if (accuracy >= 0.9) {
      recs.push({
        type: 'success',
        text: 'Model sẵn sàng để sử dụng trong thực tế',
      });
    } else if (accuracy >= 0.8) {
      recs.push({
        type: 'info',
        text: 'Cân nhắc huấn luyện lại với dữ liệu lớn hơn hoặc điều chỉnh hyperparameters',
      });
    } else {
      recs.push({
        type: 'warning',
        text: 'Cần cải thiện — thêm dữ liệu huấn luyện và thử các kiến trúc khác',
      });
    }

    return recs;
  };

  const recommendations = getRecommendations();

  return (
    <div className="space-y-6">
      {/* Overall Quality Summary */}
      <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className={`flex h-14 w-14 items-center justify-center rounded-full ${quality.iconBg}`}>
            <CheckCircleIcon className={`h-7 w-7 ${quality.iconColor}`} />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-slate-900">Huấn luyện hoàn tất</h2>
            <span className={`mt-2 inline-block rounded-full px-3 py-1 text-xs font-medium ${quality.badgeBg} ${quality.badgeText}`}>
              {quality.level}
            </span>
          </div>
          <div className="mt-2">
            <div className="text-4xl font-bold text-slate-900">{(accuracy * 100).toFixed(1)}%</div>
            <p className="mt-1 text-sm text-slate-500">
              {isTestMetrics ? 'Độ chính xác trên tập test' : 'Độ chính xác validation (epoch cuối)'}
            </p>
          </div>
        </div>
      </div>

      {/* Key Metrics Grid */}
      <div>
        <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-4">
          Chỉ số hiệu suất chính
        </h3>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label="Độ chính xác (Accuracy)"
            value={(accuracy * 100).toFixed(1)}
            unit="%"
            description="Tỷ lệ dự đoán đúng"
            color="indigo"
          />
          <MetricCard
            label="F1 Score"
            value={f1.toFixed(3)}
            unit=""
            description="Cân bằng Precision/Recall"
            color="purple"
          />
          <MetricCard
            label="Số epoch đã chạy"
            value={finalMetric.epoch.toString()}
            unit=""
            description={`Tổng cộng ${job?.total_epochs || 0} epoch`}
            color="blue"
          />
          <MetricCard
            label="F1 Score tốt nhất"
            value={bestMetric.val_f1.toFixed(3)}
            unit=""
            description={`Tại epoch ${bestMetric.epoch}`}
            color="emerald"
          />
        </div>
      </div>

      {/* Per-class evaluation + confusion matrix (test set) */}
      {evaluation?.per_class && evaluation.per_class.length > 0 && (
        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-200 bg-white p-6">
            <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-1">
              Hiệu suất theo lớp (tập test)
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              Sắp xếp từ yếu nhất — các lớp F1 thấp cần thu thêm dữ liệu hoặc kiểm tra chất lượng mẫu.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs text-slate-500 uppercase">
                    <th className="py-2 pr-3 font-medium">Lớp</th>
                    <th className="py-2 px-3 font-medium text-right">Precision</th>
                    <th className="py-2 px-3 font-medium text-right">Recall</th>
                    <th className="py-2 px-3 font-medium text-right">F1</th>
                    <th className="py-2 pl-3 font-medium text-right">Mẫu test</th>
                  </tr>
                </thead>
                <tbody>
                  {[...evaluation.per_class]
                    .sort((a, b) => a.f1 - b.f1)
                    .map((c) => {
                      const weak = c.f1 < 0.5;
                      return (
                        <tr
                          key={c.class_idx}
                          className={`border-b border-slate-100 ${weak ? 'bg-amber-50' : ''}`}
                        >
                          <td className="py-2 pr-3 font-medium text-slate-800">
                            <span className="inline-flex items-center gap-1.5">
                              {weak && (
                                <AlertTriangleIcon
                                  className="h-3.5 w-3.5 shrink-0 text-amber-500"
                                  aria-label="F1 dưới 0.5 — lớp yếu"
                                />
                              )}
                              {prettyLabel(c.label_key)}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-right tabular-nums text-slate-700">{(c.precision * 100).toFixed(1)}%</td>
                          <td className="py-2 px-3 text-right tabular-nums text-slate-700">{(c.recall * 100).toFixed(1)}%</td>
                          <td className={`py-2 px-3 text-right tabular-nums font-semibold ${weak ? 'text-amber-700' : 'text-slate-900'}`}>
                            {c.f1.toFixed(3)}
                          </td>
                          <td className="py-2 pl-3 text-right tabular-nums text-slate-500">{c.support}</td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          </div>

          {evaluation.confusion_matrix && evaluation.labels && (
            <ConfusionMatrixHeatmap labels={evaluation.labels} matrix={evaluation.confusion_matrix} />
          )}
        </div>
      )}

      {/* Recommendations */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wider">
          Khuyến nghị
        </h3>
        {recommendations.map((rec, idx) => {
          const RecIcon = rec.type === 'success' ? CheckCircleIcon : rec.type === 'warning' ? AlertTriangleIcon : InfoCircleIcon;
          return (
            <div
              key={idx}
              className={`flex items-start gap-2.5 rounded-lg border-l-4 p-4 ${
                rec.type === 'success'
                  ? 'border-l-emerald-500 bg-emerald-50 text-emerald-900'
                  : rec.type === 'warning'
                  ? 'border-l-amber-500 bg-amber-50 text-amber-900'
                  : 'border-l-ctu-blue bg-ctu-blue/10 text-ctu-navy'
              }`}
            >
              <RecIcon className="mt-0.5 h-4 w-4 shrink-0" />
              <p>{rec.text}</p>
            </div>
          );
        })}
      </div>

      {/* Model Info */}
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
        <h4 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-3">
          Thông tin model
        </h4>
        <div className="space-y-2 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-slate-600">Mã tác vụ:</span>
            <code className="font-mono text-xs bg-white rounded px-2 py-1 border border-slate-200">
              {job?.id}
            </code>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-600">Trạng thái:</span>
            <span className="font-semibold text-emerald-700 bg-emerald-50 px-2 py-1 rounded">
              {job?.status}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-600">Thời gian tạo:</span>
            <span className="text-slate-900">
              {job?.created_at
                ? new Date(job.created_at).toLocaleString('vi-VN', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit'
                  })
                : 'N/A'}
            </span>
          </div>
          {job?.checkpoint_path && (
            <div className="flex flex-col gap-2">
              <div className="flex items-start justify-between">
                <span className="text-slate-600">Đường dẫn model:</span>
                <code className="font-mono text-xs bg-white rounded px-2 py-1 border border-slate-200 break-all">
                  {job.checkpoint_path}
                </code>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(job.checkpoint_path || '');
                  }}
                  className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded bg-white border border-slate-300 hover:bg-slate-100 text-slate-700 font-medium transition"
                >
                  <CopyIcon className="h-3.5 w-3.5" />
                  Sao chép đường dẫn
                </button>
                <button
                  onClick={() => setShowTestModal(true)}
                  className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded bg-ctu-blue hover:bg-ctu-navy text-white font-medium transition shadow-sm"
                >
                  <PlayCircleIcon className="h-3.5 w-3.5" />
                  Kiểm tra model (Realtime)
                </button>
                {isAdmin && onPromote && job.status === 'completed' && !job.promoted_at && (
                  <button
                    onClick={async () => {
                      if (!window.confirm('Đưa model này vào tab nhận diện realtime? Model sẽ hiển thị cho tất cả người dùng.')) return;
                      setPromoting(true);
                      setPromoteMessage(null);
                      try {
                        const res = await onPromote();
                        setPromoteMessage(res ? res.message : 'Không thể đưa vào Realtime — kiểm tra quyền admin hoặc log backend');
                      } finally {
                        setPromoting(false);
                      }
                    }}
                    disabled={promoting}
                    className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-700 text-white font-medium transition shadow-sm disabled:opacity-60"
                  >
                    <ArrowUpCircleIcon className="h-3.5 w-3.5" />
                    {promoting ? 'Đang đưa vào Realtime...' : 'Đưa vào Realtime'}
                  </button>
                )}
              </div>
              {job.promoted_at && (
                <div className="flex items-center gap-1.5 rounded-lg bg-emerald-50 border border-emerald-200 px-3 py-2 text-xs text-emerald-800">
                  <CheckCircleIcon className="h-3.5 w-3.5 shrink-0" />
                  Đã đưa vào Realtime lúc{' '}
                  {new Date(job.promoted_at).toLocaleString('vi-VN')}
                </div>
              )}
              {promoteMessage && !job.promoted_at && (
                <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800">
                  {promoteMessage}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Training Complete Message */}
      <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-3">
        <CheckCircleIcon className="h-4 w-4 shrink-0 text-emerald-600" />
        <p className="text-sm text-emerald-900">
          Model đã được lưu và sẵn sàng kiểm tra — nhấn "Kiểm tra model (Realtime)" để xem hiệu suất thực tế.
        </p>
      </div>

      {/* Test Trained Model Modal */}
      {job && (
        <TestTrainedModelModal
          isOpen={showTestModal}
          onClose={() => setShowTestModal(false)}
          modelId={`training_${job.id}`}
        />
      )}
    </div>
  );
};

function MetricCard({
  label,
  value,
  unit,
  description,
  color,
}: {
  label: string;
  value: string;
  unit: string;
  description: string;
  color: 'indigo' | 'purple' | 'blue' | 'emerald';
}) {
  const colorClasses = {
    indigo: 'border-ctu-blue/30 bg-ctu-blue/5',
    purple: 'border-purple-200 bg-purple-50',
    blue: 'border-ctu-navy/30 bg-ctu-navy/5',
    emerald: 'border-emerald-200 bg-emerald-50',
  };

  const valueClasses = {
    indigo: 'text-ctu-blue',
    purple: 'text-purple-600',
    blue: 'text-ctu-navy',
    emerald: 'text-emerald-600',
  };

  return (
    <div className={`rounded-xl border p-4 ${colorClasses[color]}`}>
      <p className="text-xs text-slate-600 mb-2">{label}</p>
      <div className="flex items-baseline gap-1">
        <div className={`text-2xl font-bold ${valueClasses[color]}`}>{value}</div>
        <span className={`text-sm font-semibold ${valueClasses[color]}`}>{unit}</span>
      </div>
      <p className="text-xs text-slate-600 mt-2">{description}</p>
    </div>
  );
}

/**
 * Confusion matrix heatmap.
 * Sequential single-hue (ctu-blue) — intensity = share of the TRUE class's
 * samples predicted as each column (row-normalized). The diagonal (correct
 * predictions) is marked structurally with a ring, not a different hue.
 */
function ConfusionMatrixHeatmap({ labels, matrix }: { labels: string[]; matrix: number[][] }) {
  const n = labels.length;
  if (n === 0) return null;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6">
      <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-1">
        Confusion Matrix (Test Set)
      </h3>
      <p className="text-xs text-slate-500 mb-4">
        Hàng = lớp thật, cột = lớp dự đoán (theo số thứ tự). Màu đậm = tỷ lệ cao trong hàng;
        ô viền đen trên đường chéo là dự đoán đúng. Di chuột lên ô để xem chi tiết.
      </p>
      <div className="overflow-x-auto pb-2">
        <table className="border-collapse">
          <thead>
            <tr>
              <th className="pr-2" />
              {labels.map((_, j) => (
                <th key={j} className="w-8 px-0.5 pb-1 text-center text-[10px] font-normal text-slate-500">
                  {j}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.map((row, i) => {
              const rowTotal = row.reduce((s, v) => s + v, 0);
              return (
                <tr key={i}>
                  <th className="pr-2 py-0.5 text-right text-[11px] font-normal text-slate-600 whitespace-nowrap">
                    <span className="text-slate-400">{i}</span> · {prettyLabel(labels[i])}
                  </th>
                  {row.map((v, j) => {
                    const share = rowTotal > 0 ? v / rowTotal : 0;
                    const isDiag = i === j;
                    return (
                      <td
                        key={j}
                        title={`Thật: ${prettyLabel(labels[i])} → Dự đoán: ${prettyLabel(labels[j])}\n${v} mẫu (${(share * 100).toFixed(0)}% của lớp thật)`}
                        className={`h-8 w-8 min-w-8 text-center align-middle text-[10px] tabular-nums ${
                          isDiag ? 'ring-1 ring-inset ring-slate-500' : ''
                        }`}
                        style={{
                          backgroundColor: v === 0 ? 'transparent' : `rgba(14, 123, 194, ${0.12 + 0.78 * share})`,
                          color: share > 0.55 ? '#ffffff' : '#334155',
                        }}
                      >
                        {v > 0 ? v : ''}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex items-center gap-2 text-[11px] text-slate-500">
        <span>0%</span>
        <div
          className="h-2 w-28 rounded"
          style={{ background: 'linear-gradient(to right, rgba(14,123,194,0.12), rgba(14,123,194,0.9))' }}
        />
        <span>100% của lớp thật</span>
      </div>
    </div>
  );
}

export default ResultsInsights;
