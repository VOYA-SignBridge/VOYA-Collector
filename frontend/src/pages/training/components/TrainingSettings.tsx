/**
 * Step 5: Training Settings - Professional Layout
 * Configurable hyperparameters with preset option
 *
 * @i18n-key-table — nhãn trong `SETTING_META`, `*_GROUP`, `MODEL_OPTIONS` và
 * `ARCHITECTURE_NOTES` là KHOÁ từ điển, dịch tại chỗ dựng.
 */

import React, { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { useTrainingAPI } from '../../../hooks/useTrainingAPI';
import type { ModelType, ResearchSplit, TrainingConfig } from '../../../hooks/useTrainingAPI';
import { useI18n } from "../../../i18n";
import {
  ChipIcon,
  GraduationCapIcon,
  InfoCircleIcon,
  PencilIcon,
  TimerIcon,
} from '../../../components/ui/Icons';

interface Props {
  config: TrainingConfig;
  onChange: (config: TrainingConfig) => void;
}

type SettingGroup = {
  title: string;
  icon: ReactNode;
  description: string;
  settings: { key: keyof TrainingConfig; label: string; min: number; max: number; step?: number }[];
};

type ModelOption = {
  id: ModelType;
  label: string;
  description: string;
  disabled?: boolean;
};

// Shared slider metadata, keyed by TrainingConfig field
const SETTING_META: Record<string, { label: string; min: number; max: number; step?: number }> = {
  epochs: { label: 'Epochs (Vòng lặp)', min: 10, max: 200, step: 5 },
  batch_size: { label: 'Batch Size (Kích thước lô)', min: 8, max: 128, step: 8 },
  learning_rate: { label: 'Learning Rate (Tốc độ học)', min: 0.0001, max: 0.01, step: 0.0001 },
  dropout: { label: 'Dropout (Ngừng từng phần)', min: 0, max: 0.5, step: 0.05 },
  channels: { label: 'Channels (Kênh)', min: 32, max: 256, step: 16 },
  levels: { label: 'Levels (Tầng)', min: 1, max: 6 },
  kernel_size: { label: 'Kernel Size (Cửa sổ)', min: 3, max: 7, step: 2 },
};

const BASE_GROUP: SettingGroup = {
  title: 'Tham số Huấn Luyện',
  icon: <GraduationCapIcon className="h-6 w-6" />,
  description: 'Điều khiển quá trình học của mô hình',
  settings: (['epochs', 'batch_size', 'learning_rate', 'dropout'] as const).map((key) => ({
    key,
    ...SETTING_META[key],
  })),
};

// Architecture hyperparameters currently wired through the backend CLI.
// Only TCN and CNN accept channels/kernel_size/levels; the other
// architectures (LSTM, BiGRU+Attention, HandGCN) use fixed internal defaults.
const ARCHITECTURE_GROUPS: Partial<Record<ModelType, SettingGroup>> = {
  tcn: {
    title: 'Kiến Trúc TCN (Temporal Convolutional Network)',
    icon: <ChipIcon className="h-6 w-6" />,
    description: 'Cấu trúc mạng neural cho xử lý chuỗi thời gian',
    settings: (['channels', 'levels', 'kernel_size'] as const).map((key) => ({
      key,
      ...SETTING_META[key],
    })),
  },
  cnn: {
    title: 'Kiến Trúc CNN (Convolutional Neural Network)',
    icon: <ChipIcon className="h-6 w-6" />,
    description: 'Số kênh và kích thước cửa sổ tích chập',
    settings: (['channels', 'kernel_size'] as const).map((key) => ({
      key,
      ...SETTING_META[key],
    })),
  },
};

const ARCHITECTURE_NOTES: Partial<Record<ModelType, string>> = {
  lstm: 'LSTM dùng kiến trúc cố định (2 lớp BiLSTM, hidden size 64). Chỉ các tham số huấn luyện ở trên có thể tùy chỉnh.',
  bigru_attention: 'BiGRU + Attention dùng kiến trúc cố định (2 lớp BiGRU, hidden size 64, attention). Chỉ các tham số huấn luyện ở trên có thể tùy chỉnh.',
  hdgcn: 'HandGCN dùng kiến trúc cố định (2 lớp GCN, 64 kênh, temporal 128). Chỉ các tham số huấn luyện ở trên có thể tùy chỉnh.',
};

const MODEL_OPTIONS: ModelOption[] = [
  { id: 'tcn', label: 'TCN', description: 'Temporal Convolutional Network (recommended)' },
  { id: 'cnn', label: 'CNN', description: 'Convolutional Neural Network' },
  { id: 'lstm', label: 'LSTM', description: 'Long Short-Term Memory' },
  { id: 'bigru_attention', label: 'BiGRU + Attention', description: 'Bidirectional GRU with Attention' },
  // id stays 'hdgcn': it is the wire value the API expects and what existing job
  // records store. Only the display name is normalized to HandGCN.
  { id: 'hdgcn', label: 'HandGCN', description: 'Hand Skeleton Graph Convolutional Network' },
];

const DEFAULT_CONFIG: TrainingConfig = {
  model_type: 'tcn',
  dialects: [],
  languages: [],
  epochs: 80,
  batch_size: 32,
  learning_rate: 0.001,
  dropout: 0.3,
  channels: 64,
  levels: 3,
  kernel_size: 5,
  run_purpose: 'smoke_test',
  split_version: null,
};

const TrainingSettings: React.FC<Props> = ({ config, onChange }) => {
  const { t } = useI18n();
  const [useDefaults, setUseDefaults] = useState(true);
  const { getResearchSplits } = useTrainingAPI();
  const [splits, setSplits] = useState<ResearchSplit[]>([]);
  const isResearch = config.run_purpose === 'research';

  useEffect(() => {
    let stale = false;
    getResearchSplits().then((rows) => {
      if (!stale) setSplits(rows);
    });
    return () => {
      stale = true;
    };
  }, [getResearchSplits]);

  const updateConfig = <K extends keyof TrainingConfig>(key: K, value: TrainingConfig[K]) => {
    onChange({ ...config, [key]: value });
  };

  /** Bật/tắt chế độ nghiên cứu. Khi bật, chọn sẵn split đầu tiên để người dùng
   *  không gửi đi một cấu hình thiếu split rồi nhận lỗi 400. */
  const setResearchMode = (on: boolean) => {
    onChange({
      ...config,
      run_purpose: on ? 'research' : 'smoke_test',
      split_version: on ? config.split_version || splits[0]?.split_version || null : null,
    });
  };

  const resetToDefaults = () => {
    onChange({ ...DEFAULT_CONFIG, model_type: config.model_type, dialects: config.dialects, languages: config.languages });
  };

  const architectureGroup = ARCHITECTURE_GROUPS[config.model_type];
  const architectureNote = ARCHITECTURE_NOTES[config.model_type];
  const architectureNoteText = architectureNote ? t(architectureNote) : "";
  const settingGroups = architectureGroup ? [BASE_GROUP, architectureGroup] : [BASE_GROUP];

  return (
    <div className="space-y-6">
      {/* Run purpose — exploratory by default, research when results must be citable */}
      <div className={`rounded-xl border p-5 ${isResearch ? 'border-sky-300 bg-sky-50/50' : 'border-slate-200 bg-white'}`}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h4 className="font-semibold text-slate-900">{t("Chế độ chạy")}</h4>
            <p className="mt-1 text-xs text-slate-600 max-w-xl">
              {isResearch
                ? t('Huấn luyện trên split đã versioned. Checkpoint truy ngược được về đúng phiên bản dữ liệu, nên kết quả trích dẫn được trong báo cáo.')
                : t('Thăm dò nhanh: dựng tập con tạm từ phương ngữ đã chọn. Model dùng được, nhưng không truy ngược được về một phiên bản dữ liệu cố định nên không nên trích dẫn số liệu.')}
            </p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={isResearch}
            onClick={() => setResearchMode(!isResearch)}
            disabled={!isResearch && splits.length === 0}
            className={`shrink-0 inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition ${
              isResearch
                ? 'bg-sky-600 text-white hover:bg-sky-700'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200 disabled:opacity-50 disabled:cursor-not-allowed'
            }`}
          >
            <GraduationCapIcon className="h-4 w-4" />
            {isResearch ? t('Chế độ nghiên cứu: BẬT') : t('Chế độ nghiên cứu: TẮT')}
          </button>
        </div>

        {isResearch && (
          <div className="mt-4">
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
              {t("Split đã versioned")}
            </label>
            <select
              value={config.split_version || ''}
              onChange={(e) => updateConfig('split_version', e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-ctu-blue focus:outline-none"
            >
              {splits.map((s) => (
                <option key={s.split_version} value={s.split_version}>
                  {s.split_version} — {s.num_classes} lớp · train {s.counts.train}/val {s.counts.val}/test {s.counts.test}
                </option>
              ))}
            </select>
            <p className="mt-2 text-xs text-slate-500">
              {t("Split đã định nghĩa sẵn tập dữ liệu, nên lựa chọn phương ngữ ở bước trước không áp dụng cho lần chạy này.")}
            </p>
          </div>
        )}

        {!isResearch && splits.length === 0 && (
          <p className="mt-3 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            {t("Chưa có split nào đủ điều kiện nghiên cứu (cần")} <code className="font-mono">valid_for_research</code>{' '}
            và checksum manifest). Tạo bằng <code className="font-mono">processed/splits/make_splits.py</code>.
          </p>
        )}
      </div>

      {/* Model Selection */}
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-1">
            <ChipIcon className="h-6 w-6 text-ctu-blue" />
            <h4 className="font-semibold text-slate-900">{t("Chọn Mô Hình")}</h4>
          </div>
          <p className="text-xs text-slate-600">{t("Lựa chọn kiến trúc mạng neural cho huấn luyện")}</p>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {MODEL_OPTIONS.map((model) => (
            <button
              key={model.id}
              onClick={() => !model.disabled && updateConfig('model_type', model.id)}
              disabled={model.disabled}
              className={`p-3 rounded-lg border-2 transition-all text-left ${
                config.model_type === model.id
                  ? 'border-ctu-blue bg-ctu-blue/5'
                  : 'border-slate-200 bg-white hover:border-slate-300'
              } ${model.disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              <div className="font-medium text-sm text-slate-900">{model.label}</div>
              <div className="text-xs text-slate-600 mt-1">{t(model.description)}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Mode Toggle */}
      <div className="flex items-center justify-between p-4 rounded-xl bg-gradient-to-r from-ctu-blue/10 to-ctu-navy/5 border border-ctu-blue/30">
        <div>
          <h3 className="font-semibold text-slate-900">{t("Cấu Hình Hyperparameters")}</h3>
          <p className="mt-1 text-sm text-slate-600">
            {t("Chọn cách bạn muốn cấu hình các thông số huấn luyện")}
          </p>
        </div>
        <label className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white border border-ctu-blue/30 cursor-pointer hover:bg-ctu-blue/5 transition-colors">
          <input
            type="checkbox"
            checked={useDefaults}
            onChange={(e) => setUseDefaults(e.target.checked)}
            className="w-4 h-4 rounded"
          />
          <span className="text-sm font-medium text-slate-900">{t("Dùng cấu hình mặc định")}</span>
        </label>
      </div>

      {useDefaults ? (
        // Default Configuration View
        <div className="space-y-4">
          {architectureNote && (
            <div className="rounded-lg bg-amber-50 border border-amber-200 p-4 text-sm text-amber-900">
              <InfoCircleIcon className="inline h-3.5 w-3.5 mr-1 -mt-0.5"  aria-hidden="true" /> {architectureNoteText}
            </div>
          )}
          {settingGroups.map((group) => (
            <div key={group.title} className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="mb-4">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-ctu-blue">{group.icon}</span>
                  <h4 className="font-semibold text-slate-900">{t(group.title)}</h4>
                </div>
                <p className="text-xs text-slate-600">{t(group.description)}</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {group.settings.map((setting) => {
                  const value = config[setting.key] as number;
                  return (
                    <div key={setting.key} className="p-3 rounded-lg bg-slate-50">
                      <div className="flex items-center justify-between mb-1">
                        <label className="text-xs font-semibold text-slate-900 uppercase tracking-wider">
                          {t(setting.label)}
                        </label>
                        <span className="font-bold text-ctu-blue text-sm">{value}</span>
                      </div>
                      <p className="text-xs text-slate-500">
                            {t("Mặc định: {gia_tri}", {
                              gia_tri: String(
                                DEFAULT_CONFIG[
                                  setting.key as keyof typeof DEFAULT_CONFIG
                                ],
                              ),
                            })}
                          </p>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}

          <button
            onClick={() => setUseDefaults(false)}
            className="w-full py-3 px-4 rounded-lg border border-ctu-blue/40 bg-ctu-blue/5 text-ctu-blue font-medium hover:bg-ctu-blue/10 transition-colors"
          >
            <PencilIcon className="inline h-4 w-4 mr-1 -mt-0.5"  aria-hidden="true" /> {t("Tuỳ chỉnh cấu hình")}
          </button>
        </div>
      ) : (
        // Custom Configuration View
        <div className="space-y-4">
          {architectureNote && (
            <div className="rounded-lg bg-amber-50 border border-amber-200 p-4 text-sm text-amber-900">
              <InfoCircleIcon className="inline h-3.5 w-3.5 mr-1 -mt-0.5"  aria-hidden="true" /> {architectureNoteText}
            </div>
          )}
          {settingGroups.map((group) => (
            <div key={group.title} className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="mb-4 flex items-center gap-2">
                <span className="text-ctu-blue">{group.icon}</span>
                <div>
                  <h4 className="font-semibold text-slate-900">{t(group.title)}</h4>
                  <p className="text-xs text-slate-600">{t(group.description)}</p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                {group.settings.map((setting) => {
                  const value = config[setting.key] as number;
                  return (
                    <div key={setting.key}>
                      <label className="block mb-2">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-semibold text-slate-900">
                            {t(setting.label)}
                          </span>
                          <span className="text-sm font-bold text-ctu-blue">{value}</span>
                        </div>
                        <input
                          type="range"
                          min={setting.min}
                          max={setting.max}
                          step={setting.step || 1}
                          value={value}
                          onChange={(e) =>
                            updateConfig(
                              setting.key,
                              Number(e.target.value)
                            )
                          }
                          className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-ctu-blue"
                        />
                      </label>
                      <div className="text-xs text-slate-500 flex justify-between">
                        <span>Min: {setting.min}</span>
                        <span>Max: {setting.max}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}

          <button
            onClick={resetToDefaults}
            className="w-full py-3 px-4 rounded-lg border border-slate-300 bg-white text-slate-700 font-medium hover:bg-slate-50 transition-colors"
          >
            {t("↻ Đặt Lại Cấu Hình Mặc Định")}
          </button>
        </div>
      )}

      {/* Training Time Estimate */}
      <div className="rounded-lg bg-ctu-blue/10 border border-ctu-blue/30 p-4 text-sm text-ctu-navy">
        <p className="flex items-center gap-1.5 font-medium">
            <TimerIcon className="h-4 w-4"  aria-hidden="true" />
            {t("Thời gian dự kiến")}
          </p>
        <p className="mt-1">
          {t("Với cấu hình hiện tại, quá trình huấn luyện sẽ mất khoảng")} <strong>{t("30-60 phút")}</strong> {t("tùy thuộc vào cấu hình phần cứng của máy.")}
        </p>
      </div>
    </div>
  );
};

export default TrainingSettings;
