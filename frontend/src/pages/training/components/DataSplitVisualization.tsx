/**
 * Step 3: how the data is actually partitioned.
 *
 * This step used to show three ratio sliders. They were local state: nothing
 * sent them to the server, and the server has no parameter to receive them —
 * training always runs on the split already generated on disk. The control
 * implied a choice that did not exist, and hid the one fact that changes how
 * the final numbers should be read: whether the same person appears in both
 * training and evaluation. On this dataset that difference is worth +0.129
 * accuracy, so a screen that stays silent about it is misleading in the
 * direction that flatters the result.
 */

import React from 'react';
import type { DatasetInfo, SplitProvenance } from '../../../hooks/useTrainingAPI';
import DIALECT_LABELS from '../../../config/dialectLabels';
import { AlertTriangleIcon, CheckCircleIcon, GraduationCapIcon, SearchIcon } from '../../../components/ui/Icons';

interface Props {
  datasetInfo: DatasetInfo | null;
  // Phương ngữ đã chọn ở bước trước — dùng để nói rõ tập nào sẽ được lọc ra.
  selectedDialects?: string[];
}

const PARTS = [
  {
    key: 'train',
    label: 'Huấn Luyện',
    description: 'Dạy mô hình',
    color: 'from-ctu-blue to-ctu-navy',
    icon: <GraduationCapIcon className="h-7 w-7" />,
  },
  {
    key: 'val',
    label: 'Kiểm Tra',
    description: 'Chọn checkpoint',
    color: 'from-emerald-500 to-emerald-600',
    icon: <CheckCircleIcon className="h-7 w-7" />,
  },
  {
    key: 'test',
    label: 'Đánh Giá',
    description: 'Đo lần cuối',
    color: 'from-amber-500 to-orange-600',
    icon: <SearchIcon className="h-7 w-7" />,
  },
] as const;

const MODE_LABELS: Record<string, string> = {
  strict_signer_disjoint: 'Tách theo người ký',
  strict_user_disjoint: 'Tách theo tài khoản',
  coverage_preserving: 'Giữ độ phủ lớp',
  sample: 'Chia ngẫu nhiên theo mẫu',
};

const DataSplitVisualization: React.FC<Props> = ({ datasetInfo, selectedDialects = [] }) => {
  if (!datasetInfo) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-slate-600">Đang tải thông tin dataset...</p>
      </div>
    );
  }

  const prov: SplitProvenance | undefined = datasetInfo.split_provenance;
  const counts = prov?.counts ?? {};
  const total = PARTS.reduce((s, p) => s + (counts[p.key] ?? 0), 0);

  if (!prov || total === 0) {
    return (
      <div className="rounded-xl border border-amber-300 bg-amber-50 p-5 text-sm text-amber-900">
        <p className="font-semibold">Chưa đọc được cách chia dữ liệu</p>
        <p className="mt-1">
          Máy chủ không trả về thông tin phân chia. Không thể xác nhận người ký có bị
          lẫn giữa tập huấn luyện và tập đánh giá hay không — hãy kiểm tra trước khi
          tin vào con số cuối cùng.
        </p>
        <a
          href="/training/dataset"
          className="mt-3 inline-block rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-medium text-white"
        >
          Chuẩn bị dữ liệu
        </a>
      </div>
    );
  }

  const pct = (n: number) => (total > 0 ? (n / total) * 100 : 0);
  const disjoint = prov.signer_disjoint;

  return (
    <div className="space-y-6">
      {/* Cách chia này do hệ thống quyết định, không phải người dùng.
          Hai khung cũ ở trên (lối tắt "Chuẩn bị dữ liệu" và hộp cảnh báo người
          ký) đã bỏ: bước Chuẩn Bị Dữ Liệu giờ là bước 2 ngay trước đây nên lối
          tắt thành thừa, còn tình trạng trùng người ký rút thành một chip ngay
          cạnh cách chia — vẫn đọc được mà không chiếm nguyên một khung. */}
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wider text-slate-900">
              Cách chia đang áp dụng
            </p>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <p className="text-lg font-bold text-ctu-navy">
                {prov.split_mode ? MODE_LABELS[prov.split_mode] ?? prov.split_mode : 'Không xác định'}
              </p>
              <span
                title={
                  prov.warning ??
                  (disjoint
                    ? 'Không người ký nào xuất hiện ở cả tập huấn luyện và tập đánh giá.'
                    : 'Có người ký xuất hiện ở cả hai tập.')
                }
                className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
                  disjoint
                    ? 'bg-emerald-50 text-emerald-800 ring-1 ring-emerald-200'
                    : 'bg-amber-50 text-amber-800 ring-1 ring-amber-200'
                }`}
              >
                {disjoint ? (
                  <CheckCircleIcon className="h-3.5 w-3.5" />
                ) : (
                  <AlertTriangleIcon className="h-3.5 w-3.5" />
                )}
                {disjoint ? 'Người ký tách riêng' : 'Người ký bị trùng'}
              </span>
            </div>
          </div>
          <div className="text-right text-xs text-slate-500">
            <p>{total.toLocaleString()} mẫu</p>
            {prov.dataset_manifest && (
              <p className="mt-0.5 font-mono">
                {prov.dataset_manifest.replace(/^.*[\\/]/, '')}
              </p>
            )}
          </div>
        </div>

        <p className="mt-3 text-xs text-slate-500">
          Tỉ lệ và thành phần do split đã sinh sẵn quyết định — bước này hiển thị để
          đối chiếu, không chỉnh sửa được tại đây.
          {selectedDialects.length > 0 && (
            <>
              {' '}Khi huấn luyện, dữ liệu sẽ được lọc còn:{' '}
              <span className="font-semibold text-ctu-blue">
                {selectedDialects.map((d) => DIALECT_LABELS[d] ?? d).join(', ')}
              </span>
              .
            </>
          )}
        </p>
      </div>

      {/* Tỉ lệ thật */}
      <div>
        <p className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-900">
          Tỉ Lệ Thực Tế
        </p>
        <div className="flex h-20 w-full overflow-hidden rounded-xl shadow-sm">
          {PARTS.map((p) => {
            const n = counts[p.key] ?? 0;
            const w = pct(n);
            return (
              <div
                key={p.key}
                className={`flex items-center justify-center bg-gradient-to-r ${p.color} text-center text-sm font-semibold text-white`}
                style={{ width: `${w}%` }}
                title={`${p.label}: ${n.toLocaleString()} mẫu`}
              >
                {w > 10 && `${Math.round(w)}%`}
              </div>
            );
          })}
        </div>
      </div>

      {/* Ai nằm ở đâu — phần mà thanh trượt cũ che mất */}
      <div className="grid gap-3 sm:grid-cols-3">
        {PARTS.map((p) => (
          <SplitCard
            key={p.key}
            label={p.label}
            icon={p.icon}
            count={counts[p.key] ?? 0}
            percentage={Math.round(pct(counts[p.key] ?? 0))}
            color={p.color}
            description={p.description}
            signers={prov.signers?.[p.key] ?? []}
          />
        ))}
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
  signers,
}: {
  label: string;
  icon: React.ReactNode;
  count: number;
  percentage: number;
  color: string;
  description: string;
  signers: string[];
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-slate-400">{icon}</div>
          <h4 className="mt-2 font-semibold text-slate-900">{label}</h4>
          <p className="text-xs text-slate-500">{description}</p>
        </div>
        <div
          className={`inline-flex items-center gap-1 rounded-full bg-gradient-to-r ${color} px-2.5 py-1 text-xs font-semibold text-white`}
        >
          {percentage}%
        </div>
      </div>
      <p className="mt-3 text-lg font-bold text-slate-900">{count.toLocaleString()}</p>
      <p className="text-xs text-slate-500">mẫu</p>

      <div className="mt-3 border-t border-slate-100 pt-2">
        <p className="text-[11px] uppercase tracking-wide text-slate-400">
          Người ký ({signers.length})
        </p>
        <p className="mt-1 break-words font-mono text-xs text-slate-700">
          {signers.length > 0 ? signers.join(', ') : '—'}
        </p>
      </div>
    </div>
  );
}

export default DataSplitVisualization;
