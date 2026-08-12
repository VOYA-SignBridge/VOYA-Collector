/**
 * Step 6: Training Progress
 * Real-time progress, metrics, và status
 *
 * @i18n-key-table — `title`/`summary`/`reasons`/`actions` của bộ chẩn đoán là
 * KHOÁ từ điển, dịch tại chỗ dựng.
 */

import React, { useEffect, useMemo, useState } from 'react';
import type { TrainingJob, TrainingMetrics } from '../../../hooks/useTrainingAPI';
import LoadingSpinner from '../../../components/ui/LoadingSpinner';
import Button from '../../../components/ui/Button';
import { useI18n } from "../../../i18n";
import {
  BellIcon,
  InfoCircleIcon,
  RepeatIcon,
  StopIcon,
  TimerIcon,
  XCircleIcon,
} from '../../../components/ui/Icons';

interface Props {
  job: TrainingJob;
  metrics: TrainingMetrics[];
  onCancel?: () => Promise<void> | void;
  /** Quay về bước cấu hình (mở khi run đã kết thúc/thất bại). */
  onBack?: () => void;
  /** Chạy lại một run mới với cùng cấu hình. */
  onRetry?: () => void;
  /** Admin thấy chi tiết kỹ thuật/khắc phục; user thường chỉ thấy thông báo gọn. */
  isAdmin?: boolean;
}

// Trạng thái kết thúc: không còn gì để "load" nữa.
const TERMINAL = new Set(['completed', 'failed', 'cancelled']);

const TrainingProgress: React.FC<Props> = ({ job, metrics, onCancel, onBack, onRetry, isAdmin = false }) => {
  const { t } = useI18n();
  const [cancelling, setCancelling] = useState(false);
  const [startTime] = useState<Date>(new Date(job.started_at || new Date()));
  const [elapsedTime, setElapsedTime] = useState('0m');
  const [eta, setEta] = useState('Tính toán...');

  const isFailed = job.status === 'failed';
  const isCancelled = job.status === 'cancelled';
  const isTerminal = TERMINAL.has(job.status);
  const isActive = !isTerminal; // pending | queued | running

  // Update elapsed time and ETA. Freeze the clock once the run is terminal —
  // otherwise a failed/cancelled job keeps ticking as if still training.
  useEffect(() => {
    const compute = () => {
      // A terminal run stops at completed_at; otherwise count up to "now".
      const end = isTerminal && job.completed_at ? new Date(job.completed_at) : new Date();
      const elapsed = Math.max(0, Math.floor((end.getTime() - startTime.getTime()) / 1000));
      const minutes = Math.floor(elapsed / 60);
      const seconds = elapsed % 60;
      setElapsedTime(`${minutes}m ${seconds}s`);

      if (metrics.length > 0 && isActive) {
        const last = metrics[metrics.length - 1];
        const avgTimePerEpoch = elapsed / Math.max(1, last.epoch);
        const remainingEpochs = Math.max(0, job.total_epochs - last.epoch);
        const remainingSeconds = Math.ceil(avgTimePerEpoch * remainingEpochs);
        const remainingMinutes = Math.floor(remainingSeconds / 60);
        setEta(`~${remainingMinutes}m`);
      }
    };

    compute(); // set immediately (also correct when opened straight on a failed job)
    if (!isActive) return;
    // don't keep an interval running for a finished run
    const interval = setInterval(compute, 1000);
    return () => clearInterval(interval);
  }, [startTime, metrics, job.total_epochs, job.completed_at, isActive, isTerminal]);

  const trainLossSeries = useMemo(() => metrics.map((m) => m.train_loss), [metrics]);
  const trainAccSeries = useMemo(() => metrics.map((m) => m.train_acc), [metrics]);
  const valAccSeries = useMemo(() => metrics.map((m) => m.val_acc), [metrics]);

  const latestMetric = metrics[metrics.length - 1];
  const progressPercent = latestMetric ? (latestMetric.epoch / Math.max(1, job.total_epochs)) * 100 : 0;

  // --- Terminal failure / cancel: stop the loading UI and show a clear,
  // actionable error screen instead of a spinner that never resolves. ---------
  if (isFailed || isCancelled) {
    return (
      <TrainingEndState
        cancelled={isCancelled}
        rawError={job.error_message}
        elapsed={elapsedTime}
        epochsDone={latestMetric?.epoch ?? 0}
        totalEpochs={job.total_epochs}
        isAdmin={isAdmin}
        onBack={onBack}
        onRetry={onRetry}
      />
    );
  }

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

  return (
    <div className="space-y-6">
      {/* Header with Timer */}
      <div className="rounded-xl border border-slate-200 bg-gradient-to-br from-slate-50 to-slate-100 p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-slate-900">{t("Đang Huấn Luyện Mô Hình")}</h3>
            <p className="mt-1 text-sm text-slate-600">
              {t("Trạng thái:")} <span className="font-medium text-ctu-blue">{job.status}</span>
            </p>
          </div>
          <div className="text-right">
            <div className="text-sm text-slate-600">
              <div className="flex items-center justify-end gap-1.5">
                <TimerIcon className="h-4 w-4"  aria-hidden="true" />
                {t("Thời gian:")} <strong>{elapsedTime}</strong>
              </div>
              <div className="text-xs text-slate-500 mt-1">ETA: {eta}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-sm font-semibold text-slate-900">{t("Tiến độ huấn luyện")}</h4>
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
        <p className="mt-1 text-xs text-slate-500">
          {t("{pct}% hoàn thành", { pct: Math.round(progressPercent) })}
        </p>
      </div>

      {/* Metrics Cards */}
      {!latestMetric ? (
        <div className="flex items-center justify-center py-12 text-slate-500">
          <LoadingSpinner size="md" label={t("Đang chờ epoch đầu tiên...")} />
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label={t("Mất mát khi huấn luyện")}
            value={latestMetric.train_loss.toFixed(4)}
            trend={metrics.length > 1 && metrics[metrics.length - 2].train_loss > latestMetric.train_loss ? t('Giảm') : t('Tăng')}
            sparkline={renderSparkline(trainLossSeries, '#ef4444')}
            color="red"
            description={t("Mức độ sai lệch trên tập huấn luyện")}
          />
          <MetricCard
            label={t("Độ chính xác trên tập huấn luyện")}
            value={`${(latestMetric.train_acc * 100).toFixed(1)}%`}
            trend={metrics.length > 1 && metrics[metrics.length - 2].train_acc < latestMetric.train_acc ? t('Tăng') : t('Giảm')}
            sparkline={renderSparkline(trainAccSeries, '#10b981')}
            color="green"
            description={t("Độ chính xác trên tập huấn luyện")}
          />
          <MetricCard
            label={t("Độ chính xác trên tập kiểm định")}
            value={`${(latestMetric.val_acc * 100).toFixed(1)}%`}
            trend="KPI Chính"
            sparkline={renderSparkline(valAccSeries, '#0e7bc2')}
            color="blue"
            description={t("Độ chính xác trên tập kiểm tra")}
          />
          <MetricCard
            label={t("Điểm F1")}
            value={latestMetric.val_f1.toFixed(3)}
            trend="Cân bằng"
            sparkline={renderSparkline(trainLossSeries, '#8b5cf6')}
            color="purple"
            description={t("Precision/Recall cân bằng")}
          />
        </div>
      )}

      {/* Recent Epochs History */}
      {metrics.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h4 className="font-semibold text-slate-900 mb-4">{t("Lịch Sử Metrics (5 Epoch Gần Nhất)")}</h4>
          <div className="grid gap-3 sm:grid-cols-5">
            {metrics.slice(-5).map((m) => (
              <div key={m.epoch} className="rounded-lg bg-gradient-to-br from-slate-50 to-slate-100 p-3 text-center border border-slate-200">
                <div className="font-semibold text-slate-900">E{m.epoch}</div>
                <div className="mt-2 space-y-1 text-xs">
                  <div>
                    <span className="text-slate-500">{t("Mất mát:")}</span> <span className="font-bold text-red-600">{m.train_loss.toFixed(3)}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">{t("Kiểm định:")}</span> <span className="font-bold text-ctu-blue">{(m.val_acc * 100).toFixed(1)}%</span>
                  </div>
                  <div>
                    <span className="text-slate-500">F1:</span> <span className="font-bold text-sky-700">{m.val_f1.toFixed(3)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-4">
        {/* Terminal states (failed/cancelled) are handled by TrainingEndState
            above via an early return, so here the run is always in progress. */}
        <div className="rounded-lg bg-ctu-blue/10 border border-ctu-blue/30 p-4 text-sm text-ctu-navy">
          <InfoCircleIcon className="inline h-4 w-4 mr-1.5 -mt-0.5"  aria-hidden="true" />
          {t("Mô hình sẽ được lưu tự động khi huấn luyện hoàn tất.")}
        </div>

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
            {cancelling ? (
              'Đang huỷ…'
            ) : (
              <><StopIcon className="inline h-4 w-4 mr-1.5 -mt-0.5"  aria-hidden="true" /> {t("Huỷ huấn luyện")}</>
            )}
          </Button>
        )}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Terminal state (failed / cancelled)
// ---------------------------------------------------------------------------

interface Diagnosis {
  /** 'system' = lỗi hạ tầng (không phải lỗi user, đã báo admin); 'data' = user tự sửa được. */
  kind: 'system' | 'data';
  title: string;
  summary: string;
  reasons: string[];
  actions: string[];
}

/** Turn a raw backend error string into a human, actionable diagnosis. Keyword
 *  based so a new backend message still lands on a sensible category. Must stay
 *  in sync with the backend classifier (app/training_alerts.py). */
function diagnoseTrainingError(raw?: string): Diagnosis {
  const msg = (raw || '').toLowerCase();

  if (/redis|celery|broker|queue|enqueue|dispatch|gửi được job|connection refused|10061|down/.test(msg)) {
    return {
      kind: 'system',
      title: 'Không gửi được job tới trainer',
      summary:
        'Hệ thống hàng đợi (Redis / Celery) không phản hồi nên job huấn luyện chưa được đưa vào trainer. Chưa có epoch nào chạy.',
      reasons: [
        'Dịch vụ Redis (message broker) đang tắt, khởi động lại hoặc quá tải.',
        'Trainer/worker Celery không chạy hoặc mất kết nối tới Redis.',
        'Cấu hình REDIS_URL / CELERY_BROKER_URL sai hoặc mạng nội bộ gián đoạn.',
      ],
      actions: [
        'Kiểm tra Redis: docker exec voya_redis redis-cli ping (kỳ vọng PONG).',
        'Xem log trainer: docker logs voya_trainer --tail 50.',
        'Khởi động lại dịch vụ nếu cần, sau đó bấm "Thử lại".',
      ],
    };
  }

  if (/no data|không có dữ liệu|dataset|splits|empty|no samples|thiếu dữ liệu|train\.csv|val\.csv|not found/.test(msg)) {
    return {
      kind: 'data',
      title: 'Thiếu dữ liệu huấn luyện',
      summary: 'Không tìm thấy đủ dữ liệu đã xử lý để bắt đầu huấn luyện cho lựa chọn hiện tại.',
      reasons: [
        'Phương ngữ/ngôn ngữ đã chọn chưa có mẫu nào được xử lý (.npz).',
        'Bộ chia train/val/test (splits) chưa được tạo hoặc rỗng.',
        'Dữ liệu vừa thu chưa được đồng bộ xong về máy huấn luyện.',
      ],
      actions: [
        'Quay lại bước chọn phương ngữ và chọn nhãn có dữ liệu.',
        'Kiểm tra bước xử lý/đồng bộ dữ liệu đã hoàn tất chưa.',
        'Sau khi có dữ liệu, bấm "Thử lại".',
      ],
    };
  }

  if (/cuda|gpu|out of memory|oom|memory|vram/.test(msg)) {
    return {
      kind: 'system',
      title: 'Hết tài nguyên phần cứng',
      summary: 'Máy huấn luyện không đủ bộ nhớ (GPU/VRAM hoặc RAM) để chạy cấu hình này.',
      reasons: [
        'Batch size hoặc kích thước mô hình quá lớn so với VRAM khả dụng.',
        'GPU đang bị một job khác chiếm dụng.',
      ],
      actions: [
        'Giảm batch size hoặc số kênh (channels) ở bước cấu hình.',
        'Đợi job khác chạy xong hoặc giải phóng GPU, rồi "Thử lại".',
      ],
    };
  }

  if (/timeout|timed out|hết thời gian|deadline/.test(msg)) {
    return {
      kind: 'system',
      title: 'Quá thời gian chờ',
      summary: 'Quá trình huấn luyện không phản hồi trong thời gian cho phép và đã bị dừng.',
      reasons: ['Trainer bị treo hoặc quá tải.', 'Kết nối tới trainer bị gián đoạn giữa chừng.'],
      actions: ['Xem log trainer để tìm nguyên nhân.', 'Bấm "Thử lại" khi hệ thống đã ổn định.'],
    };
  }

  return {
    kind: 'system',
    title: 'Huấn luyện thất bại',
    summary: raw
      // i18n-ignore-next-line — KHOÁ của bộ chẩn đoán, dịch ở chỗ dựng bằng
      // `t(diag.summary)`; xem `@i18n-key-table` ở đầu tệp.
      ? 'Đã xảy ra lỗi trong quá trình huấn luyện (chi tiết kỹ thuật bên dưới).'
      : 'Đã xảy ra lỗi không xác định trong quá trình huấn luyện.',
    reasons: [
      'Lỗi phát sinh ở phía trainer trong lúc chạy.',
      'Có thể do cấu hình huấn luyện hoặc dữ liệu đầu vào.',
    ],
    actions: [
      'Xem chi tiết kỹ thuật bên dưới và log trainer: docker logs voya_trainer --tail 50.',
      'Điều chỉnh cấu hình nếu cần rồi "Thử lại".',
    ],
  };
}

function TrainingEndState({
  cancelled,
  rawError,
  elapsed,
  epochsDone,
  totalEpochs,
  isAdmin,
  onBack,
  onRetry,
}: {
  cancelled: boolean;
  rawError?: string;
  elapsed: string;
  epochsDone: number;
  totalEpochs: number;
  isAdmin: boolean;
  onBack?: () => void;
  onRetry?: () => void;
}) {
  const { t } = useI18n();
  const diag = cancelled ? null : diagnoseTrainingError(rawError);
  const isSystem = !!diag && diag.kind === 'system';

  // What each audience sees:
  //  - Technical detail (raw error + docker/infra fixes): ADMIN only — it leaks
  //    internals and users can't act on it anyway.
  //  - Causes/fixes grid: admins always; users only for DATA errors they can fix.
  //  - System errors for a normal user collapse to a friendly "admins notified".
  const showTechnical = isAdmin && !!rawError;
  const showCausesFixes = !!diag && (isAdmin || diag.kind === 'data');

  // `t()` bọc NGOÀI cả ba nhánh — hai nhánh đầu là chuỗi thật, nhánh cuối là
  // khoá lấy từ bộ chẩn đoán. Đừng bọc `t()` thêm ở từng nhánh: `t(t(x))` sẽ
  // dịch một lần rồi tra cứu chính bản dịch như một khoá mới, và ngày nào từ
  // điển có đúng chuỗi tiếng Anh đó làm khoá thì nó dịch nhầm lần thứ hai.
  const summary = t(
    cancelled
      ? 'Bạn đã hủy phiên huấn luyện này. Không có mô hình nào được lưu.'
      : isSystem && !isAdmin
        ? 'Hệ thống đang tạm thời gặp sự cố kỹ thuật (không phải do dữ liệu của bạn). Quản trị viên đã được thông báo và sẽ xử lý — vui lòng thử lại sau ít phút.'
        : diag!.summary,
  );

  const tone = cancelled
    ? { ring: 'border-amber-300', head: 'bg-amber-50', badge: 'bg-amber-100 text-amber-800', Icon: StopIcon, title: 'text-amber-900' }
    : { ring: 'border-red-300', head: 'bg-red-50', badge: 'bg-red-100 text-red-800', Icon: XCircleIcon, title: 'text-red-900' };

  // A user should never see infra jargon in the title either.
  const title = t(
    cancelled
      ? 'Huấn luyện đã bị hủy'
      : isSystem && !isAdmin
        ? 'Huấn luyện thất bại do sự cố hệ thống'
        : diag!.title,
  );

  const hasBody = showTechnical || showCausesFixes || isSystem;

  return (
    <div className="space-y-6">
      <div className={`overflow-hidden rounded-xl border ${tone.ring} bg-white shadow-sm`}>
        {/* Header */}
        <div className={`flex items-start gap-4 border-b ${tone.ring} ${tone.head} p-5`}>
          <tone.Icon className="h-7 w-7 shrink-0" aria-hidden="true" />
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className={`text-lg font-semibold ${tone.title}`}>{title}</h3>
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${tone.badge}`}>
                {t("Đã dừng")}
              </span>
            </div>
            <p className="mt-1 text-sm text-slate-600">{summary}</p>
            <p className="mt-2 text-xs text-slate-500">
              <TimerIcon className="inline h-3.5 w-3.5 mr-1 -mt-0.5"  aria-hidden="true" />
              {t("Đã chạy {khi}", { khi: elapsed })}
              {epochsDone > 0
                ? ` • ${t("{n}/{tong} epoch trước khi dừng", { n: epochsDone, tong: totalEpochs })}`
                : ` • ${t("chưa có epoch nào bắt đầu")}`}
            </p>
          </div>
        </div>

        {/* Body */}
        {hasBody && (
          <div className="space-y-5 p-5">
            {/* "admins notified" banner for system failures */}
            {isSystem && (
              <div className="flex items-start gap-2 rounded-lg border border-ctu-blue/30 bg-ctu-blue/5 p-3 text-sm text-ctu-navy">
                <BellIcon className="mt-0.5 h-4 w-4 shrink-0"  aria-hidden="true" />
                <span>
                  {isAdmin
                    ? t('Sự cố hệ thống — đã tự động ghi vào nhật ký quản trị (Security log / Loki) và đếm vào cảnh báo giám sát.')
                    : t('Quản trị viên đã được thông báo tự động về sự cố này.')}
                </span>
              </div>
            )}

            {/* Technical detail — admin only */}
            {showTechnical && (
              <div>
                <h4 className="mb-1 text-sm font-semibold text-slate-800">{t("Chi tiết kỹ thuật")}</h4>
                <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
                  {rawError}
                </pre>
              </div>
            )}

            {/* Likely causes + fixes */}
            {showCausesFixes && diag && (
              <div className="grid gap-5 sm:grid-cols-2">
                <div>
                  <h4 className="mb-2 text-sm font-semibold text-slate-800">{t("Nguyên nhân có thể")}</h4>
                  <ul className="space-y-1.5 text-sm text-slate-600">
                    {diag.reasons.map((r, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="mt-0.5 text-red-500">•</span>
                        <span>{t(r)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4 className="mb-2 text-sm font-semibold text-slate-800">{t("Cách khắc phục")}</h4>
                  <ol className="space-y-1.5 text-sm text-slate-600">
                    {diag.actions.map((a, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="mt-0.5 font-semibold text-ctu-blue">{i + 1}.</span>
                        <span>{t(a)}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Footer actions */}
        <div className={`flex flex-wrap items-center justify-end gap-3 border-t ${tone.ring} bg-slate-50 px-5 py-4`}>
          {onBack && (
            <Button variant="secondary" size="md" onClick={onBack}>
              {t("← Quay về cấu hình")}
            </Button>
          )}
          {onRetry && (
            <Button variant="primary" size="md" onClick={onRetry}>
              <RepeatIcon className="inline h-4 w-4 mr-1.5 -mt-0.5"  aria-hidden="true" />
              {t("Thử lại")}
            </Button>
          )}
        </div>
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
    green: 'border-sky-200 bg-sky-50',
    blue: 'border-ctu-blue/30 bg-ctu-blue/5',
    purple: 'border-purple-200 bg-purple-50',
  };

  const valueClasses = {
    red: 'text-red-600',
    green: 'text-sky-700',
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
