/**
 * Step 5: Training Settings - Professional Layout
 * Configurable hyperparameters with preset option
 */

import React, { useState } from 'react';
import type { ReactNode } from 'react';
import type { ModelType, TrainingConfig } from '../../../hooks/useTrainingAPI';
import { ChipIcon, GraduationCapIcon } from '../../../components/ui/Icons';

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
};

const TrainingSettings: React.FC<Props> = ({ config, onChange }) => {
  const [useDefaults, setUseDefaults] = useState(true);

  const updateConfig = <K extends keyof TrainingConfig>(key: K, value: TrainingConfig[K]) => {
    onChange({ ...config, [key]: value });
  };

  const resetToDefaults = () => {
    onChange({ ...DEFAULT_CONFIG, model_type: config.model_type, dialects: config.dialects, languages: config.languages });
  };

  const architectureGroup = ARCHITECTURE_GROUPS[config.model_type];
  const architectureNote = ARCHITECTURE_NOTES[config.model_type];
  const settingGroups = architectureGroup ? [BASE_GROUP, architectureGroup] : [BASE_GROUP];

  return (
    <div className="space-y-6">
      {/* Model Selection */}
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-1">
            <ChipIcon className="h-6 w-6 text-ctu-blue" />
            <h4 className="font-semibold text-slate-900">Chọn Mô Hình</h4>
          </div>
          <p className="text-xs text-slate-600">Lựa chọn kiến trúc mạng neural cho huấn luyện</p>
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
              <div className="text-xs text-slate-600 mt-1">{model.description}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Mode Toggle */}
      <div className="flex items-center justify-between p-4 rounded-xl bg-gradient-to-r from-ctu-blue/10 to-ctu-navy/5 border border-ctu-blue/30">
        <div>
          <h3 className="font-semibold text-slate-900">Cấu Hình Hyperparameters</h3>
          <p className="mt-1 text-sm text-slate-600">
            Chọn cách bạn muốn cấu hình các thông số huấn luyện
          </p>
        </div>
        <label className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white border border-ctu-blue/30 cursor-pointer hover:bg-ctu-blue/5 transition-colors">
          <input
            type="checkbox"
            checked={useDefaults}
            onChange={(e) => setUseDefaults(e.target.checked)}
            className="w-4 h-4 rounded"
          />
          <span className="text-sm font-medium text-slate-900">Dùng cấu hình mặc định</span>
        </label>
      </div>

      {useDefaults ? (
        // Default Configuration View
        <div className="space-y-4">
          {architectureNote && (
            <div className="rounded-lg bg-amber-50 border border-amber-200 p-4 text-sm text-amber-900">
              ℹ️ {architectureNote}
            </div>
          )}
          {settingGroups.map((group) => (
            <div key={group.title} className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="mb-4">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-ctu-blue">{group.icon}</span>
                  <h4 className="font-semibold text-slate-900">{group.title}</h4>
                </div>
                <p className="text-xs text-slate-600">{group.description}</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {group.settings.map((setting) => {
                  const value = config[setting.key] as number;
                  return (
                    <div key={setting.key} className="p-3 rounded-lg bg-slate-50">
                      <div className="flex items-center justify-between mb-1">
                        <label className="text-xs font-semibold text-slate-900 uppercase tracking-wider">
                          {setting.label}
                        </label>
                        <span className="font-bold text-ctu-blue text-sm">{value}</span>
                      </div>
                      <p className="text-xs text-slate-500">Mặc định: {DEFAULT_CONFIG[setting.key as keyof typeof DEFAULT_CONFIG]}</p>
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
            ✏️ Tùy chỉnh Cấu Hình
          </button>
        </div>
      ) : (
        // Custom Configuration View
        <div className="space-y-4">
          {architectureNote && (
            <div className="rounded-lg bg-amber-50 border border-amber-200 p-4 text-sm text-amber-900">
              ℹ️ {architectureNote}
            </div>
          )}
          {settingGroups.map((group) => (
            <div key={group.title} className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="mb-4 flex items-center gap-2">
                <span className="text-ctu-blue">{group.icon}</span>
                <div>
                  <h4 className="font-semibold text-slate-900">{group.title}</h4>
                  <p className="text-xs text-slate-600">{group.description}</p>
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
                            {setting.label}
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
            ↻ Đặt Lại Cấu Hình Mặc Định
          </button>
        </div>
      )}

      {/* Training Time Estimate */}
      <div className="rounded-lg bg-ctu-blue/10 border border-ctu-blue/30 p-4 text-sm text-ctu-navy">
        <p className="font-medium">⏱️ Thời gian dự kiến</p>
        <p className="mt-1">
          Với cấu hình hiện tại, quá trình huấn luyện sẽ mất khoảng <strong>30-60 phút</strong> tùy
          thuộc vào cấu hình phần cứng của máy.
        </p>
      </div>
    </div>
  );
};

export default TrainingSettings;
