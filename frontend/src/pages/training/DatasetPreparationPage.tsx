import { useCallback, useEffect, useRef, useState } from 'react';
import { useTrainingAPI } from '../../hooks/useTrainingAPI';
import type { PrepareReport, PreparedSplit } from '../../hooks/useTrainingAPI';
import { dialectName } from '../../config/dialectLabels';
import { AlertTriangleIcon, CheckCircleIcon } from '../../components/ui/Icons';

/**
 * Turning collected recordings into a dataset a model can be trained on.
 *
 * This used to be four command-line tools that had to run in the right order:
 * the manifest has to exist before any split can reference it, and the folds are
 * re-partitioned from the research split rather than the manifest. Anyone who
 * collected data through the platform still needed a terminal to make it
 * trainable, which put the most consequential step of the workflow outside the
 * product.
 *
 * Screen text is deliberately short. The first version explained the reasoning
 * behind every stage, which read as an essay; the people who need this page most
 * are the least likely to read one. Stages are named by what they do, and the
 * only distinction spelled out is the one that changes a decision: which of the
 * two outputs to train on.
 */

const STAGES: Array<{ key: string; title: string }> = [
  { key: 'create_manifest', title: 'Ghi nhận dữ liệu' },
  { key: 'validate_manifest', title: 'Kiểm tra' },
  { key: 'deploy_split', title: 'Chia dữ liệu để huấn luyện' },
  { key: 'strict_split', title: 'Chia dữ liệu để đánh giá' },
  { key: 'loso_folds', title: 'Tạo các lượt đánh giá chéo' },
];

function stageState(report: PrepareReport | null, key: string) {
  if (!report) return 'idle' as const;
  const matches = report.steps.filter((s) => s.step === key || s.step.startsWith(`${key}:`));
  if (matches.length === 0) {
    return report.status === 'failed' ? ('skipped' as const) : ('pending' as const);
  }
  if (matches.some((s) => s.ok === undefined)) return 'running' as const;
  if (matches.every((s) => s.ok)) return 'done' as const;

  // A step can report problems without those problems being disqualifying. The
  // manifest validator is the standing example: it exits non-zero when files on
  // disk are not referenced by the manifest, which is normal here because
  // excluded samples deliberately stay on disk. Painting that red told the user
  // the run had failed while it was in fact finishing successfully.
  return report.status === 'failed' ? ('failed' as const) : ('warning' as const);
}

const DOT: Record<string, string> = {
  idle: 'bg-slate-200',
  pending: 'bg-slate-200',
  running: 'bg-ctu-blue animate-pulse',
  done: 'bg-emerald-500',
  warning: 'bg-amber-500',
  failed: 'bg-red-500',
  skipped: 'bg-slate-300',
};

function SplitCard({ title, note, split, primary }: {
  title: string; note: string; split?: PreparedSplit; primary?: boolean;
}) {
  const counts = split?.counts || {};
  return (
    <div className={`rounded-xl border p-4 ${primary ? 'border-emerald-300 bg-emerald-50/50' : 'border-slate-200 bg-white'}`}>
      <div className="flex items-baseline justify-between gap-2">
        <h4 className="text-sm font-semibold text-slate-900">{title}</h4>
        <span className="text-xs text-slate-500">{split?.num_classes ?? '—'} lớp</span>
      </div>
      <p className="mt-0.5 text-xs text-slate-500">{note}</p>

      {!split?.exists ? (
        <p className="mt-3 text-xs text-slate-400">Chưa tạo</p>
      ) : (
        <div className="mt-3 flex gap-5">
          {(['train', 'val', 'test'] as const).map((k) => (
            <div key={k}>
              <div className="text-lg font-semibold text-slate-900">{counts[k] ?? 0}</div>
              <div className="text-xs text-slate-500">
                {k === 'train' ? 'học' : k === 'val' ? 'dò' : 'chấm'}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

type Props = {
  embedded?: boolean;
  dialects?: string[];
  /** Máy chủ đã có sẵn bộ chia cho phạm vi này từ lần chuẩn bị trước. */
  alreadyPrepared?: boolean;
  /** Báo cho wizard biết đã có dữ liệu chuẩn hoá để đi tiếp hay chưa. */
  onReadyChange?: (ready: boolean) => void;
};

export default function DatasetPreparationPage({
  embedded = false,
  dialects = [],
  alreadyPrepared = false,
  onReadyChange,
}: Props = {}) {
  const { startDatasetPreparation, getDatasetPreparation, error } = useTrainingAPI();
  const [report, setReport] = useState<PrepareReport | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const timer = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (timer.current !== null) {
      window.clearInterval(timer.current);
      timer.current = null;
    }
  }, []);

  useEffect(() => {
    if (!runId) return;
    // Preparation takes minutes; poll rather than block, and stop as soon as the
    // task reports a terminal state so a finished run costs nothing.
    const tick = async () => {
      const r = await getDatasetPreparation(runId);
      if (r) {
        setReport(r);
        if (r.status === 'completed' || r.status === 'failed') stopPolling();
      }
    };
    void tick();
    timer.current = window.setInterval(tick, 3000);
    return stopPolling;
  }, [runId, getDatasetPreparation, stopPolling]);

  const onStart = async () => {
    setStarting(true);
    setReport(null);
    const started = await startDatasetPreparation(dialects.length > 0 ? dialects : undefined);
    setStarting(false);
    if (started) setRunId(started.run_id);
  };

  const running = report?.status === 'running' || report?.status === 'queued' || starting;
  // Tên phương ngữ chứ không phải slug: "Hòa Đê", không phải "hoa-de".
  const scope = dialects.length > 0 ? dialects.map(dialectName).join(', ') : 'Toàn bộ dữ liệu';

  // Bước này coi là xong khi vừa chạy thành công, hoặc khi máy chủ đã có sẵn
  // bộ chia từ lần chuẩn bị trước (`alreadyPrepared`). Báo ngược lên wizard để
  // nút "Tiếp theo" chỉ xuất hiện khi thật sự có dữ liệu chuẩn hoá để đi tiếp.
  const justFinished = report?.status === 'completed';
  const ready = justFinished || alreadyPrepared;

  useEffect(() => {
    onReadyChange?.(ready);
  }, [ready, onReadyChange]);

  return (
    <div className={embedded ? 'space-y-5' : 'mx-auto max-w-3xl space-y-5 p-6'}>
      {!embedded && <h1 className="text-2xl font-semibold text-slate-900">Chuẩn bị dữ liệu</h1>}

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-slate-900">{scope}</p>
            <p className="mt-0.5 text-xs text-slate-500">
              {report?.status === 'completed' && `Xong · ${report.manifest_version}`}
              {report?.status === 'failed' && 'Có bước không chạy được'}
              {report?.status === 'queued' && 'Đang chờ tới lượt'}
              {running && report?.status !== 'queued' && 'Đang chạy, mất vài phút'}
              {!report && !starting && 'Chạy mỗi khi thu thêm dữ liệu mới'}
            </p>
          </div>
          <button
            type="button"
            onClick={onStart}
            disabled={running}
            className="rounded-lg bg-ctu-blue px-4 py-2 text-sm font-medium text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
          >
            {running ? 'Đang chạy…' : ready ? 'Chuẩn hoá lại' : 'Bắt đầu'}
          </button>
        </div>

        {/* Trạng thái sẵn sàng, đặt ngay dưới nút để người dùng biết có đi tiếp
            được chưa mà không phải đoán qua việc nút "Tiếp theo" có hiện hay không. */}
        {ready ? (
          <div className="mt-4 flex items-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2.5 text-sm text-emerald-900">
            <CheckCircleIcon className="mt-0.5 h-4 w-4 shrink-0" />
            <p>
              {justFinished
                ? 'Đã chuẩn hoá xong. Bấm "Tiếp theo" để sang bước kế.'
                : 'Dữ liệu đã được chuẩn hoá từ trước, bấm "Tiếp theo" để đi tiếp. Chỉ cần chuẩn hoá lại nếu bạn vừa thu thêm dữ liệu mới.'}
            </p>
          </div>
        ) : (
          !running && (
            <div className="mt-4 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-sm text-amber-900">
              <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" />
              <p>
                Chưa có dữ liệu chuẩn hoá cho phạm vi này. Bấm <strong>Bắt đầu</strong> để chuẩn hoá
                trước, xong mới đi tiếp được.
              </p>
            </div>
          )
        )}

        {/* Bỏ qua lỗi đọc tiến độ khi chưa có báo cáo nào: lần hỏi đầu tiên có
            thể tới trước khi worker ghi, và báo đỏ lúc đó là báo sai. */}
        {error && report && <p className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        {report?.error && <p className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">{report.error}</p>}

        {(report || starting) && (
          <ol className="mt-5 space-y-3">
            {STAGES.map((stage) => {
              const st = stageState(report, stage.key);
              return (
                <li key={stage.key} className="flex items-center gap-3">
                  <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${DOT[st]}`} />
                  <span className={`text-sm ${st === 'done' || st === 'warning' ? 'text-slate-900' : 'text-slate-500'}`}>
                    {stage.title}
                  </span>
                  {st === 'warning' && <span className="text-xs text-amber-600">có lưu ý</span>}
                  {st === 'failed' && <span className="text-xs text-red-600">lỗi</span>}
                </li>
              );
            })}
          </ol>
        )}
      </div>

      {report && Object.keys(report.artifacts || {}).length > 0 && (
        <div className="space-y-4">
          {Object.entries(report.artifacts).map(([profile, art]) => (
            <div key={profile} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="grid gap-3 md:grid-cols-2">
                <SplitCard
                  primary
                  title="Để huấn luyện"
                  note="Học từ tất cả người ký"
                  split={art.deployment}
                />
                <SplitCard
                  title="Để đánh giá"
                  note="Giữ riêng vài người ký để chấm"
                  split={art.research}
                />
              </div>
              {art.loso?.folds?.length > 0 && (
                <p className="mt-3 text-xs text-slate-500">
                  {art.loso.folds.length} lượt đánh giá chéo
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {report && report.steps.length > 0 && (
        <details className="rounded-xl border border-slate-200 bg-white px-4 py-3">
          <summary className="cursor-pointer text-xs text-slate-500">Chi tiết kỹ thuật</summary>
          {(report.warnings?.length ?? 0) > 0 && (
            <p className="mt-2 text-xs text-amber-700">{report.warnings!.join(' · ')}</p>
          )}
          <ul className="mt-2 space-y-1">
            {report.steps.map((s, i) => (
              <li key={`${s.step}-${i}`}>
                <p className="font-mono text-[11px] text-slate-600">
                  {s.ok === true ? '\u2713' : s.ok === false ? '\u00d7' : '\u2026'} {s.step}
                </p>
                {s.stderr_tail && s.ok === false && (
                  <pre className="mt-1 overflow-x-auto whitespace-pre-wrap text-[11px] text-slate-500">{s.stderr_tail}</pre>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
