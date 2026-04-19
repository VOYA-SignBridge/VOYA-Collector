import type { Filters } from "../../types";

export default function FilterPanel({ filters, setFilters }: { filters: Filters; setFilters: (f: Filters) => void }) {
  return (
    <div className="flex flex-wrap gap-4 bg-gray-50 p-3 border rounded mb-4">
      <input
        placeholder="Lọc theo user"
        className="border p-2 rounded"
        value={filters.user}
        onChange={(e) => setFilters({ ...filters, user: e.target.value })}
      />
      <input
        placeholder="Lọc theo label"
        className="border p-2 rounded"
        value={filters.label}
        onChange={(e) => setFilters({ ...filters, label: e.target.value })}
      />
      <input
        type="date"
        className="border p-2 rounded"
        value={filters.date}
        onChange={(e) => setFilters({ ...filters, date: e.target.value })}
      />
      <button
        className="bg-blue-600 text-white px-4 py-2 rounded"
        onClick={() => setFilters({ user: "", label: "", date: "" })}
      >
        Reset
      </button>
    </div>
  );
}
