const statusStyles: Record<string, string> = {
  captured: "border-sky-400/40 bg-sky-400/10 text-sky-200",
  needs_identification: "border-amber-400/40 bg-amber-400/10 text-amber-200",
  needs_cleaning: "border-orange-400/40 bg-orange-400/10 text-orange-200",
  needs_research: "border-violet-400/40 bg-violet-400/10 text-violet-200",
  ready_to_list: "border-emerald-400/40 bg-emerald-400/10 text-emerald-200",
  listed: "border-blue-400/40 bg-blue-400/10 text-blue-200",
  partially_sold: "border-teal-400/40 bg-teal-400/10 text-teal-200",
  sold: "border-lime-400/40 bg-lime-400/10 text-lime-200",
  stored: "border-slate-400/40 bg-slate-400/10 text-slate-200",
  archived: "border-zinc-400/40 bg-zinc-400/10 text-zinc-200",
  in_bulk_lot: "border-fuchsia-400/40 bg-fuchsia-400/10 text-fuchsia-200"
};

export const statusLabels: Record<string, string> = {
  captured: "Captured",
  needs_identification: "Needs ID",
  needs_cleaning: "Needs cleaning",
  needs_research: "Needs research",
  ready_to_list: "Ready",
  listed: "Listed",
  partially_sold: "Partially sold",
  sold: "Sold",
  stored: "Stored",
  archived: "Archived",
  in_bulk_lot: "Bulk lot"
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium ${
        statusStyles[status] ?? "border-slate-500 bg-slate-800 text-slate-200"
      }`}
    >
      {statusLabels[status] ?? status}
    </span>
  );
}

export { statusStyles };
