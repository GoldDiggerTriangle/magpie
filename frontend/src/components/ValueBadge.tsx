export function ValueBadge({ value, currency }: { value: string | null; currency: string }) {
  if (!value) {
    return <span className="text-sm text-slate-500">No value</span>;
  }

  const numeric = Number(value);
  const formatted = Number.isFinite(numeric)
    ? new Intl.NumberFormat("en-AU", {
        style: "currency",
        currency,
        maximumFractionDigits: 0
      }).format(numeric)
    : `${currency} ${value}`;

  return (
    <span className="inline-flex items-center rounded border border-emerald-400/30 bg-emerald-400/10 px-2 py-0.5 text-sm font-semibold text-emerald-100">
      {formatted}
    </span>
  );
}
