/**
 * Step 2: Data Split Visualization - Professional Layout
 * Displays and allows customization of train/validation/test split ratios
 *
 * MIỄN TRỪ khỏi bảng màu trạng thái (`theme/status.ts`). Ba dải màu ở đây là
 * ba CHUỖI DỮ LIỆU (train / validation / test) trên cùng một thanh, không phải
 * ba mức trạng thái. Quy dải "validation" về xanh dương "thành công" sẽ làm nó
 * trùng màu với dải bên cạnh, và người xem mất khả năng đọc tỉ lệ — đúng thứ
 * duy nhất biểu đồ này tồn tại để hiển thị.
 */

import React, { useMemo, useState } from 'react';
import type { DatasetInfo } from '../../../hooks/useTrainingAPI';
import { dialectLabel } from '../../../config/dialectLabels';
import { useI18n } from "../../../i18n";
import {
  CheckCircleIcon,
  GraduationCapIcon,
  InfoCircleIcon,
  SearchIcon,
} from '../../../components/ui/Icons';

interface Props {
  datasetInfo: DatasetInfo | null;
  // Phương ngữ đã chọn ở bước trước — split chỉ áp dụng cho các phương ngữ này.
  selectedDialects?: string[];
}

const clamp = (v: number) => Math.max(0, Math.min(100, Math.round(v)));

const DataSplitVisualization: React.FC<Props> = ({ datasetInfo, selectedDialects = [] }) => {
  const { t } = useI18n();
  if (!datasetInfo) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-slate-600">{t("Đang tải thông tin dataset...")}</p>
      </div>
    );
  }

  // Số mẫu để chia: nếu đã chọn phương ngữ, chỉ tính các phương ngữ đó
  // (khớp đúng dữ liệu sẽ được huấn luyện); nếu chưa chọn, dùng toàn dataset.
  const byDialect = datasetInfo.samples_by_dialect || {};
  const total =
    selectedDialects.length > 0
      ? selectedDialects.reduce((sum, d) => sum + (byDialect[d] || 0), 0)
      : datasetInfo.total_samples;
  const [trainPct, setTrainPct] = useState<number>(70);
  const [valPct, setValPct] = useState<number>(15);

  const testPct = useMemo(() => 100 - clamp(trainPct) - clamp(valPct), [trainPct, valPct]);
  const trainCount = Math.floor((clamp(trainPct) / 100) * total);
  const valCount = Math.floor((clamp(valPct) / 100) * total);
  const testCount = Math.max(0, total - trainCount - valCount);

  return (
    <div className="space-y-6">
      {/* Ngữ cảnh: split áp dụng cho các phương ngữ đã chọn ở bước trước */}
      {selectedDialects.length > 0 && (
        <div className="rounded-lg bg-ctu-blue/5 border border-ctu-blue/20 px-4 py-3 text-sm">
          <span className="text-slate-600">{t("Chia tập cho phương ngữ đã chọn:")} </span>
          <span className="font-semibold text-ctu-blue">
            {selectedDialects.map((d) => dialectLabel(d)).join(', ')}
          </span>
        </div>
      )}

      {/* Controls */}
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-6">
          {t("Điều Chỉnh Tỷ Lệ Chia Tập")}
        </h3>

        <div className="space-y-6">
          {/* Training Split */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label htmlFor="train-split" className="text-sm font-medium text-slate-900">
                {t("Tập Huấn Luyện")}
              </label>
              <span className="text-sm font-semibold text-ctu-blue">{clamp(trainPct)}%</span>
            </div>
            <input
              id="train-split"
              type="range"
              min={0}
              max={100}
              value={trainPct}
              onChange={(e) => setTrainPct(Number(e.target.value))}
              className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-ctu-blue"
            />
            <p className="mt-1 text-xs text-slate-500">
              {trainCount.toLocaleString()} mẫu — dùng để dạy mô hình
            </p>
          </div>

          {/* Validation Split */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label htmlFor="val-split" className="text-sm font-medium text-slate-900">
                {t("Tập Kiểm Tra (Validation)")}
              </label>
              <span className="text-sm font-semibold text-emerald-600">{clamp(valPct)}%</span>
            </div>
            <input
              id="val-split"
              type="range"
              min={0}
              max={100}
              value={valPct}
              onChange={(e) => setValPct(Number(e.target.value))}
              className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-emerald-600"
            />
            <p className="mt-1 text-xs text-slate-500">
              {valCount.toLocaleString()} mẫu — dùng để điều chỉnh mô hình
            </p>
          </div>

          {/* Test Split (Auto) */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-slate-900">
                {t("Tập Đánh Giá (Test)")}
              </label>
              <span className="text-sm font-semibold text-amber-600">{Math.max(0, testPct)}%</span>
            </div>
            <div className="w-full h-2 bg-slate-200 rounded-lg overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-amber-500 to-orange-600"
                style={{ width: `${Math.max(0, testPct)}%` }}
              />
            </div>
            <p className="mt-1 text-xs text-slate-500">
              {testCount.toLocaleString()} mẫu — đo hiệu suất cuối cùng (tính tự động)
            </p>
          </div>
        </div>
      </div>

      {/* Visual Representation */}
      <div>
        <p className="mb-3 text-sm font-semibold text-slate-900 uppercase tracking-wider">
          {t("Hình Ảnh Phân Chia")}
        </p>
        <div className="flex h-20 w-full overflow-hidden rounded-xl shadow-sm">
          <div
            className="flex items-center justify-center bg-gradient-to-r from-ctu-blue to-ctu-navy text-white font-semibold text-sm text-center transition-all duration-300"
            style={{ width: `${clamp(trainPct)}%` }}
            title={t("Train: {p1} mẫu", { p1: trainCount.toLocaleString() })}
          >
            {clamp(trainPct) > 10 && `${clamp(trainPct)}% Train`}
          </div>
          <div
            className="flex items-center justify-center bg-gradient-to-r from-emerald-500 to-emerald-600 text-white font-semibold text-sm text-center transition-all duration-300"
            style={{ width: `${clamp(valPct)}%` }}
            title={t("Validation: {p1} mẫu", { p1: valCount.toLocaleString() })}
          >
            {clamp(valPct) > 10 && `${clamp(valPct)}% Val`}
          </div>
          <div
            className="flex items-center justify-center bg-gradient-to-r from-amber-500 to-orange-600 text-white font-semibold text-sm text-center transition-all duration-300"
            style={{ width: `${Math.max(0, testPct)}%` }}
            title={t("Test: {p1} mẫu", { p1: testCount.toLocaleString() })}
          >
            {Math.max(0, testPct) > 10 && `${Math.max(0, testPct)}% Test`}
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-3 sm:grid-cols-3">
        <SplitCard
          label={t("Huấn Luyện")}
          icon={<GraduationCapIcon className="h-7 w-7" />}
          count={trainCount}
          percentage={clamp(trainPct)}
          color="from-ctu-blue to-ctu-navy"
          description={t("Dạy mô hình")}
        />
        <SplitCard
          label={t("Kiểm Tra")}
          icon={<CheckCircleIcon className="h-7 w-7" />}
          count={valCount}
          percentage={clamp(valPct)}
          color="from-emerald-500 to-emerald-600"
          description={t("Điều chỉnh")}
        />
        <SplitCard
          label={t("Đánh Giá")}
          icon={<SearchIcon className="h-7 w-7" />}
          count={testCount}
          percentage={Math.max(0, testPct)}
          color="from-amber-500 to-orange-600"
          description={t("Kiểm định cuối")}
        />
      </div>

      {/* Info */}
      <div className="rounded-lg bg-ctu-blue/10 border border-ctu-blue/30 p-4 text-sm text-ctu-navy">
        <p className="flex items-center gap-1.5 font-medium">
            <InfoCircleIcon className="h-4 w-4"  aria-hidden="true" />
            {t("Hướng dẫn phân chia")}
          </p>
        <ul className="mt-2 list-inside list-disc space-y-1 text-xs">
          <li>{t("Train (70%): Dùng để huấn luyện mô hình")}</li>
          <li>{t("Validation (15%): Dùng để điều chỉnh hyperparameters")}</li>
          <li>{t("Test (15%): Dùng để đánh giá hiệu suất cuối cùng (không được thay đổi)")}</li>
        </ul>
      </div>
    </div>
  );
};

function SplitCard({
  label,
  icon,
  count,
  percentage,
  color,
  description,
}: {
  label: string;
  icon: React.ReactNode;
  count: number;
  percentage: number;
  color: string;
  description: string;
}) {
  const { t } = useI18n();
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-slate-400">{icon}</div>
          <h4 className="mt-2 font-semibold text-slate-900">{label}</h4>
          <p className="text-xs text-slate-500">{description}</p>
        </div>
        <div className={`inline-flex items-center gap-1 rounded-full bg-gradient-to-r ${color} px-2.5 py-1 text-xs font-semibold text-white`}>
          {percentage}%
        </div>
      </div>
      <p className="mt-3 text-lg font-bold text-slate-900">{count.toLocaleString()}</p>
      <p className="text-xs text-slate-500">{t("mẫu")}</p>
    </div>
  );
}

export default DataSplitVisualization;
