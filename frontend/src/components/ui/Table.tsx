import type { ReactNode } from "react";
import LoadingSpinner from "./LoadingSpinner";
import EmptyState from "./EmptyState";

export interface TableColumn {
  key: string;
  label: ReactNode;
  className?: string;
  headerClassName?: string;
}

interface TableProps<T> {
  columns: TableColumn[];
  data: T[];
  renderCell: (row: T, columnKey: string) => ReactNode;
  keyExtractor: (row: T, index: number) => string | number;
  loading?: boolean;
  emptyMessage?: string;
  className?: string;
  onRowClick?: (row: T) => void;
}

export default function Table<T>({
  columns,
  data,
  renderCell,
  keyExtractor,
  loading = false,
  emptyMessage = "Không có dữ liệu",
  className = "",
  onRowClick,
}: TableProps<T>) {
  if (loading) {
    return (
      <div className="card flex items-center justify-center py-12">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (data.length === 0) {
    return <EmptyState title={emptyMessage} />;
  }

  return (
    <div className={`overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-md ${className}`}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50/60">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 ${col.headerClassName ?? ""}`}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, index) => (
            <tr
              key={keyExtractor(row, index)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={`border-b border-slate-100 last:border-0 transition-colors ${
                onRowClick ? "cursor-pointer hover:bg-slate-50/80" : "hover:bg-slate-50/40"
              }`}
            >
              {columns.map((col) => (
                <td key={col.key} className={`px-4 py-3 text-slate-700 ${col.className ?? ""}`}>
                  {renderCell(row, col.key)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
