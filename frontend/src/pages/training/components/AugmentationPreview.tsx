/**
 * Step 4: Tăng cường dữ liệu.
 *
 * Mỗi kỹ thuật là một thẻ bật/tắt. Phần "vì sao cần" nằm ngay trong thẻ thay vì
 * dồn xuống một khung tổng kết riêng ở cuối trang — người dùng đọc lý do đúng
 * lúc đang cân nhắc bật hay tắt kỹ thuật đó.
 */

import React, { useState } from 'react';
import type { ReactNode } from 'react';
import {
  CheckIcon,
  FilmIcon,
  MirrorIcon,
  MoveIcon,
  RotateIcon,
  ScaleIcon,
  WaveIcon,
  XIcon,
} from '../../../components/ui/Icons';

type Aug = {
  id: string;
  name: string;
  icon: ReactNode;
  description: string;
  benefit: string;
  enabled: boolean;
};

const AUG_ICON_CLASS = 'h-5 w-5';

const INITIAL_AUGS: Aug[] = [
  {
    id: 'noise',
    name: 'Thêm nhiễu',
    icon: <WaveIcon className={AUG_ICON_CLASS} />,
    description: 'Lệch nhẹ toạ độ (±1%)',
    benefit: 'Tay run hoặc camera rung không làm sai kết quả',
    enabled: true,
  },
  {
    id: 'rotate',
    name: 'Xoay góc',
    icon: <RotateIcon className={AUG_ICON_CLASS} />,
    description: 'Xoay nhẹ (±5°)',
    benefit: 'Nhận được cả khi camera đặt hơi nghiêng',
    enabled: true,
  },
  {
    id: 'scale',
    name: 'Co giãn',
    icon: <ScaleIcon className={AUG_ICON_CLASS} />,
    description: 'Đổi kích thước (−5% → +5%)',
    benefit: 'Người ngồi gần hay xa camera đều nhận được',
    enabled: true,
  },
  {
    id: 'translate',
    name: 'Dịch chuyển',
    icon: <MoveIcon className={AUG_ICON_CLASS} />,
    description: 'Dời vị trí trong khung (±1.5%)',
    benefit: 'Tay đặt lệch trái hay lệch phải đều nhận được',
    enabled: true,
  },
  {
    id: 'time_mask',
    name: 'Che khung hình',
    icon: <FilmIcon className={AUG_ICON_CLASS} />,
    description: 'Bỏ ngẫu nhiên 15% số khung',
    benefit: 'Vẫn nhận ra khi vài khung hình bị mất hoặc mờ',
    enabled: true,
  },
  {
    id: 'flip',
    name: 'Đổi tay',
    icon: <MirrorIcon className={AUG_ICON_CLASS} />,
    description: 'Hoán đổi trái/phải (50%)',
    benefit: 'Người thuận tay trái ký cũng nhận được',
    enabled: true,
  },
];

const AugmentationPreview: React.FC = () => {
  const [augs, setAugs] = useState<Aug[]>(INITIAL_AUGS);

  const toggle = (id: string) => {
    setAugs((prev) => prev.map((a) => (a.id === id ? { ...a, enabled: !a.enabled } : a)));
  };

  const enableAll = () => setAugs((prev) => prev.map((a) => ({ ...a, enabled: true })));
  const disableAll = () => setAugs((prev) => prev.map((a) => ({ ...a, enabled: false })));

  const enabledCount = augs.filter((a) => a.enabled).length;

  return (
    <div className="space-y-6">
      {/* Header + thao tác nhanh */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-slate-900">Tăng cường dữ liệu</h3>
          <p className="mt-1 text-sm text-slate-600">
            Tạo thêm biến thể từ video đã thu, để mô hình quen với nhiều điều kiện quay khác nhau.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={enableAll}
            className="inline-flex items-center gap-1.5 rounded-lg bg-ctu-blue/10 px-3 py-2 text-sm font-medium text-ctu-blue transition-colors hover:bg-ctu-blue/20"
          >
            <CheckIcon className="h-4 w-4" />
            Bật hết
          </button>
          <button
            onClick={disableAll}
            className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-200"
          >
            <XIcon className="h-4 w-4" />
            Tắt hết
          </button>
        </div>
      </div>

      <div className="rounded-lg border border-ctu-blue/30 bg-ctu-blue/10 px-4 py-3 text-sm text-ctu-navy">
        Đang bật <strong>{enabledCount}/{augs.length}</strong> kỹ thuật. Mỗi video gốc sinh ra khoảng
        10 biến thể, nên thời gian huấn luyện tăng chừng 20–30%.
      </div>

      {/* Danh sách kỹ thuật */}
      <div className="grid gap-4 sm:grid-cols-2">
        {augs.map((aug) => (
          <button
            key={aug.id}
            onClick={() => toggle(aug.id)}
            aria-pressed={aug.enabled}
            className={`rounded-xl border-2 p-4 text-left transition-all duration-200 ${
              aug.enabled
                ? 'border-ctu-blue/40 bg-ctu-blue/5 shadow-sm'
                : 'border-slate-200 bg-white hover:border-slate-300'
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-start gap-3">
                <span
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${
                    aug.enabled ? 'bg-ctu-blue/10 text-ctu-blue' : 'bg-slate-100 text-slate-400'
                  }`}
                >
                  {aug.icon}
                </span>
                <div className="min-w-0 flex-1">
                  <h4 className="font-semibold text-slate-900">{aug.name}</h4>
                  <p className="mt-0.5 text-xs text-slate-500">{aug.description}</p>
                  <p className="mt-2 text-xs text-slate-600">{aug.benefit}</p>
                </div>
              </div>

              <span
                className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 ${
                  aug.enabled ? 'border-ctu-blue bg-ctu-blue' : 'border-slate-300 bg-white'
                }`}
              >
                {aug.enabled && <CheckIcon className="h-3 w-3 text-white" />}
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
};

export default AugmentationPreview;
