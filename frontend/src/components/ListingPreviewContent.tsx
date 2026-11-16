import { createElement, type ReactNode } from "react";
import type { ListingReview, ReviewBlocker } from "../api/listingWorkflow";

const descriptionTags: Record<string, string> = {
  h1: "mt-4 mb-2 text-xl font-semibold", h2: "mt-4 mb-2 text-lg font-semibold",
  h3: "mt-3 mb-2 font-semibold", h4: "mt-3 mb-2 font-semibold",
  h5: "mt-3 font-semibold", h6: "mt-3 font-semibold", p: "my-2",
  br: "", strong: "font-semibold", b: "font-semibold", em: "italic", i: "italic",
  ul: "my-2 list-disc pl-5", ol: "my-2 list-decimal pl-5", li: "my-1",
  table: "my-3 w-full table-fixed", tbody: "", thead: "", tr: "border-b border-slate-300",
  th: "break-words py-2 pr-3 text-left font-semibold", td: "break-words py-2 text-left",
  blockquote: "my-2 border-l-2 border-slate-500 pl-3", div: "", span: "",
};

export function ListingDescription({ html }: { html: string }) {
  function renderNode(node: Node, key: number): ReactNode {
    if (node.nodeType === Node.TEXT_NODE) return node.textContent;
    if (!(node instanceof Element)) return null;
    const tag = node.tagName.toLowerCase();
    if (["script", "style", "iframe", "img", "object", "embed", "video", "audio", "svg", "math", "template"].includes(tag)) return null;
    const children = Array.from(node.childNodes, (child, index) => renderNode(child, index));
    // Rebuild formatting only: no provider HTML attributes, URLs or executable content.
    return Object.prototype.hasOwnProperty.call(descriptionTags, tag)
      ? createElement(tag, { key, className: descriptionTags[tag] }, ...(tag === "br" ? [] : children))
      : children;
  }
  const template = document.createElement("template");
  template.innerHTML = html;
  return <div className="min-w-0 whitespace-pre-wrap break-words" aria-label="Listing description">
    {Array.from(template.content.childNodes, (node, index) => renderNode(node, index))}
  </div>;
}

export function ListingFees({ fees }: { fees: ListingReview["fees"] }) {
  const valid = fees.filter((fee) => Number.isFinite(Number(fee.value)) && Number(fee.value) >= 0);
  const totals = new Map<string, number>();
  for (const fee of valid) totals.set(fee.currency, (totals.get(fee.currency) ?? 0) + Math.round(Number(fee.value) * 100));
  function money(value: number, currency: string) {
    try { return new Intl.NumberFormat("en-AU", { style: "currency", currency }).format(value); }
    catch { return `${currency} ${value.toFixed(2)}`; }
  }
  function name(value: string) { return value.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/_/g, " "); }
  function line(fee: ListingReview["fees"][number], index: number) {
    return <p key={index}>{name(fee.type)}: {money(Number(fee.value), fee.currency)}</p>;
  }
  return <div className="font-sans tabular-nums"><h4 className="font-semibold">eBay listing fee estimate</h4>
    {valid.filter((fee) => Number(fee.value) > 0).map(line)}
    {Array.from(totals, ([currency, cents]) => <p className="font-semibold" key={currency}>{currency} listing fee total: {money(cents / 100, currency)}</p>)}
    <details className="my-2"><summary className="min-h-11 cursor-pointer py-2 font-semibold">Show all fees</summary>{valid.map(line)}</details>
    <p>Listing fees only; final selling fees depend on the sale.</p>
  </div>;
}

export function groupedBlockers(rows: ReviewBlocker[]): ReviewBlocker[] {
  const groups = new Map<string, ReviewBlocker[]>();
  for (const row of rows) {
    const key = row.key === "photo_freshness" ? row.key : JSON.stringify([row.key, row.field, row.message]);
    groups.set(key, [...(groups.get(key) ?? []), row]);
  }
  return Array.from(groups.values(), (group) => {
    const row = group[0];
    const staging = ["staged_drift", "remote_drift", "stage_required", "photo_freshness"].includes(row.key);
    return { ...row, field: staging ? "staging" : row.field,
      message: row.key === "photo_freshness" && group.length > 1 ? `${group.length} photos need re-uploading. Use Update staged offer.` : row.message };
  });
}

export function reviewedTime(value: string) {
  const date = new Date(value);
  return Number.isFinite(date.getTime())
    ? `Reviewed ${new Intl.DateTimeFormat("en-AU", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit", hour12: true }).format(date)}`
    : "Reviewed time unavailable";
}
