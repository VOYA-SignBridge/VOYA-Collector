export default function EmptyState({ title, description }: { title?: string; description?: string }) {
  return (
    <div className="card flex flex-col items-center justify-center py-8 text-center">
      <div className="text-4xl mb-3">📭</div>
      <h3 className="text-lg font-semibold text-white">{title ?? "No items found"}</h3>
      {description ? <p className="text-sm text-slate-400 mt-2">{description}</p> : null}
    </div>
  );
}
