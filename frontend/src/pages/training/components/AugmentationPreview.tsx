/**
 * Step 3: Augmentation Preview - Professional Layout
 * Displays and configures data augmentation techniques
 *
 * @i18n-key-table — `name`/`description`/`benefit` trong `INITIAL_AUGS` là KHOÁ
 * từ điển, dịch lúc dựng bằng `t(aug.name)`.
 */

import React, { useState } from 'react';
import { Trans, useI18n } from "../../../i18n";
import {
  AlertTriangleIcon,
  ArrowRightIcon,
  ChartBarIcon,
  CheckIcon,
  FilmIcon,
  LightbulbIcon,
  RepeatIcon,
  RulerIcon,
  XIcon,
} from '../../../components/ui/Icons';

type Aug = {
  id: string;
  name: string;
  Icon: (props: { className?: string }) => React.ReactElement;
  description: string;
  benefit: string;
  enabled: boolean;
};

const INITIAL_AUGS: Aug[] = [
  {
    id: 'noise',
    name: 'Thêm Nhiễu',
    Icon: ChartBarIcon,
    description: 'Thêm lệch nhỏ vào tọa độ (±1%)',
    benefit: 'Chống nhạy cảm với các biến động nhỏ',
    enabled: true,
  },
  {
    id: 'rotate',
    name: 'Xoay Góc',
    Icon: RepeatIcon,
    description: 'Xoay nhẹ (±5°)',
    benefit: 'Làm việc với nhiều góc camera khác nhau',
    enabled: true,
  },
  {
    id: 'scale',
    name: 'Co Giãn',
    Icon: RulerIcon,
    description: 'Thay đổi kích thước (-5% → +5%)',
    benefit: 'Xử lý người cao thấp khác nhau',
    enabled: true,
  },
  {
    id: 'translate',
    name: 'Dịch Chuyển',
    Icon: ArrowRightIcon,
    description: 'Dịch vị trí trong khung (±1.5%)',
    benefit: 'Thích ứng với vị trí tay khác nhau',
    enabled: true,
  },
  {
    id: 'time_mask',
    name: 'Mặt Nạ Thời Gian',
    Icon: FilmIcon,
    description: 'Che khung ngẫu nhiên (15%)',
    benefit: 'Học từ dữ liệu thưa và không liên tục',
    enabled: true,
  },
  {
    id: 'flip',
    name: 'Lật Ngược Tay',
    Icon: RepeatIcon,
    description: 'Hoán đổi trái/phải (50%)',
    benefit: 'Xử lý cả tay thuận và tay trái',
    enabled: true,
  },
];

const AugmentationPreview: React.FC = () => {
  const { t } = useI18n();
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
            {t("Kỹ Thuật Tăng Cường Dữ Liệu")}
          </h3>
          <p className="mt-1 text-sm text-slate-600">
            {t("Tạo các biến thể từ dữ liệu gốc để mô hình học tổng quát hơn")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={enableAll}
            className="inline-flex items-center gap-1 rounded-lg bg-ctu-blue/10 px-3 py-2 text-sm font-medium text-ctu-blue hover:bg-ctu-blue/20 transition-colors"
          >
            <CheckIcon className="inline h-3.5 w-3.5 mr-1 -mt-0.5"  aria-hidden="true" /> {t("Bật Hết")}
          </button>
          <button
            onClick={disableAll}
            className="inline-flex items-center gap-1 rounded-lg bg-slate-100 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200 transition-colors"
          >
            <XIcon className="inline h-3.5 w-3.5 mr-1 -mt-0.5"  aria-hidden="true" /> {t("Tắt Hết")}
          </button>
        </div>
      </div>

      {/* Summary Indicator */}
      <div className="rounded-lg bg-ctu-blue/10 border border-ctu-blue/30 p-4">
        <p className="text-sm text-ctu-navy">
          <Trans
            k="{dang_dung} — Mỗi mẫu sẽ tạo ra ~10 biến thể"
            vars={{
              dang_dung: (
                <strong>
                  {t("Đang sử dụng {n}/{tong} kỹ thuật", {
                    n: enabledCount,
                    tong: augs.length,
                  })}
                </strong>
              ),
            }}
          />
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
                <aug.Icon className="h-7 w-7 shrink-0 text-ctu-blue"  aria-hidden="true" />
                <div className="flex-1 min-w-0">
                  <h4 className="font-semibold text-slate-900">{t(aug.name)}</h4>
                  <p className="mt-0.5 text-xs text-slate-600">{t(aug.description)}</p>
                  <p className="mt-2 flex items-start gap-1.5 text-xs font-medium text-ctu-blue">
        <LightbulbIcon className="mt-0.5 h-3.5 w-3.5 shrink-0"  aria-hidden="true" />
        {t(aug.benefit)}
      </p>
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
        <h4 className="font-semibold text-slate-900 mb-3">{t("Lợi Ích Của Tăng Cường")}</h4>
        <ul className="space-y-2 text-sm text-slate-700">
          <li className="flex gap-2">
            <CheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600"  aria-hidden="true" />
            <span>
              <strong>{t("Tăng dữ liệu:")}</strong> {t("Mỗi mẫu gốc tạo ra ~10 biến thể mới")}
            </span>
          </li>
          <li className="flex gap-2">
            <CheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600"  aria-hidden="true" />
            <span>
              <strong>{t("Cải thiện tổng quát:")}</strong> {t("Model học các đặc trưng cốt lõi thay vì ghi nhớ")}
            </span>
          </li>
          <li className="flex gap-2">
            <CheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600"  aria-hidden="true" />
            <span>
              <strong>{t("Linh hoạt hơn:")}</strong> {t("Xử lý tốt hơn với góc độ, vị trí, kích thước khác nhau")}
            </span>
          </li>
          <li className="flex gap-2">
            <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0 text-amber-600"  aria-hidden="true" />
            <span>
              <strong>{t("Tính toán:")}</strong> {t("Tăng thời gian huấn luyện ~ 20-30% (vẫn chấp nhận được)")}
            </span>
          </li>
        </ul>
      </div>
    </div>
  );
};

export default AugmentationPreview;
