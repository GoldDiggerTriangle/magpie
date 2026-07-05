import { useMutation, useQuery } from "@tanstack/react-query";
import { ClipboardCopy, Copy, Download, PackageOpen } from "lucide-react";
import { useState } from "react";

import { downloadItemPhotoZip } from "../api/items";
import { getItemCopyPack } from "../api/listing";
import type { CopyPack, InventoryItemDetail } from "../types";

const channelOptions: Array<{ value: CopyPack["channel"]; label: string }> = [
  { value: "ebay", label: "eBay" },
  { value: "facebook_marketplace", label: "Facebook Marketplace" },
  { value: "gumtree", label: "Gumtree" },
  { value: "generic", label: "Plain copy" }
];

export function CopyPackPanel({ item }: { item: InventoryItemDetail }) {
  const [channel, setChannel] = useState<CopyPack["channel"]>("facebook_marketplace");
  const [evidencePrice, setEvidencePrice] = useState("");
  const [evidenceLabel, setEvidenceLabel] = useState("");
  const [copied, setCopied] = useState("");
  const pack = useQuery({
    queryKey: ["item-copy-pack", item.id, channel, evidencePrice, evidenceLabel],
    queryFn: () =>
      getItemCopyPack(item.id, {
        channel,
        evidence_price: evidencePrice || undefined,
        evidence_label: evidenceLabel || undefined
      })
  });
  const photoExport = useMutation({
    mutationFn: () => downloadItemPhotoZip(item.id),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `photos-${item.sku}.zip`;
      link.click();
      URL.revokeObjectURL(url);
    }
  });

  async function copyText(label: string, text: string) {
    await navigator.clipboard.writeText(text);
    setCopied(label);
  }

  return (
    <section className="intelligence-panel copy-pack-panel">
      <div className="intelligence-panel-header">
        <div>
          <p className="intelligence-kicker">Channel copy packs</p>
          <h2>Ready-to-paste ad copy</h2>
          <p>Local deterministic templates only. Gaps stay visible; prices come only from an item asking/listed price or a human-picked evidence figure.</p>
        </div>
        <button className="btn-secondary gap-2" disabled={photoExport.isPending} onClick={() => photoExport.mutate()} type="button">
          <Download className="h-4 w-4" aria-hidden="true" />
          Photo zip
        </button>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)]">
        <label className="label">
          <span>Channel</span>
          <select className="field" value={channel} onChange={(event) => setChannel(event.target.value as CopyPack["channel"])}>
            {channelOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label className="label">
          <span>Human evidence price</span>
          <input className="field" inputMode="decimal" placeholder="Optional" value={evidencePrice} onChange={(event) => setEvidencePrice(event.target.value)} />
        </label>
        <label className="label">
          <span>Evidence label</span>
          <input className="field" placeholder="e.g. approved comp" value={evidenceLabel} onChange={(event) => setEvidenceLabel(event.target.value)} />
        </label>
      </div>

      {pack.isLoading ? <div className="intelligence-skeleton" /> : null}
      {pack.error ? <p className="intelligence-error">{pack.error instanceof Error ? pack.error.message : "Copy pack failed."}</p> : null}
      {pack.data ? (
        <>
          <p className="mt-3 text-sm text-slate-700">
            Price source: <strong>{pack.data.price_source.label}</strong>. {pack.data.price_source.hint}
          </p>
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            <CopySection label="Title" value={pack.data.sections.title} onCopy={(text) => copyText("Title", text)} />
            <CopySection label="Price line" value={pack.data.sections.price_line} onCopy={(text) => copyText("Price line", text)} />
            <CopySection label="Postage / pickup" value={pack.data.sections.postage_pickup_line} onCopy={(text) => copyText("Postage / pickup", text)} />
            <CopySection label="Description" value={pack.data.sections.description} onCopy={(text) => copyText("Description", text)} large />
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button className="btn-primary gap-2" type="button" onClick={() => copyText("Whole ad", pack.data.whole_ad)}>
              <ClipboardCopy className="h-4 w-4" aria-hidden="true" />
              Copy whole ad
            </button>
            {copied ? <span className="text-sm font-semibold text-emerald-700">{copied} copied.</span> : null}
            {photoExport.error ? <span className="text-sm font-semibold text-rose-700">{photoExport.error instanceof Error ? photoExport.error.message : "Photo export failed."}</span> : null}
          </div>
        </>
      ) : null}
    </section>
  );
}

function CopySection({ label, value, onCopy, large = false }: { label: string; value: string; onCopy: (value: string) => void; large?: boolean }) {
  return (
    <article className="rounded border border-slate-300 bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-base font-semibold text-slate-950">{label}</h3>
        <button className="btn-secondary gap-2" type="button" onClick={() => onCopy(value)}>
          <Copy className="h-4 w-4" aria-hidden="true" />
          Copy
        </button>
      </div>
      <pre className={large ? "mt-3 min-h-32 whitespace-pre-wrap break-words rounded bg-slate-50 p-3 text-sm" : "mt-3 whitespace-pre-wrap break-words rounded bg-slate-50 p-3 text-sm"}>
        {value || "[blank]"}
      </pre>
    </article>
  );
}

export function CopyPackEmpty() {
  return (
    <div className="ledger-empty">
      <PackageOpen className="h-5 w-5" aria-hidden="true" />
      <div>
        <strong>No copy pack yet.</strong>
        <p>Open an item and Magpie will render local channel templates from its fields.</p>
      </div>
    </div>
  );
}
