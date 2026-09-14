/**
 * Chọn tập chia vận hành để GHIM cho lượt huấn luyện.
 *
 * Vì sao có nó: không ghim hiện vật thì lượt "thăm dò nhanh" đọc ba tệp nghiên
 * cứu đóng băng ở gốc `processed/splits/` — chúng không khai sàn mẫu, nên cổng
 * huấn luyện từ chối (vd. "lấy chỉ tôm (16 mẫu)") và trước 15/09/2026 mọi lượt
 * bấm từ giao diện đều dừng ở 400. Ghim một hiện vật do `make_splits.py
 * --operational_split_id` dựng (có sàn, có chủ tổ chức) là đường được thiết kế
 * cho việc huấn luyện hằng ngày.
 *
 * Giữ đơn giản: một ô chọn, chọn sẵn hiện vật mới nhất khớp phương ngữ, một
 * câu nói nó là gì. Ai không có hiện vật thì thấy ngay lệnh cần chạy.
 */
import { useEffect, useMemo } from 'react';
import type { OperationalSplit } from '../../../hooks/useTrainingAPI';
import { useI18n } from '../../../i18n';

interface Props {
  splits: OperationalSplit[];
  loading: boolean;
  selectedDialects: string[];
  value: string | null;
  onChange: (splitId: string | null) => void;
}

const OperationalSplitPicker: React.FC<Props> = ({ splits, loading, selectedDialects, value, onChange }) => {
  const { t } = useI18n();

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

  const current = matching.find((s) => s.split_id === value) ?? null;

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
            {t("Quản trị viên dựng một tập bằng lệnh sau (trong container trainer), rồi quay lại bước này:")}
          </p>
          {/* i18n-ignore-next-line — lệnh máy, không dịch */}
          <code className="mt-1 block overflow-x-auto rounded bg-white/70 px-2 py-1 text-[11px] text-slate-800">
            {`python processed/splits/make_splits.py --operational_split_id=${selectedDialects.join('+')}-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-floor25 --tenant_id=<TENANT> --dialects ${selectedDialects.join(',')} --min_samples_per_class=25`}
          </code>
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
    </div>
  );
};

export default OperationalSplitPicker;
