export function EmptyState({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="rounded border border-dashed border-slate-700 bg-slate-900/50 p-8 text-center">
      <p className="text-base font-semibold text-slate-100">{title}</p>
      {detail ? <p className="mt-2 text-sm text-slate-400">{detail}</p> : null}
    </div>
  );
}
