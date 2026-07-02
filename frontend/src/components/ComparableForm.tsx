import type { FormEvent } from "react";
import { useEffect, useState } from "react";

import type { Comparable, ComparableKind, ComparablePayload, UUID } from "../types";

export const comparableKindOptions: Array<[ComparableKind, string]> = [
  ["sold", "Sold / completed"],
  ["active", "Active listing"],
  ["dealer", "Dealer asking"],
  ["catalogue", "Catalogue value"],
  ["manual_estimate", "Manual estimate"],
  ["auction_result", "Auction result"]
];

interface ComparableFormProps {
  itemId: UUID;
  initial?: Comparable | null;
  onSubmit: (payload: ComparablePayload) => void;
  submitLabel?: string;
  disabled?: boolean;
}

const blankForm = {
  kind: "sold" as ComparableKind,
  source: "",
  title: "",
  price: "",
  price_basis: "unknown" as ComparablePayload["price_basis"],
  shipping: "",
  currency: "AUD",
  condition: "",
  url: "",
  observed_on: "",
  notes: ""
};

export function ComparableForm({ itemId, initial, onSubmit, submitLabel = "Save comparable", disabled }: ComparableFormProps) {
  const [form, setForm] = useState(blankForm);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!initial) {
      setForm(blankForm);
      return;
    }
    setForm({
      kind: initial.kind,
      source: initial.source,
      title: initial.title,
      price: initial.price ?? "",
      price_basis: initial.price_basis,
      shipping: initial.shipping ?? "",
      currency: initial.currency,
      condition: initial.condition,
      url: initial.url,
      observed_on: initial.observed_on ?? "",
      notes: initial.notes
    });
  }, [initial]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!form.kind) {
      setError("Kind is required.");
      return;
    }
    if (form.price && Number.isNaN(Number(form.price))) {
      setError("Price must be a number.");
      return;
    }
    if (form.shipping && Number.isNaN(Number(form.shipping))) {
      setError("Shipping must be a number.");
      return;
    }
    setError("");
    onSubmit({
      item: itemId,
      kind: form.kind,
      source: form.source,
      title: form.title,
      price: form.price || null,
      price_basis: form.price_basis,
      shipping: form.shipping || null,
      currency: form.currency,
      condition: form.condition,
      url: form.url,
      observed_on: form.observed_on || null,
      notes: form.notes
    });
    if (!initial) {
      setForm(blankForm);
    }
  }

  return (
    <form className="space-y-3" onSubmit={handleSubmit}>
      {error ? <p className="rounded border border-rose-400/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-100">{error}</p> : null}
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="label">
          <span>Kind</span>
          <select className="field" value={form.kind} onChange={(event) => setForm({ ...form, kind: event.target.value as ComparableKind })}>
            {comparableKindOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label className="label">
          <span>Price</span>
          <input className="field" inputMode="decimal" value={form.price} onChange={(event) => setForm({ ...form, price: event.target.value })} />
        </label>
        <label className="label">
          <span>Price basis</span>
          <select className="field" value={form.price_basis} onChange={(event) => setForm({ ...form, price_basis: event.target.value as ComparablePayload["price_basis"] })}>
            <option value="unknown">Unknown / review</option>
            <option value="seller_receives">Seller receives</option>
            <option value="buyer_visible">Buyer-visible total</option>
          </select>
        </label>
        <label className="label">
          <span>Shipping</span>
          <input className="field" inputMode="decimal" value={form.shipping} onChange={(event) => setForm({ ...form, shipping: event.target.value })} />
        </label>
        <label className="label">
          <span>Currency</span>
          <input className="field" maxLength={3} value={form.currency} onChange={(event) => setForm({ ...form, currency: event.target.value.toUpperCase() })} />
        </label>
        <label className="label sm:col-span-2">
          <span>Title</span>
          <input className="field" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
        </label>
        <label className="label">
          <span>Source</span>
          <input className="field" value={form.source} onChange={(event) => setForm({ ...form, source: event.target.value })} />
        </label>
        <label className="label">
          <span>Condition</span>
          <input className="field" value={form.condition} onChange={(event) => setForm({ ...form, condition: event.target.value })} />
        </label>
        <label className="label">
          <span>Observed on</span>
          <input className="field" type="date" value={form.observed_on} onChange={(event) => setForm({ ...form, observed_on: event.target.value })} />
        </label>
        <label className="label">
          <span>URL</span>
          <input className="field" value={form.url} onChange={(event) => setForm({ ...form, url: event.target.value })} />
        </label>
        <label className="label sm:col-span-2">
          <span>Notes</span>
          <textarea className="field min-h-20" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} />
        </label>
      </div>
      <button className="btn-primary" disabled={disabled} type="submit">{submitLabel}</button>
    </form>
  );
}

