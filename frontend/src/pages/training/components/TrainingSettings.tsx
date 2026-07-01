/**
 * Step 5: Training Settings - Professional Layout
 * Configurable hyperparameters with preset option
 */

import React, { useState } from 'react';
import type { TrainingConfig } from '../../../hooks/useTrainingAPI';

interface Props {
  config: TrainingConfig;
  onChange: (config: TrainingConfig) => void;
}

type SettingGroup = {
  title: string;
  icon: string;
  description: string;
  settings: { key: keyof TrainingConfig; label: string; min: number; max: number; step?: number }[];
};

const SETTING_GROUPS: SettingGroup[] = [
  {
    title: 'Tham số Huấn Luyện',
    icon: '🎓',
    description: 'Điều khiển quá trình học của mô hình',
    settings: [
      { key: 'epochs', label: 'Epochs (Vòng lặp)', min: 10, max: 200, step: 5 },
      { key: 'batch_size', label: 'Batch Size (Kích thước lô)', min: 8, max: 128, step: 8 },
      { key: 'learning_rate', label: 'Learning Rate (Tốc độ học)', min: 0.0001, max: 0.01, step: 0.0001 },
      { key: 'dropout', label: 'Dropout (Ngừng từng phần)', min: 0, max: 0.5, step: 0.05 },
    ],
  },
  {
    title: 'Kiến Trúc TCN (Temporal Convolutional Network)',
    icon: '🏗️',
    description: 'Cấu trúc mạng neural cho xử lý chuỗi thời gian',
    settings: [
      { key: 'channels', label: 'Channels (Kênh)', min: 32, max: 256, step: 16 },
      { key: 'levels', label: 'Levels (Tầng)', min: 1, max: 6 },
      { key: 'kernel_size', label: 'Kernel Size (Cửa sổ)', min: 3, max: 7, step: 2 },
    ],
  },
];

const DEFAULT_CONFIG: TrainingConfig = {
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
    onChange({ ...DEFAULT_CONFIG, dialects: config.dialects, languages: config.languages });
  };

  return (
    <div className="space-y-6">
      {/* Mode Toggle */}
      <div className="flex items-center justify-between p-4 rounded-xl bg-gradient-to-r from-indigo-50 to-cyan-50 border border-indigo-200">
        <div>
          <h3 className="font-semibold text-slate-900">Cấu Hình Hyperparameters</h3>
          <p className="mt-1 text-sm text-slate-600">
            Chọn cách bạn muốn cấu hình các thông số huấn luyện
          </p>
        </div>
        <label className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white border border-indigo-200 cursor-pointer hover:bg-indigo-50 transition-colors">
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
          {SETTING_GROUPS.map((group) => (
            <div key={group.title} className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="mb-4">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-2xl">{group.icon}</span>
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
                        <span className="font-bold text-indigo-600 text-sm">{value}</span>
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
            className="w-full py-3 px-4 rounded-lg border border-indigo-300 bg-indigo-50 text-indigo-700 font-medium hover:bg-indigo-100 transition-colors"
          >
            ✏️ Tùy chỉnh Cấu Hình
          </button>
        </div>
      ) : (
        // Custom Configuration View
        <div className="space-y-4">
          {SETTING_GROUPS.map((group) => (
            <div key={group.title} className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="mb-4 flex items-center gap-2">
                <span className="text-2xl">{group.icon}</span>
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
                          <span className="text-sm font-bold text-indigo-600">{value}</span>
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
                          className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
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
      <div className="rounded-lg bg-blue-50 border border-blue-200 p-4 text-sm text-blue-900">
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
