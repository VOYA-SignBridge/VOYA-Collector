/**
 * Training History — landing view của trang Huấn Luyện (kiểu Roboflow).
 * Gồm: bảng so sánh model tốt nhất theo dialect + lịch sử toàn bộ jobs.
 * Click một job → mở kết quả (Step 7) hoặc tiến độ (Step 6).
 *
 * @i18n-key-table — `STATUS_BADGE` và nhãn phương ngữ là KHOÁ từ điển.
 */

import React, { useMemo } from 'react';
import type { TrainingJobListItem } from '../../../hooks/useTrainingAPI';
import LoadingSpinner from '../../../components/ui/LoadingSpinner';
import { CrownIcon, RocketIcon, TrashIcon } from '../../../components/ui/Icons';
import { useI18n } from "../../../i18n";

interface Props {
  jobs: TrainingJobListItem[];
  loading: boolean;
  onOpenJob: (job: TrainingJobListItem) => void;
  onRefresh: () => void;
  onDeleteJob: (job: TrainingJobListItem) => void;
}

// Chỉ job đã kết thúc mới xóa được — job đang chạy/đang chờ phải hủy trước.
const isDeletable = (status: string) => !['pending', 'queued', 'running'].includes(status);

const STATUS_BADGE: Record<string, { text: string; cls: string }> = {
  queued: { text: 'Đang chờ', cls: 'bg-slate-100 text-slate-700' },
  running: { text: 'Đang chạy', cls: 'bg-ctu-blue/10 text-ctu-blue' },
  completed: { text: 'Hoàn thành', cls: 'bg-sky-50 text-sky-800' },
  failed: { text: 'Thất bại', cls: 'bg-red-50 text-red-700' },
  cancelled: { text: 'Đã hủy', cls: 'bg-amber-50 text-amber-700' },
};

const MODEL_LABELS: Record<string, string> = {
  tcn: 'TCN',
  cnn: 'CNN',
  lstm: 'LSTM',
  bigru_attention: 'BiGRU+Attn',
  hdgcn: 'HandGCN',
  handgcn: 'HandGCN',
};

// Giá trị trả về là KHOÁ, không phải chữ để hiện: chỗ dựng gọi `t(dialectKey(job))`
// (dòng ~193). Bọc `t()` ngay đây sẽ hỏng cả việc gom nhóm ở dòng ~66 lẫn dịch hai lần.
const dialectKey = (job: TrainingJobListItem): string =>
  // i18n-ignore-next-line
  job.config?.dialects?.length ? job.config.dialects.join(' + ') : 'Tất cả';

const fmtDate = (iso?: string): string => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('vi-VN', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
};

const TrainingHistory: React.FC<Props> = ({ jobs, loading, onOpenJob, onRefresh, onDeleteJob }) => {
  const { t } = useI18n();
  // So sánh model theo dialect: chỉ jobs completed có test_acc,
  // mỗi (dialect, model) giữ run tốt nhất
  const comparison = useMemo(() => {
    const byDialect = new Map<string, Map<string, TrainingJobListItem>>();
    for (const job of jobs) {
      if (job.status !== 'completed' || job.test_acc == null) continue;
      const dk = dialectKey(job);
      const model = job.config?.model_type || 'tcn';
      if (!byDialect.has(dk)) byDialect.set(dk, new Map());
      const models = byDialect.get(dk)!;
      const existing = models.get(model);
      if (!existing || (job.test_acc ?? 0) > (existing.test_acc ?? 0)) {
        models.set(model, job);
      }
    }
    return [...byDialect.entries()].map(([dk, models]) => ({
      dialect: dk,
      entries: [...models.values()].sort((a, b) => (b.test_acc ?? 0) - (a.test_acc ?? 0)),
    }));
  }, [jobs]);

  if (loading && jobs.length === 0) {
    return (
      <div className="flex items-center justify-center py-16 text-slate-500">
        <LoadingSpinner size="md" label={t("Đang tải lịch sử training...")} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Model comparison by dialect */}
      {comparison.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6">
          <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-1">
            {t("Model Tốt Nhất Theo Phương Ngữ")}
          </h3>
          <p className="text-xs text-slate-500 mb-4">
            {t("Run tốt nhất của mỗi kiến trúc, trong cùng phương ngữ (chỉ so sánh trong cùng một hàng — khác phương ngữ là khác dữ liệu).")}
          </p>
          <div className="space-y-3">
            {comparison.map(({ dialect, entries }) => (
              <div key={dialect} className="flex flex-wrap items-center gap-2">
                <span className="w-32 flex-shrink-0 text-sm font-medium text-slate-700 truncate" title={dialect}>
                  {dialect}
                </span>
                {entries.map((job, rank) => (
                  <button
                    key={job.id}
                    onClick={() => onOpenJob(job)}
                    title={t("Lượt {id} — {khi}. Bấm để xem chi tiết.", { id: job.id, khi: fmtDate(job.created_at) })}
                    className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition hover:shadow-sm ${
                      rank === 0
                        ? 'border-sky-300 bg-sky-50 text-sky-800'
                        : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    {rank === 0 && <CrownIcon className="h-4 w-4 text-amber-500" aria-hidden="true" />}
                    <span className="font-medium">{MODEL_LABELS[job.config?.model_type || ''] || job.config?.model_type}</span>
                    <span className="tabular-nums">{((job.test_acc ?? 0) * 100).toFixed(1)}%</span>
                    {job.promoted_at && (
                <RocketIcon className="h-4 w-4 text-sky-600" aria-label={t("Đã đưa vào Realtime")} />
              )}
                  </button>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* History table */}
      <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden">
        <div className="flex items-center justify-between px-6 pt-5 pb-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wider">
              {t("Lịch Sử Huấn Luyện")}
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              {t("{n} lượt gần nhất — bấm vào một dòng để xem chi tiết", { n: jobs.length })}
            </p>
          </div>
          <button
            onClick={onRefresh}
            className="text-xs px-3 py-1.5 rounded bg-white border border-slate-300 hover:bg-slate-100 text-slate-700 font-medium transition"
          >
            {t("⟳ Làm mới")}
          </button>
        </div>

        {jobs.length === 0 ? (
          <div className="px-6 pb-8 pt-4 text-center text-sm text-slate-500">
            {t("Chưa có phiên huấn luyện nào. Bấm \"Bắt Đầu Huấn Luyện Mới\" để chạy lần đầu.")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-y border-slate-200 bg-slate-50 text-left text-xs text-slate-500 uppercase">
                  <th className="px-6 py-2.5 font-medium">{t("Thời gian")}</th>
                  <th className="px-3 py-2.5 font-medium">{t("Mô hình")}</th>
                  <th className="px-3 py-2.5 font-medium">{t("Phương ngữ")}</th>
                  <th className="px-3 py-2.5 font-medium text-right">{t("Số vòng")}</th>
                  <th className="px-3 py-2.5 font-medium text-right">{t("Độ chính xác kiểm tra")}</th>
                  <th className="px-3 py-2.5 font-medium text-right">F1</th>
                  <th className="px-3 py-2.5 font-medium">{t("Trạng thái")}</th>
                  <th className="px-6 py-2.5 font-medium">{t("Người chạy")}</th>
                  <th className="px-3 py-2.5 font-medium text-right">{t("Xóa")}</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => {
                  const badge = STATUS_BADGE[job.status] || STATUS_BADGE.queued;
                  const deletable = isDeletable(job.status);
                  return (
                    <tr
                      key={job.id}
                      onClick={() => onOpenJob(job)}
                      className="border-b border-slate-100 cursor-pointer transition hover:bg-ctu-blue/5"
                      title={job.error_message || `Job ${job.id}`}
                    >
                      <td className="px-6 py-3 whitespace-nowrap text-slate-700">{fmtDate(job.created_at)}</td>
                      <td className="px-3 py-3">
                        <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
                          {MODEL_LABELS[job.config?.model_type || ''] || job.config?.model_type || '—'}
                        </span>
                        {job.promoted_at && (
                          <RocketIcon
                className="ml-1.5 inline h-4 w-4 text-sky-600"
                aria-label={t("Đã đưa vào Realtime lúc {p1}", { p1: fmtDate(job.promoted_at) })}
              />
                        )}
                      </td>
                      <td className="px-3 py-3 text-slate-600 max-w-[160px] truncate" title={t(dialectKey(job))}>
                        {t(dialectKey(job))}
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums text-slate-600">
                        {job.status === 'running' ? `${job.current_epoch}/${job.total_epochs}` : job.total_epochs}
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums font-semibold text-slate-900">
                        {job.test_acc != null ? `${(job.test_acc * 100).toFixed(1)}%` : '—'}
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums text-slate-700">
                        {job.test_f1 != null ? job.test_f1.toFixed(3) : '—'}
                      </td>
                      <td className="px-3 py-3">
                        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${badge.cls}`}>
                          {t(badge.text)}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-slate-600">{job.username || '—'}</td>
                      <td className="px-3 py-3 text-right">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (!deletable) return;
                            if (window.confirm(t("Xóa phiên huấn luyện này khỏi lịch sử? Hành động này không thể hoàn tác."))) {
                              onDeleteJob(job);
                            }
                          }}
                          disabled={!deletable}
                          title={deletable ? t('Xóa khỏi lịch sử huấn luyện') : t('Hủy phiên đang chạy trước khi xóa')}
                          className="rounded p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
                        >
                          <TrashIcon className="h-4 w-4"  aria-hidden="true" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default TrainingHistory;
