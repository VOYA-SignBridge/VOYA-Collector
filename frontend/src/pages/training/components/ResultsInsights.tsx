/**
 * Step 7: Results & Insights - Professional Layout
 * Displays final training results and recommendations
 */

import React, { useEffect, useState } from 'react';
import { useTrainingAPI } from '../../../hooks/useTrainingAPI';
import type { JobEvaluation, JobProvenance, PromoteResponse, TrainingJob, TrainingMetrics } from '../../../hooks/useTrainingAPI';
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
import { jobStatusBadge } from '../jobStatus';
import SplitProtocolBanner from './SplitProtocolBanner';
import Collapsible from '../../../components/ui/Collapsible';
import { formatDuration, jobDurationSeconds } from '../jobTiming';

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

const ProvenanceGroup: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div>
    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">{title}</p>
    <div className="space-y-1.5">{children}</div>
  </div>
);

/** One provenance field. Renders "chưa ghi" rather than an empty cell, so a
 *  missing value reads as a fact about the run instead of a broken UI. */
const ProvenanceRow: React.FC<{
  label: string;
  value?: string | number | null;
  mono?: boolean;
  truncate?: boolean;
  copyable?: boolean;
}> = ({ label, value, mono, truncate, copyable }) => {
  const text = value === null || value === undefined || value === '' ? '' : String(value);
  const shown = text && truncate && text.length > 12 ? `${text.slice(0, 12)}…` : text;

  return (
    <div className="flex items-baseline justify-between gap-2 text-sm">
      <span className="text-slate-600 shrink-0">{label}:</span>
      <span className="flex items-center gap-1 min-w-0">
        <span
          className={`${mono ? 'font-mono text-xs' : ''} ${text ? 'text-slate-900' : 'italic text-slate-400'} truncate`}
          title={text || undefined}
        >
          {shown || 'chưa ghi'}
        </span>
        {copyable && text && (
          <button
            onClick={() => navigator.clipboard.writeText(text)}
            className="shrink-0 text-slate-400 hover:text-slate-700 transition"
            aria-label={`Sao chép ${label}`}
          >
            <CopyIcon className="h-3 w-3" />
          </button>
        )}
      </span>
    </div>
  );
};

const ResultsInsights: React.FC<Props> = ({ metrics, job, onPromote }) => {
  const [showTestModal, setShowTestModal] = useState(false);
  const { isAdmin } = useAuth();
  const { getJobEvaluation, getJobProvenance } = useTrainingAPI();
  const [promoting, setPromoting] = useState(false);
  // Giữ nguyên cả phản hồi promote, không chỉ chuỗi message: hai cờ
  // registry_updated / realtime_reloaded phân biệt "đã dùng được ngay" với
  // "phải khởi động lại dịch vụ mới có hiệu lực".
  const [promoteResult, setPromoteResult] = useState<PromoteResponse | null>(null);
  const [evaluation, setEvaluation] = useState<JobEvaluation | null>(null);
  const [provenance, setProvenance] = useState<JobProvenance | null>(null);

  useEffect(() => {
    let stale = false;
    if (job?.id && job.status === 'completed') {
      getJobEvaluation(job.id).then((ev) => {
        if (!stale && ev?.available) setEvaluation(ev);
      });
      getJobProvenance(job.id).then((pv) => {
        if (!stale && pv?.available) setProvenance(pv);
      });
    }
    return () => {
      stale = true;
    };
  }, [job?.id, job?.status, getJobEvaluation, getJobProvenance]);

  if (!metrics || metrics.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <ClipboardCheckIcon className="h-12 w-12 mb-4 text-slate-300" />
        <p className="text-slate-600">Chưa có kết quả. Chạy huấn luyện xong sẽ hiện ở đây.</p>
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
          text: 'Mô hình vẫn còn tiến bộ ở những vòng cuối — chạy thêm vòng có thể còn tốt hơn.',
        });
      } else if (recentImprovement < -0.02) {
        recs.push({
          type: 'warning',
          text: 'Mô hình bắt đầu học thuộc dữ liệu huấn luyện thay vì hiểu quy luật. Thử giảm số vòng hoặc tăng dropout.',
        });
      }
    }

    if (accuracy >= 0.9) {
      recs.push({
        type: 'success',
        text: 'Đủ tốt để đưa vào dùng thật.',
      });
    } else if (accuracy >= 0.8) {
      recs.push({
        type: 'info',
        text: 'Dùng tạm được. Muốn tốt hơn thì thu thêm video cho những nhãn còn yếu ở mục dưới.',
      });
    } else {
      recs.push({
        type: 'warning',
        text: 'Chưa đủ tốt để dùng thật. Cần thu thêm video, nhất là cho những nhãn điểm thấp ở mục dưới.',
      });
    }

    return recs;
  };

  const recommendations = getRecommendations();

  const hasCheckpoint = !!job?.checkpoint_path;
  const canPromote = isAdmin && !!onPromote && job?.status === 'completed' && !job?.promoted_at;
  const weakClasses = evaluation?.per_class?.filter((c) => c.f1 < 0.5).length ?? 0;
  // null = job không ghi lại cách chia, khác hẳn với "đã chia nhưng bị trùng".
  const signerDisjoint = job?.split_provenance ? job.split_provenance.signer_disjoint : null;
  const durationSeconds = jobDurationSeconds(job);

  return (
    <div className="space-y-6">
      {/* ---------- Phần ai cũng cần đọc ---------- */}

      {/* Kết quả tóm tắt */}
      <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className={`flex h-14 w-14 items-center justify-center rounded-full ${quality.iconBg}`}>
            <CheckCircleIcon className={`h-7 w-7 ${quality.iconColor}`} />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-slate-900">Huấn luyện xong</h2>
            <span className={`mt-2 inline-block rounded-full px-3 py-1 text-xs font-medium ${quality.badgeBg} ${quality.badgeText}`}>
              {quality.level}
            </span>
          </div>
          <div className="mt-2">
            <div className="text-4xl font-bold text-slate-900">{(accuracy * 100).toFixed(1)}%</div>
            <p className="mt-1 text-sm text-slate-500">
              {isTestMetrics ? 'Đoán đúng trên tập kiểm tra cuối' : 'Đoán đúng trên tập kiểm tra giữa chừng (vòng cuối)'}
            </p>
          </div>
        </div>

      </div>

      {/* Giao thức đánh giá: gập lại vì đa số người xem chỉ cần con số, nhưng
          badge trên đầu vẫn nói ngay con số đó đo trên người mới hay người quen
          — thứ quyết định cách đọc kết quả thì không được giấu sau một cú bấm. */}
      <Collapsible
        title="Con số này đo trên ai?"
        description="Cách chia dữ liệu đã tạo ra kết quả bên trên"
        badge={
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
              signerDisjoint === null
                ? 'bg-amber-50 text-amber-800'
                : signerDisjoint
                ? 'bg-emerald-50 text-emerald-800'
                : 'bg-red-50 text-red-700'
            }`}
          >
            {signerDisjoint ? (
              <CheckCircleIcon className="h-3.5 w-3.5" />
            ) : (
              <AlertTriangleIcon className="h-3.5 w-3.5" />
            )}
            {signerDisjoint === null
              ? 'Không rõ cách chia'
              : signerDisjoint
              ? 'Đo trên người mới'
              : 'Đo trên người đã học'}
          </span>
        }
      >
        <SplitProtocolBanner
          provenance={job?.split_provenance}
          splitVersion={job?.config?.split_version}
        />
      </Collapsible>

      {/* Vài chỉ số đi kèm */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Điểm F1"
          value={f1.toFixed(3)}
          unit=""
          description="Cân bằng giữa đoán đúng và bỏ sót"
          color="purple"
        />
        <MetricCard
          label="Thời gian huấn luyện"
          value={durationSeconds === null ? '—' : formatDuration(durationSeconds)}
          unit=""
          description={
            durationSeconds === null
              ? 'Không ghi lại mốc thời gian'
              : `Trung bình ${formatDuration(durationSeconds / Math.max(1, finalMetric.epoch))}/vòng`
          }
          color="indigo"
        />
        <MetricCard
          label="Số vòng đã chạy"
          value={finalMetric.epoch.toString()}
          unit=""
          description={`Đặt trước ${job?.total_epochs || 0} vòng`}
          color="blue"
        />
        <MetricCard
          label="Điểm F1 cao nhất"
          value={bestMetric.val_f1.toFixed(3)}
          unit=""
          description={`Ở vòng thứ ${bestMetric.epoch}`}
          color="emerald"
        />
      </div>

      {/* Việc làm tiếp — trước đây nằm lẫn trong khối "Thông tin model" ở cuối
          trang, nên hai thao tác chính của bước này bị chôn dưới đường dẫn file. */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <h3 className="font-semibold text-slate-900">Việc làm tiếp</h3>

        {hasCheckpoint ? (
          <>
            <p className="mt-1 text-sm text-slate-600">
              Mô hình đã lưu. Thử bằng camera trước khi quyết định có dùng thật hay không.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                onClick={() => setShowTestModal(true)}
                className="inline-flex items-center gap-2 rounded-lg bg-ctu-blue px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-ctu-navy"
              >
                <PlayCircleIcon className="h-4 w-4" />
                Thử bằng camera
              </button>
              {canPromote && (
                <button
                  onClick={async () => {
                    if (!window.confirm('Đưa mô hình này vào trang Nhận dạng? Mọi người dùng sẽ thấy và chọn được nó.')) return;
                    setPromoting(true);
                    setPromoteResult(null);
                    try {
                      setPromoteResult(await onPromote!());
                    } finally {
                      setPromoting(false);
                    }
                  }}
                  disabled={promoting}
                  className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-emerald-700 disabled:opacity-60"
                >
                  <ArrowUpCircleIcon className="h-4 w-4" />
                  {promoting ? 'Đang đưa vào...' : 'Đưa vào trang Nhận dạng'}
                </button>
              )}
            </div>

            {/* Ghi registry và nạp lại realtime là hai việc tách rời: backend
                có thể ghi xong registry nhưng nạp lại thất bại, khi đó máy chủ
                vẫn đang phục vụ model CŨ dù cấu hình đã trỏ sang model mới.
                `promoted_at` được ghi trong cả hai trường hợp, nên nếu chỉ dựa
                vào nó thì lần hỏng một nửa vẫn hiện dải xanh "đã xong" và cảnh
                báo của backend bị nuốt mất — đúng lúc cần đọc nhất. */}
            {promoteResult && !promoteResult.realtime_reloaded ? (
              <div className="mt-3 flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                <AlertTriangleIcon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>
                  {promoteResult.message}
                  {promoteResult.registry_updated && (
                    <>
                      {' '}Trang Nhận dạng vẫn đang chạy mô hình cũ cho tới khi dịch vụ khởi động lại.
                    </>
                  )}
                </span>
              </div>
            ) : promoteResult ? (
              <div className="mt-3 flex items-center gap-1.5 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
                <CheckCircleIcon className="h-3.5 w-3.5 shrink-0" />
                {promoteResult.message}
              </div>
            ) : (
              job?.promoted_at && (
                <div className="mt-3 flex items-center gap-1.5 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
                  <CheckCircleIcon className="h-3.5 w-3.5 shrink-0" />
                  Đã đưa vào trang Nhận dạng lúc {new Date(job.promoted_at).toLocaleString('vi-VN')}
                </div>
              )
            )}
          </>
        ) : (
          <div className="mt-3 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-sm text-amber-900">
            <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" />
            <p>
              Không tìm thấy file mô hình của lần chạy này, nên chưa thử hay đưa vào dùng được.
              Các chỉ số ở trên vẫn đọc bình thường.
            </p>
          </div>
        )}
      </div>

      {/* Nhận xét */}
      <div className="space-y-3">
        <h3 className="font-semibold text-slate-900">Nhận xét</h3>
        {recommendations.map((rec, idx) => {
          const RecIcon = rec.type === 'success' ? CheckCircleIcon : rec.type === 'warning' ? AlertTriangleIcon : InfoCircleIcon;
          return (
            <div
              key={idx}
              className={`flex items-start gap-2.5 rounded-lg border-l-4 p-4 text-sm ${
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

      {/* ---------- Phần chi tiết, mặc định gập lại ---------- */}

      {evaluation?.per_class && evaluation.per_class.length > 0 && (
        <Collapsible
          title="Kết quả theo từng nhãn"
          description="Nhãn nào mô hình làm tốt, nhãn nào còn yếu"
          badge={
            weakClasses > 0 ? (
              <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800">
                {weakClasses} nhãn yếu
              </span>
            ) : (
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
                {evaluation.per_class.length} nhãn
              </span>
            )
          }
        >
          <p className="mb-4 text-xs text-slate-500">
            Xếp từ yếu nhất lên. Nhãn điểm thấp thường là do thiếu mẫu hoặc mẫu thu chưa chuẩn.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                  <th className="py-2 pr-3 font-medium">Nhãn</th>
                  <th className="py-2 px-3 text-right font-medium">Đoán đúng</th>
                  <th className="py-2 px-3 text-right font-medium">Bắt được</th>
                  <th className="py-2 px-3 text-right font-medium">F1</th>
                  <th className="py-2 pl-3 text-right font-medium">Số mẫu</th>
                </tr>
              </thead>
              <tbody>
                {[...evaluation.per_class]
                  .sort((a, b) => a.f1 - b.f1)
                  .map((c) => {
                    const weak = c.f1 < 0.5;
                    return (
                      <tr key={c.class_idx} className={`border-b border-slate-100 ${weak ? 'bg-amber-50' : ''}`}>
                        <td className="py-2 pr-3 font-medium text-slate-800">
                          <span className="inline-flex items-center gap-1.5">
                            {weak && (
                              <AlertTriangleIcon
                                className="h-3.5 w-3.5 shrink-0 text-amber-500"
                                aria-label="Điểm F1 dưới 0.5"
                              />
                            )}
                            {prettyLabel(c.label_key)}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-right tabular-nums text-slate-700">{(c.precision * 100).toFixed(1)}%</td>
                        <td className="py-2 px-3 text-right tabular-nums text-slate-700">{(c.recall * 100).toFixed(1)}%</td>
                        <td className={`py-2 px-3 text-right font-semibold tabular-nums ${weak ? 'text-amber-700' : 'text-slate-900'}`}>
                          {c.f1.toFixed(3)}
                        </td>
                        <td className="py-2 pl-3 text-right tabular-nums text-slate-500">{c.support}</td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </Collapsible>
      )}

      {evaluation?.confusion_matrix && evaluation.labels && (
        <Collapsible
          title="Ma trận nhầm lẫn"
          description="Mô hình hay nhầm nhãn nào với nhãn nào"
        >
          <ConfusionMatrixHeatmap labels={evaluation.labels} matrix={evaluation.confusion_matrix} />
        </Collapsible>
      )}

      {provenance?.available && (
        <Collapsible
          title="Nguồn gốc & khả năng tái lập"
          description="Dữ liệu, mã nguồn và môi trường đã tạo ra mô hình này"
          badge={
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
                provenance.reproducible
                  ? 'bg-emerald-50 text-emerald-800'
                  : 'bg-amber-50 text-amber-800'
              }`}
            >
              {provenance.reproducible ? (
                <CheckCircleIcon className="h-3.5 w-3.5" />
              ) : (
                <AlertTriangleIcon className="h-3.5 w-3.5" />
              )}
              {provenance.reproducible ? 'Tái lập được' : 'Chưa tái lập được'}
            </span>
          }
        >
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <ProvenanceGroup title="Mã nguồn & lần chạy">
              <ProvenanceRow label="Commit" value={provenance.code?.git_commit} mono truncate copyable />
              <ProvenanceRow label="Seed" value={provenance.code?.seed} mono />
              <ProvenanceRow label="Mục đích" value={provenance.code?.run_purpose} />
              <ProvenanceRow label="Tính lặp lại" value={provenance.code?.determinism} />
            </ProvenanceGroup>

            <ProvenanceGroup title="Dữ liệu">
              <ProvenanceRow label="Phiên bản dữ liệu" value={provenance.data?.dataset_version} />
              <ProvenanceRow label="Phiên bản bộ chia" value={provenance.data?.split_version} />
              <ProvenanceRow
                label="Mã kiểm tra"
                value={provenance.data?.dataset_manifest_checksum}
                mono
                truncate
              />
              <ProvenanceRow label="Chuẩn hoá" value={provenance.model?.normalization_version} />
            </ProvenanceGroup>

            <ProvenanceGroup title="Môi trường chạy">
              <ProvenanceRow label="Python" value={provenance.runtime_env?.python_version as string} />
              <ProvenanceRow label="PyTorch" value={provenance.runtime_env?.pytorch_version as string} />
              <ProvenanceRow label="NumPy" value={provenance.runtime_env?.numpy_version as string} />
              <ProvenanceRow label="Thiết bị" value={provenance.runtime_env?.device as string} />
            </ProvenanceGroup>
          </div>

          {provenance.checks && provenance.checks.length > 0 && (
            <div className="mt-4 border-t border-slate-200 pt-3">
              <p className="mb-2 text-xs text-slate-500">
                Điều kiện để kết quả dùng được trong báo cáo
              </p>
              <ul className="space-y-1.5">
                {provenance.checks.map((check) => (
                  <li key={check.id} className="flex items-start gap-2 text-sm">
                    {check.ok ? (
                      <CheckCircleIcon className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                    ) : (
                      <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                    )}
                    <span className={check.ok ? 'text-slate-700' : 'text-amber-900'}>
                      <span className="mr-1.5 font-mono text-xs text-slate-500">{check.id}</span>
                      {check.label}
                      <span className="text-slate-500"> — {check.detail}</span>
                    </span>
                  </li>
                ))}
              </ul>
              {!provenance.reproducible && (
                <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                  Mô hình vẫn dùng để thử được, nhưng chưa đủ dữ kiện để chạy lại y hệt lần này.
                  Không nên lấy con số của nó đưa vào báo cáo.
                </p>
              )}
            </div>
          )}
        </Collapsible>
      )}

      <Collapsible title="Thông tin kỹ thuật" description="Mã phiên chạy, trạng thái và đường dẫn file">
        <div className="space-y-2 text-sm">
          <div className="flex items-center justify-between gap-3">
            <span className="text-slate-600">Mã phiên chạy</span>
            <code className="rounded border border-slate-200 bg-slate-50 px-2 py-1 font-mono text-xs">
              {job?.id}
            </code>
          </div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-slate-600">Trạng thái</span>
            <span className={`rounded px-2 py-1 font-medium ${jobStatusBadge(job?.status).cls}`}>
              {jobStatusBadge(job?.status).text}
            </span>
          </div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-slate-600">Thời gian tạo</span>
            <span className="text-slate-900">
              {job?.created_at
                ? new Date(job.created_at).toLocaleString('vi-VN', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                  })
                : '—'}
            </span>
          </div>
          {hasCheckpoint && (
            <div className="flex flex-col gap-2 border-t border-slate-100 pt-2">
              <span className="text-slate-600">Đường dẫn file mô hình</span>
              <code className="break-all rounded border border-slate-200 bg-slate-50 px-2 py-1 font-mono text-xs">
                {job?.checkpoint_path}
              </code>
              <button
                onClick={() => navigator.clipboard.writeText(job?.checkpoint_path || '')}
                className="inline-flex w-fit items-center gap-1.5 rounded border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-100"
              >
                <CopyIcon className="h-3.5 w-3.5" />
                Sao chép đường dẫn
              </button>
            </div>
          )}
        </div>
      </Collapsible>

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

  // Không tự bọc thẻ card: component này nằm trong một khối đóng/mở đã có
  // khung và tiêu đề riêng, bọc thêm sẽ thành card lồng card.
  return (
    <div>
      <p className="text-xs text-slate-500 mb-4">
        Hàng là nhãn đúng, cột là nhãn mô hình đoán (đánh theo số thứ tự). Màu càng đậm thì tỉ lệ
        càng cao; ô viền đậm trên đường chéo là đoán đúng. Di chuột lên ô để xem chi tiết.
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
