import { useEffect, useState } from "react";
import SessionList from "./SessionList";
import DatasetStats from "./DatasetStats";
import FilterPanel from "./FilterPanel";
import { getSamples } from "../../api/dataset";
import type { Session, Filters } from "../../types";
import ErrorBanner from "../ErrorBanner";

export default function DashboardPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [filters, setFilters] = useState<Filters>({ user: "", label: "", date: "" });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await getSamples();
        if (!mounted) return;
        if (result.ok) setSessions(result.data);
        else setError(result.error);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg || "Failed to load sessions");
      } finally {
        if (mounted) setLoading(false);
      }
    };
    fetchData();
    return () => {
      mounted = false;
    };
  }, [filters]);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">📊 Dataset Management Dashboard</h1>
      {error ? <ErrorBanner message={error} onClose={() => setError(null)} /> : null}
      <FilterPanel filters={filters} setFilters={setFilters} />
      {loading ? (
        <div>Loading sessions…</div>
      ) : (
        <>
          <DatasetStats sessions={sessions} />
          <SessionList sessions={sessions} />
        </>
      )}
    </div>
  );
}
