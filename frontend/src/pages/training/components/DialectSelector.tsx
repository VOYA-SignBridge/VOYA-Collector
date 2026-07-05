/**
 * Step 4: Dialect Selector
 * Chọn phương ngữ để huấn luyện
 */

import React, { useState } from 'react';
import DIALECT_LABELS from '../../../config/dialectLabels';

interface Props {
  dialects: Record<string, string[]>;
  selected: string[];
  onChange: (selected: string[]) => void;
}

const DialectSelector: React.FC<Props> = ({ dialects, selected, onChange }) => {
  const [viewMode, setViewMode] = useState<'group' | 'alpha'>('group');
  const allDialects = Object.values(dialects).flat();
  const isAllSelected = selected.length === allDialects.length;
  const isNoneSelected = selected.length === 0;

  const toggleDialect = (dialect: string) => {
    if (selected.includes(dialect)) onChange(selected.filter((d) => d !== dialect));
    else onChange([...selected, dialect]);
  };

  const toggleAll = () => {
    if (isAllSelected) onChange([]);
    else onChange(allDialects);
  };

  return (
    <div className="space-y-6">
      {/* Header and Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wider">
            Chọn Phương Ngữ Để Huấn Luyện
          </h3>
          <p className="mt-1 text-sm text-slate-600">
            Chọn một hoặc nhiều phương ngữ để bao gồm trong quá trình huấn luyện
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* View Mode Toggle */}
          <div className="rounded-lg bg-slate-100 p-1 flex items-center gap-1" role="tablist" aria-label="Chế độ hiển thị">
            <button
              role="tab"
              aria-selected={viewMode === 'group'}
              onClick={() => setViewMode('group')}
              className={`px-3 py-2 rounded text-sm font-medium transition-all ${
                viewMode === 'group'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              📍 Theo Vùng
            </button>
            <button
              role="tab"
              aria-selected={viewMode === 'alpha'}
              onClick={() => setViewMode('alpha')}
              className={`px-3 py-2 rounded text-sm font-medium transition-all ${
                viewMode === 'alpha'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              🔤 Bảng Chữ Cái
            </button>
          </div>

          {/* Select All / Deselect All */}
          <button
            onClick={toggleAll}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              isAllSelected
                ? 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                : 'bg-ctu-blue/10 text-ctu-blue hover:bg-ctu-blue/20'
            }`}
          >
            {isAllSelected ? '✕ Bỏ chọn tất cả' : `✓ Chọn tất cả (${allDialects.length})`}
          </button>
        </div>
      </div>

      {/* Dialect Selection Grid */}
      <div className="space-y-4">
        {viewMode === 'group' ? (
          // Group by Language/Region
          Object.entries(dialects).map(([language, langDialects]) => {
            const GROUP_LABELS: Record<string, string> = {
              'mien-bac': '🌞 Miền Bắc',
              'mien-nam': '🌴 Miền Nam',
              'mien-trung': '⛰️ Miền Trung',
              vi: '🇻🇳 Tiếng Việt',
              default: language,
            };

            const groupLabel = GROUP_LABELS[language] ?? language;
            const groupSelected = langDialects.filter((d) => selected.includes(d)).length;

            return (
              <div key={language} className="rounded-xl border border-slate-200 bg-white p-5">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h4 className="font-semibold text-slate-900">{groupLabel}</h4>
                    <p className="text-xs text-slate-500 mt-1">
                      {langDialects.length} phương ngữ • {groupSelected} được chọn
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {groupSelected === langDialects.length ? (
                      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-emerald-100 text-xs font-medium text-emerald-700">
                        ✓ Đã chọn hết
                      </span>
                    ) : groupSelected > 0 ? (
                      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-ctu-blue/10 text-xs font-medium text-ctu-blue">
                        ◐ {groupSelected} mục
                      </span>
                    ) : null}
                  </div>
                </div>

                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {langDialects.map((dialect) => {
                    const display =
                      DIALECT_LABELS[dialect] ??
                      dialect
                        .replace(/-/g, ' ')
                        .split(' ')
                        .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
                        .join(' ');
                    const isSelected = selected.includes(dialect);

                    return (
                      <button
                        key={dialect}
                        onClick={() => toggleDialect(dialect)}
                        className={`rounded-lg border-2 p-3 text-left transition-all ${
                          isSelected
                            ? 'border-ctu-blue/40 bg-ctu-blue/5 shadow-sm'
                            : 'border-slate-200 bg-white hover:border-slate-300'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <h5 className="font-medium text-slate-900 text-sm">{display}</h5>
                            <p className="text-xs text-slate-500 mt-0.5 truncate">{dialect}</p>
                          </div>
                          <div
                            className={`flex-shrink-0 w-5 h-5 rounded-full border-2 flex items-center justify-center mt-0.5 ${
                              isSelected
                                ? 'border-ctu-blue bg-ctu-blue'
                                : 'border-slate-300 bg-white'
                            }`}
                          >
                            {isSelected && (
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
                    );
                  })}
                </div>
              </div>
            );
          })
        ) : (
          // Alphabetical view
          (() => {
            const map = DIALECT_LABELS;
            const unique = Array.from(new Set(allDialects)).sort(
              (a, b) =>
                (map[a] ?? a.replace(/-/g, ' ')).localeCompare(
                  map[b] ?? b.replace(/-/g, ' '),
                  'vi'
                )
            );

            const groups: Record<string, string[]> = {};
            unique.forEach((d) => {
              const label = map[d] ?? d.replace(/-/g, ' ');
              const first = label.charAt(0).toUpperCase();
              if (!groups[first]) groups[first] = [];
              groups[first].push(d);
            });

            return Object.entries(groups).map(([letter, items]) => (
              <div key={letter} className="rounded-xl border border-slate-200 bg-white p-5">
                <h4 className="font-semibold text-slate-900 mb-4">{letter}</h4>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {items.map((dialect) => {
                    const display = map[dialect] ?? dialect.replace(/-/g, ' ');
                    const isSelected = selected.includes(dialect);

                    return (
                      <button
                        key={dialect}
                        onClick={() => toggleDialect(dialect)}
                        className={`rounded-lg border-2 p-3 text-left transition-all ${
                          isSelected
                            ? 'border-ctu-blue/40 bg-ctu-blue/5 shadow-sm'
                            : 'border-slate-200 bg-white hover:border-slate-300'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <h5 className="font-medium text-slate-900 text-sm">{display}</h5>
                            <p className="text-xs text-slate-500 mt-0.5 truncate">{dialect}</p>
                          </div>
                          <div
                            className={`flex-shrink-0 w-5 h-5 rounded-full border-2 flex items-center justify-center mt-0.5 ${
                              isSelected
                                ? 'border-ctu-blue bg-ctu-blue'
                                : 'border-slate-300 bg-white'
                            }`}
                          >
                            {isSelected && (
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
                    );
                  })}
                </div>
              </div>
            ));
          })()
        )}
      </div>

      {/* Status Message */}
      {isNoneSelected ? (
        <div className="rounded-lg bg-yellow-50 border border-yellow-200 p-4">
          <div className="flex gap-3">
            <span className="text-xl">⚠️</span>
            <div>
              <p className="font-semibold text-yellow-900">Chưa chọn phương ngữ</p>
              <p className="text-sm text-yellow-800 mt-1">
                Vui lòng chọn ít nhất một phương ngữ để có thể bắt đầu huấn luyện.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-4">
          <div className="flex gap-3">
            <span className="text-xl">✓</span>
            <div>
              <p className="font-semibold text-emerald-900">Đã chọn {selected.length} phương ngữ</p>
              <p className="text-sm text-emerald-800 mt-1">
                Mô hình sẽ được huấn luyện sử dụng các phương ngữ đã chọn.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DialectSelector;
