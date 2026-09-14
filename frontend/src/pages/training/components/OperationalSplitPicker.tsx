/**
 * Chọn (hoặc dựng) tập chia vận hành để GHIM cho lượt huấn luyện.
 *
 * Vì sao có nó: không ghim hiện vật thì lượt "thăm dò nhanh" đọc ba tệp nghiên
 * cứu đóng băng ở gốc `processed/splits/` — chúng không khai sàn mẫu, nên cổng
 * huấn luyện từ chối (vd. "lấy chỉ tôm (16 mẫu)") và trước 15/09/2026 mọi lượt
 * bấm từ giao diện đều dừng ở 400. Ghim một hiện vật có sàn, có chủ tổ chức là
 * đường được thiết kế cho việc huấn luyện hằng ngày.
 *
 * "Dựng tập chia mới" là bước "Chuẩn Bị Dữ Liệu" của feature-v2 (Kateht,
 * 17/08) thu về MỘT nút đặt ngay đây, thay vì một trang/bước riêng: người mới
 * chỉ cần biết "chưa có thì bấm dựng, có rồi thì chọn". Máy chủ chạy
 * make_splits.py trên hàng đợi worker; ở đây chỉ hỏi tiến độ mỗi 3 giây.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { OperationalSplit, PreparationReport } from '../../../hooks/useTrainingAPI';
import { useI18n } from '../../../i18n';

interface Props {
  splits: OperationalSplit[];
  loading: boolean;
  selectedDialects: string[];
  value: string | null;
  onChange: (splitId: string | null) => void;
  /** Bắt đầu dựng; trả run_id hoặc null (lỗi đã được hook báo). */
  onPrepare?: (dialects: string[]) => Promise<{ run_id: string } | null>;
  /** Đọc tiến độ một lần dựng. */
  getPreparation?: (runId: string) => Promise<PreparationReport | null>;
  /** Gọi khi dựng xong để tải lại danh sách; nhận split_id vừa dựng để chọn sẵn. */
  onPrepared?: (newSplitIds: string[]) => void;
}

// Tên bước máy chủ → câu người đọc được. Khoá là tiền tố (trước dấu ':').
// @i18n-key-table — giá trị là KHOÁ, dịch tại chỗ dựng.
const STEP_LABEL: Record<string, string> = {
  operational_split: 'Đang chia tập cho phương ngữ',
  create_manifest: 'Đang đóng băng manifest',
  validate_manifest: 'Đang kiểm định manifest',
  research_split: 'Đang chia tập nghiên cứu',
};

const OperationalSplitPicker: React.FC<Props> = ({
  splits, loading, selectedDialects, value, onChange, onPrepare, getPreparation, onPrepared,
}) => {
  const { t } = useI18n();
  const [prep, setPrep] = useState<PreparationReport | null>(null);
  const [preparing, setPreparing] = useState(false);
  const pollRef = useRef<number | null>(null);

  // Chỉ hiện vật phủ ĐÚNG các phương ngữ đã chọn: một hiện vật hoà-đê không
  // dùng được cho lượt bảng-chữ-cái, và một hiện vật gộp hai phương ngữ không
  // phải là lượt "chỉ hoà-đê".
  const matching = useMemo(() => {
    const want = [...selectedDialects].sort().join('|');
    return splits.filter((s) => [...s.dialects].sort().join('|') === want);
  }, [splits, selectedDialects]);

  // Chọn sẵn hiện vật mới nhất (server đã xếp mới nhất lên đầu); bỏ chọn khi
  // hiện vật đang chọn không còn khớp phương ngữ.
  useEffect(() => {
    if (matching.length === 0) {
      if (value !== null) onChange(null);
      return;
    }
    if (!value || !matching.some((s) => s.split_id === value)) onChange(matching[0].split_id);
  }, [matching, value, onChange]);

  useEffect(() => () => { if (pollRef.current) window.clearTimeout(pollRef.current); }, []);

  const startPrepare = useCallback(async () => {
    if (!onPrepare || !getPreparation || preparing) return;
    setPreparing(true);
    setPrep(null);
    const started = await onPrepare(selectedDialects);
    if (!started) {
      setPreparing(false);
      return;
    }
    const tick = async () => {
      const report = await getPreparation(started.run_id);
      if (!report) {
        setPreparing(false);
        return;
      }
      setPrep(report);
      if (report.status === 'completed' || report.status === 'failed') {
        setPreparing(false);
        if (report.status === 'completed') {
          onPrepared?.(report.operational_splits.filter((s) => s.ok).map((s) => s.split_id));
        }
        return;
      }
      pollRef.current = window.setTimeout(tick, 3000);
    };
    tick();
  }, [onPrepare, getPreparation, preparing, selectedDialects, onPrepared]);

  const current = matching.find((s) => s.split_id === value) ?? null;
  const canPrepare = !!onPrepare && !!getPreparation && selectedDialects.length > 0;

  // Một câu tiến độ: bước đang chạy, hoặc kết quả.
  const progressLine = (() => {
    if (!prep) return preparing ? t('Đang gửi yêu cầu…') : null;
    if (prep.status === 'completed') {
      const ok = prep.operational_splits.filter((s) => s.ok).length;
      return t('Đã dựng xong {n} tập chia.', { n: ok });
    }
    if (prep.status === 'failed') return prep.error || t('Dựng tập chia thất bại.');
    const key = (prep.current_step || '').split(':')[0];
    const which = (prep.current_step || '').split(':')[1];
    return `${t(STEP_LABEL[key] || 'Đang xử lý')}${which ? ` ${which}` : ''}… (${prep.steps.length})`;
  })();
  const failedSplits = prep?.status === 'failed' || prep?.status === 'completed'
    ? prep.operational_splits.filter((s) => !s.ok)
    : [];

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5" data-testid="operational-split-picker">
      <label htmlFor="operational-split" className="block text-sm font-semibold text-slate-900">
        {t("Tập chia dùng cho lượt này")}
      </label>
      <p className="mt-1 text-xs text-slate-500">
        {t("Lượt huấn luyện ghim đúng một tập chia đã dựng sẵn (đã lọc lớp thiếu mẫu), để kết quả truy ngược được về dữ liệu.")}
      </p>

      {loading ? (
        <p className="mt-3 text-sm text-slate-500">{t("Đang tải danh sách tập chia…")}</p>
      ) : matching.length === 0 ? (
        <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900" data-testid="operational-split-empty">
          <p className="font-medium">{t("Chưa có tập chia nào cho phương ngữ đã chọn.")}</p>
          <p className="mt-1 text-xs">
            {canPrepare
              ? t("Bấm \"Dựng tập chia mới\" — hệ thống chia dữ liệu hiện có của phương ngữ này (bỏ lớp chưa đủ mẫu) trong khoảng một phút.")
              : t("Quản trị viên dựng một tập bằng lệnh sau (trong container trainer), rồi quay lại bước này:")}
          </p>
          {!canPrepare && (
            /* i18n-ignore-next-line — lệnh máy, không dịch */
            <code className="mt-1 block overflow-x-auto rounded bg-white/70 px-2 py-1 text-[11px] text-slate-800">
              {`python processed/splits/make_splits.py --operational_split_id=${selectedDialects.join('+')}-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-floor25 --tenant_id=<TENANT> --dialects ${selectedDialects.join(',')} --min_samples_per_class=25`}
            </code>
          )}
        </div>
      ) : (
        <>
          <select
            id="operational-split"
            className="mt-3 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-ctu-blue focus:outline-none focus:ring-2 focus:ring-ctu-blue/30"
            value={value ?? ''}
            onChange={(e) => onChange(e.target.value || null)}
          >
            {matching.map((s) => (
              <option key={s.split_id} value={s.split_id}>
                {s.split_id}
              </option>
            ))}
          </select>
          {current && (
            <p className="mt-2 text-xs text-slate-600" data-testid="operational-split-summary">
              {t("{classes} lớp · train {train} / val {val} / test {test} mẫu · sàn {floor} mẫu/lớp", {
                classes: current.num_classes,
                train: current.counts.train,
                val: current.counts.val,
                test: current.counts.test,
                floor: current.min_samples_per_class ?? '—',
              })}
            </p>
          )}
        </>
      )}

      {canPrepare && (
        <div className="mt-4 flex flex-wrap items-center gap-3" data-testid="operational-split-prepare">
          <button
            type="button"
            onClick={startPrepare}
            disabled={preparing}
            className="rounded-lg border border-ctu-blue bg-white px-3 py-2 text-sm font-medium text-ctu-blue hover:bg-ctu-blue/5 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {preparing ? t('Đang dựng…') : t('Dựng tập chia mới')}
          </button>
          {progressLine && (
            <span
              className={`text-xs ${prep?.status === 'failed' ? 'text-red-700' : 'text-slate-600'}`}
              role="status"
              data-testid="operational-split-progress"
            >
              {progressLine}
            </span>
          )}
        </div>
      )}
      {failedSplits.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs text-red-700" data-testid="operational-split-failures">
          {failedSplits.map((s) => (
            <li key={s.dialect}>
              {s.dialect}: {s.error || t('không dựng được')}
            </li>
          ))}
        </ul>
      )}
      {prep?.warnings?.length ? (
        <ul className="mt-2 space-y-1 text-xs text-amber-800">
          {prep.warnings.slice(0, 3).map((w, i) => <li key={i}>{w}</li>)}
        </ul>
      ) : null}
    </div>
  );
};

export default OperationalSplitPicker;
