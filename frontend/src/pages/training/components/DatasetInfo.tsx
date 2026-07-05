/**
 * Step 1: Dataset Info - Professional Layout
 * Displays dataset statistics and overview
 */

import React from 'react';
import type { DatasetInfo as DatasetInfoType } from '../../../hooks/useTrainingAPI';
import LoadingSpinner from '../../../components/ui/LoadingSpinner';

interface Props {
  datasetInfo: DatasetInfoType | null;
  loading: boolean;
}

const DatasetInfo: React.FC<Props> = ({ datasetInfo, loading }) => {
  const dialectCount = datasetInfo ? Object.values(datasetInfo.dialects).flat().length : 0;

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <LoadingSpinner size="lg" />
        <p className="mt-4 text-slate-600">Đang tải thông tin dataset...</p>
      </div>
    );
  }

  if (!datasetInfo) {
    return (
      <div className="rounded-lg bg-red-50 border border-red-200 p-6">
        <div className="flex gap-3">
          <div className="text-2xl">⚠️</div>
          <div>
            <h4 className="font-semibold text-red-900">Không thể tải dataset</h4>
            <p className="mt-1 text-sm text-red-800">
              Vui lòng kiểm tra xem folder dataset có tồn tại và chứa các file CSV cần thiết.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Key Metrics */}
      <div>
        <h3 className="text-sm font-semibold text-slate-600 uppercase tracking-wider mb-3">
          Thống Kê Chính
        </h3>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard label="Tổng mẫu" value={datasetInfo.total_samples} unit="video" />
          <MetricCard label="Classes" value={datasetInfo.total_classes} unit="ký hiệu" />
          <MetricCard label="Ngôn ngữ" value={datasetInfo.languages.length} unit="ngôn ngữ" />
          <MetricCard label="Phương ngữ" value={dialectCount} unit="phương ngữ" />
        </div>
      </div>

      {/* Dataset Distribution */}
      <div className="rounded-xl bg-gradient-to-br from-slate-50 to-slate-100 border border-slate-200 p-6">
        <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-4">
          Phân Bố Theo Phương Ngữ
        </h3>
        <div className="space-y-3">
          {Object.entries(datasetInfo.dialects).map(([lang, dialects]) => (
            <div key={lang}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-slate-900">{lang.toUpperCase()}</span>
                <span className="text-xs text-slate-500">{dialects.length} phương ngữ</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {dialects.map((d) => (
                  <span
                    key={d}
                    className="inline-flex items-center px-2.5 py-1 rounded-md bg-white border border-slate-200 text-xs font-medium text-slate-700 shadow-sm"
                  >
                    {d}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Class Distribution */}
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wider">
            Phân Bố Lớp (Top 10)
          </h3>
          <span className="text-xs text-slate-500">
            Tổng: {datasetInfo.total_samples} mẫu
          </span>
        </div>

        <div className="space-y-4">
          {Object.entries(datasetInfo.class_distribution)
            .sort(([, a], [, b]) => b - a)
            .slice(0, 10)
            .map(([className, count], index) => {
              const display = datasetInfo.label_map?.[className] ?? className;
              const percentage = (count / datasetInfo.total_samples) * 100;

              return (
                <div key={className}>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="flex items-center gap-2 text-sm">
                      <span className="text-xs font-semibold text-slate-500 w-5">#{index + 1}</span>
                      <span className="truncate text-slate-900" title={display}>
                        {display}
                      </span>
                    </label>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-ctu-blue w-12 text-right">
                        {percentage.toFixed(1)}%
                      </span>
                      <span className="text-xs text-slate-500 w-10 text-right">
                        {count}
                      </span>
                    </div>
                  </div>
                  <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-ctu-navy to-ctu-blue transition-all duration-300"
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              );
            })}
        </div>
      </div>

      {/* Info Message */}
      <div className="rounded-lg bg-ctu-blue/10 border border-ctu-blue/30 p-4 text-sm text-ctu-navy">
        <p className="font-medium">ℹ️ Dữ liệu sẵn sàng</p>
        <p className="mt-1">Dataset đã được tải thành công. Hãy tiếp tục để xem chi tiết phân chia tập dữ liệu.</p>
      </div>
    </div>
  );
};

function MetricCard({
  label,
  value,
  unit,
}: {
  label: string;
  value: number | string;
  unit: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 text-center shadow-sm hover:shadow-md transition-shadow">
      <div className="text-2xl font-bold text-transparent bg-gradient-to-br from-ctu-navy to-ctu-blue bg-clip-text">
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
      <div className="mt-1 text-sm font-semibold text-slate-900">{label}</div>
      <div className="text-xs text-slate-500">{unit}</div>
    </div>
  );
}

export default DatasetInfo;
