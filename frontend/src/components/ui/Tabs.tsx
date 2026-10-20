/**
 * Thanh tab dùng chung — cho những trang quản trị từng là "một trang dài
 * nhiều bảng và biểu mẫu" (kế hoạch UX 13/09/2026, Đợt 2).
 *
 * Ba điều được bảo đảm ở đây, để mỗi trang không phải tự làm lại:
 *
 * 1. **ARIA đúng**: `role="tablist"` / `role="tab"` / `aria-selected` /
 *    `aria-controls`, và panel mang `role="tabpanel"` + `aria-labelledby`.
 *    Trình đọc màn hình đọc "tab 2 trên 5, Phiên bản, đã chọn".
 * 2. **Bàn phím**: chỉ tab đang chọn nằm trong thứ tự Tab (roving tabindex);
 *    ←/→ (và Home/End) chuyển tab, đúng mẫu WAI-ARIA "Tabs".
 * 3. **Trạng thái nằm ở URL** khi trang truyền `paramName`: F5, back/forward,
 *    và liên kết chia sẻ mở đúng mục. Không có nó, người dùng bị đá về mục
 *    đầu mỗi lần tải lại — một lỗi "chỉ là phiền" cho tới khi nó xảy ra giữa
 *    một thao tác dài.
 *
 * Trên điện thoại thanh cuộn ngang, không xuống dòng — 5 tab xuống thành hai
 * hàng thì không còn giống tab nữa.
 */

import { useCallback, useId, useRef, type KeyboardEvent, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

export interface TabItem<K extends string = string> {
  id: K;
  label: string;
  /** Số nhỏ bên cạnh nhãn (việc chờ, lỗi…). `0`/undefined = không hiện. */
  count?: number;
}

export function useUrlTab<K extends string>(paramName: string, tabs: readonly TabItem<K>[], fallback: K): [K, (k: K) => void] {
  const [params, setParams] = useSearchParams();
  const raw = params.get(paramName);
  const value = (tabs.some((tb) => tb.id === raw) ? raw : fallback) as K;
  const set = useCallback(
    (k: K) => {
      const next = new URLSearchParams(params);
      if (k === fallback) next.delete(paramName);
      else next.set(paramName, k);
      setParams(next, { replace: true });
    },
    [params, setParams, paramName, fallback],
  );
  return [value, set];
}

export default function Tabs<K extends string>({
  tabs,
  value,
  onChange,
  label,
  children,
}: {
  tabs: readonly TabItem<K>[];
  value: K;
  onChange: (k: K) => void;
  /** Tên của cả bộ tab, cho `aria-label` — ví dụ "Mục của trang văn bản". */
  label: string;
  /** Nội dung của tab đang chọn. */
  children: ReactNode;
}) {
  const baseId = useId();
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const idx = tabs.findIndex((tb) => tb.id === value);
    let next = -1;
    if (e.key === "ArrowRight") next = (idx + 1) % tabs.length;
    else if (e.key === "ArrowLeft") next = (idx - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = tabs.length - 1;
    if (next < 0) return;
    e.preventDefault();
    const k = tabs[next].id;
    onChange(k);
    refs.current[k]?.focus();
  };

  return (
    <div>
      <div
        role="tablist"
        aria-label={label}
        onKeyDown={onKeyDown}
        className="-mb-px flex gap-1 overflow-x-auto border-b border-slate-200"
      >
        {tabs.map((tb) => {
          const selected = tb.id === value;
          return (
            <button
              key={tb.id}
              ref={(el) => { refs.current[tb.id] = el; }}
              type="button"
              role="tab"
              id={`${baseId}-tab-${tb.id}`}
              aria-selected={selected}
              aria-controls={`${baseId}-panel-${tb.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(tb.id)}
              className={`inline-flex shrink-0 items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors ${
                selected
                  ? "border-ctu-blue text-ctu-blue"
                  : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-800"
              }`}
            >
              {tb.label}
              {!!tb.count && (
                <span className="rounded-full bg-slate-100 px-1.5 text-xs tabular-nums text-slate-700">{tb.count}</span>
              )}
            </button>
          );
        })}
      </div>
      <div
        role="tabpanel"
        id={`${baseId}-panel-${value}`}
        aria-labelledby={`${baseId}-tab-${value}`}
        className="pt-6"
      >
        {children}
      </div>
    </div>
  );
}
