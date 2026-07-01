/**
 * Step 2: Data Split Visualization - Professional Layout
 * Displays and allows customization of train/validation/test split ratios
 */

import React, { useMemo, useState } from 'react';
import type { DatasetInfo } from '../../../hooks/useTrainingAPI';

interface Props {
  datasetInfo: DatasetInfo | null;
}

const clamp = (v: number) => Math.max(0, Math.min(100, Math.round(v)));

const DataSplitVisualization: React.FC<Props> = ({ datasetInfo }) => {
  if (!datasetInfo) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-slate-600">Đang tải thông tin dataset...</p>
      </div>
    );
  }

  const total = datasetInfo.total_samples;
  const [trainPct, setTrainPct] = useState<number>(70);
  const [valPct, setValPct] = useState<number>(15);

  const testPct = useMemo(() => 100 - clamp(trainPct) - clamp(valPct), [trainPct, valPct]);
  const trainCount = Math.floor((clamp(trainPct) / 100) * total);
  const valCount = Math.floor((clamp(valPct) / 100) * total);
  const testCount = Math.max(0, total - trainCount - valCount);

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-6">
          Điều Chỉnh Tỷ Lệ Chia Tập
        </h3>

        <div className="space-y-6">
          {/* Training Split */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label htmlFor="train-split" className="text-sm font-medium text-slate-900">
                🎓 Tập Huấn Luyện
              </label>
              <span className="text-sm font-semibold text-indigo-600">{clamp(trainPct)}%</span>
            </div>
            <input
              id="train-split"
              type="range"
              min={0}
              max={100}
              value={trainPct}
              onChange={(e) => setTrainPct(Number(e.target.value))}
              className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
            />
            <p className="mt-1 text-xs text-slate-500">
              {trainCount.toLocaleString()} mẫu — dùng để dạy mô hình
            </p>
          </div>

          {/* Validation Split */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label htmlFor="val-split" className="text-sm font-medium text-slate-900">
                ✅ Tập Kiểm Tra (Validation)
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
                🔍 Tập Đánh Giá (Test)
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
          Hình Ảnh Phân Chia
        </p>
        <div className="flex h-20 w-full overflow-hidden rounded-xl shadow-sm">
          <div
            className="flex items-center justify-center bg-gradient-to-r from-indigo-500 to-indigo-600 text-white font-semibold text-sm text-center transition-all duration-300"
            style={{ width: `${clamp(trainPct)}%` }}
            title={`Train: ${trainCount.toLocaleString()} mẫu`}
          >
            {clamp(trainPct) > 10 && `${clamp(trainPct)}% Train`}
          </div>
          <div
            className="flex items-center justify-center bg-gradient-to-r from-emerald-500 to-emerald-600 text-white font-semibold text-sm text-center transition-all duration-300"
            style={{ width: `${clamp(valPct)}%` }}
            title={`Validation: ${valCount.toLocaleString()} mẫu`}
          >
            {clamp(valPct) > 10 && `${clamp(valPct)}% Val`}
          </div>
          <div
            className="flex items-center justify-center bg-gradient-to-r from-amber-500 to-orange-600 text-white font-semibold text-sm text-center transition-all duration-300"
            style={{ width: `${Math.max(0, testPct)}%` }}
            title={`Test: ${testCount.toLocaleString()} mẫu`}
          >
            {Math.max(0, testPct) > 10 && `${Math.max(0, testPct)}% Test`}
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-3 sm:grid-cols-3">
        <SplitCard
          label="Huấn Luyện"
          emoji="🎓"
          count={trainCount}
          percentage={clamp(trainPct)}
          color="from-indigo-500 to-indigo-600"
          description="Dạy mô hình"
        />
        <SplitCard
          label="Kiểm Tra"
          emoji="✅"
          count={valCount}
          percentage={clamp(valPct)}
          color="from-emerald-500 to-emerald-600"
          description="Điều chỉnh"
        />
        <SplitCard
          label="Đánh Giá"
          emoji="🔍"
          count={testCount}
          percentage={Math.max(0, testPct)}
          color="from-amber-500 to-orange-600"
          description="Kiểm định cuối"
        />
      </div>

      {/* Info */}
      <div className="rounded-lg bg-blue-50 border border-blue-200 p-4 text-sm text-blue-900">
        <p className="font-medium">ℹ️ Hướng dẫn phân chia</p>
        <ul className="mt-2 list-inside list-disc space-y-1 text-xs">
          <li>Train (70%): Dùng để huấn luyện mô hình</li>
          <li>Validation (15%): Dùng để điều chỉnh hyperparameters</li>
          <li>Test (15%): Dùng để đánh giá hiệu suất cuối cùng (không được thay đổi)</li>
        </ul>
      </div>
    </div>
  );
};

function SplitCard({
  label,
  emoji,
  count,
  percentage,
  color,
  description,
}: {
  label: string;
  emoji: string;
  count: number;
  percentage: number;
  color: string;
  description: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-2xl">{emoji}</div>
          <h4 className="mt-2 font-semibold text-slate-900">{label}</h4>
          <p className="text-xs text-slate-500">{description}</p>
        </div>
        <div className={`inline-flex items-center gap-1 rounded-full bg-gradient-to-r ${color} px-2.5 py-1 text-xs font-semibold text-white`}>
          {percentage}%
        </div>
      </div>
      <p className="mt-3 text-lg font-bold text-slate-900">{count.toLocaleString()}</p>
      <p className="text-xs text-slate-500">mẫu</p>
    </div>
  );
}

export default DataSplitVisualization;
