/**
 * Step 3: Augmentation Preview - Professional Layout
 * Displays and configures data augmentation techniques
 */

import React, { useState } from 'react';

type Aug = {
  id: string;
  name: string;
  icon: string;
  description: string;
  benefit: string;
  enabled: boolean;
};

const INITIAL_AUGS: Aug[] = [
  {
    id: 'noise',
    name: 'Thêm Nhiễu',
    icon: '📊',
    description: 'Thêm lệch nhỏ vào tọa độ (±1%)',
    benefit: 'Chống nhạy cảm với các biến động nhỏ',
    enabled: true,
  },
  {
    id: 'rotate',
    name: 'Xoay Góc',
    icon: '🔄',
    description: 'Xoay nhẹ (±5°)',
    benefit: 'Làm việc với nhiều góc camera khác nhau',
    enabled: true,
  },
  {
    id: 'scale',
    name: 'Co Giãn',
    icon: '📏',
    description: 'Thay đổi kích thước (-5% → +5%)',
    benefit: 'Xử lý người cao thấp khác nhau',
    enabled: true,
  },
  {
    id: 'translate',
    name: 'Dịch Chuyển',
    icon: '➡️',
    description: 'Dịch vị trí trong khung (±1.5%)',
    benefit: 'Thích ứng với vị trí tay khác nhau',
    enabled: true,
  },
  {
    id: 'time_mask',
    name: 'Mặt Nạ Thời Gian',
    icon: '🎬',
    description: 'Che khung ngẫu nhiên (15%)',
    benefit: 'Học từ dữ liệu thưa và không liên tục',
    enabled: true,
  },
  {
    id: 'flip',
    name: 'Lật Ngược Tay',
    icon: '🔁',
    description: 'Hoán đổi trái/phải (50%)',
    benefit: 'Xử lý cả tay thuận và tay trái',
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
      {/* Header with Actions */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wider">
            Kỹ Thuật Tăng Cường Dữ Liệu
          </h3>
          <p className="mt-1 text-sm text-slate-600">
            Tạo các biến thể từ dữ liệu gốc để mô hình học tổng quát hơn
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={enableAll}
            className="inline-flex items-center gap-1 rounded-lg bg-ctu-blue/10 px-3 py-2 text-sm font-medium text-ctu-blue hover:bg-ctu-blue/20 transition-colors"
          >
            ✓ Bật Hết
          </button>
          <button
            onClick={disableAll}
            className="inline-flex items-center gap-1 rounded-lg bg-slate-100 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200 transition-colors"
          >
            ✕ Tắt Hết
          </button>
        </div>
      </div>

      {/* Summary Indicator */}
      <div className="rounded-lg bg-ctu-blue/10 border border-ctu-blue/30 p-4">
        <p className="text-sm text-ctu-navy">
          <strong>Đang sử dụng {enabledCount}/{augs.length} kỹ thuật</strong> — Mỗi mẫu sẽ tạo ra ~10 biến thể
        </p>
      </div>

      {/* Augmentation Techniques Grid */}
      <div className="grid gap-4 sm:grid-cols-2">
        {augs.map((aug) => (
          <button
            key={aug.id}
            onClick={() => toggle(aug.id)}
            className={`rounded-xl border-2 p-4 text-left transition-all duration-200 ${
              aug.enabled
                ? 'border-ctu-blue/40 bg-ctu-blue/5 shadow-sm'
                : 'border-slate-200 bg-white hover:border-slate-300'
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-3">
                <div className="text-3xl">{aug.icon}</div>
                <div className="flex-1 min-w-0">
                  <h4 className="font-semibold text-slate-900">{aug.name}</h4>
                  <p className="mt-0.5 text-xs text-slate-600">{aug.description}</p>
                  <p className="mt-2 text-xs font-medium text-ctu-blue">💡 {aug.benefit}</p>
                </div>
              </div>

              <div
                className={`flex-shrink-0 w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                  aug.enabled
                    ? 'border-ctu-blue bg-ctu-blue'
                    : 'border-slate-300 bg-white'
                }`}
              >
                {aug.enabled && (
                  <svg
                    className="w-3 h-3 text-white"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={3}
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                )}
              </div>
            </div>

          </button>
        ))}
      </div>

      {/* Info Section */}
      <div className="rounded-lg bg-slate-50 border border-slate-200 p-5">
        <h4 className="font-semibold text-slate-900 mb-3">Lợi Ích Của Tăng Cường</h4>
        <ul className="space-y-2 text-sm text-slate-700">
          <li className="flex gap-2">
            <span>✓</span>
            <span>
              <strong>Tăng dữ liệu:</strong> Mỗi mẫu gốc tạo ra ~10 biến thể mới
            </span>
          </li>
          <li className="flex gap-2">
            <span>✓</span>
            <span>
              <strong>Cải thiện tổng quát:</strong> Model học các đặc trưng cốt lõi thay vì ghi nhớ
            </span>
          </li>
          <li className="flex gap-2">
            <span>✓</span>
            <span>
              <strong>Linh hoạt hơn:</strong> Xử lý tốt hơn với góc độ, vị trí, kích thước khác nhau
            </span>
          </li>
          <li className="flex gap-2">
            <span>⚠️</span>
            <span>
              <strong>Tính toán:</strong> Tăng thời gian huấn luyện ~ 20-30% (vẫn chấp nhận được)
            </span>
          </li>
        </ul>
      </div>
    </div>
  );
};

export default AugmentationPreview;
