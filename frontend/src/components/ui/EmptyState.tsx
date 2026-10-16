import { InboxIcon } from "./Icons";

export default function EmptyState({ title, description }: { title?: string; description?: string }) {
  return (
    <div className="card flex flex-col items-center justify-center py-8 text-center">
      <InboxIcon className="mx-auto mb-3 h-10 w-10 text-slate-300"  aria-hidden="true" />
      <h3 className="text-lg font-semibold text-slate-800">{title ?? "No items found"}</h3>
      {description ? <p className="text-sm text-slate-500 mt-2">{description}</p> : null}
    </div>
  );
}
