import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Plus, Scale, Star } from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";

import { createComparable } from "../api/comparables";
import { getPricingEvidence } from "../api/pricingEvidence";
import type { ComparablePayload, PricingEvidence, PricingEvidenceRow, PricingGridCell, UUID } from "../types";
import { EmptyState } from "./EmptyState";

const blankCapture = {
  title: "",
  price: "",
  price_basis: "unknown" as ComparablePayload["price_basis"],
  shipping: "",
  source: "",
  source_tag: "ebay_sold",
  url: "",
  observed_on: "",
  condition: "",
  grade: "",
  sale_format: "unknown" as ComparablePayload["sale_format"],
  match_scope: "exact" as ComparablePayload["match_scope"],
  match_reason: ""
};

export function PricingEvidencePanel({ itemId }: { itemId: UUID }) {
  const queryClient = useQueryClient();
  const pricing = useQuery({
    queryKey: ["pricing-evidence", itemId],
    queryFn: () => getPricingEvidence(itemId)
  });
  const [form, setForm] = useState(blankCapture);
  const [error, setError] = useState("");

  const capture = useMutation({
    mutationFn: (payload: ComparablePayload) => createComparable(payload),
    onSuccess: () => {
      setForm(blankCapture);
      queryClient.invalidateQueries({ queryKey: ["pricing-evidence", itemId] });
      queryClient.invalidateQueries({ queryKey: ["comparables", itemId] });
    }
  });

  function submitCapture(event: FormEvent) {
    event.preventDefault();
    if (!form.price || Number.isNaN(Number(form.price))) {
      setError("Enter the verified sold price before adding evidence.");
      return;
    }
    if (!form.source.trim()) {
      setError("Source is required so the row has an evidence tag.");
      return;
    }
    setError("");
    capture.mutate({
      item: itemId,
      kind: "sold",
      source: form.source,
      source_tag: form.source_tag,
      title: form.title,
      price: form.price,
      price_basis: form.price_basis,
      shipping: form.shipping || null,
      currency: pricing.data?.currency ?? "AUD",
      condition: form.condition,
      grade: form.grade,
      sale_format: form.sale_format,
      match_scope: form.match_scope,
      match_reason: form.match_reason,
      url: form.url,
      observed_on: form.observed_on || null,
      notes: "User-captured pricing evidence."
    });
  }

  const primaryLink = pricing.data?.source_links.find((link) => link.primary);
  const otherLinks = pricing.data?.source_links.filter((link) => !link.primary) ?? [];

  return (
    <section className="pricing-evidence-panel">
      <div className="pricing-evidence-header">
        <div>
          <p className="intelligence-kicker">Pricing evidence</p>
          <h2>Own sales first</h2>
          <p>
            This grid uses only your own sales and comparables you capture by hand. Source links open in a new tab; Magpie does not fetch or store marketplace result pages.
          </p>
        </div>
        <Scale className="h-5 w-5 text-[#9A7B2E]" aria-hidden="true" />
      </div>

      {pricing.isLoading ? <div className="pricing-skeleton" /> : null}
      {pricing.error ? <EmptyState title="Unable to load pricing evidence" detail="Check your Django admin session." /> : null}

      {pricing.data ? (
        <>
          <div className="pricing-source-strip">
            {primaryLink ? (
              <a className="pricing-primary-link" href={primaryLink.url} target="_blank" rel="noreferrer">
                <span>
                  <strong>{primaryLink.label}</strong>
                  <small>{primaryLink.query}</small>
                </span>
                <ExternalLink className="h-4 w-4" aria-hidden="true" />
              </a>
            ) : null}
            <div className="pricing-secondary-links">
              {otherLinks.map((link) => (
                <a className="pricing-source-link" href={link.url} key={link.id} target="_blank" rel="noreferrer">
                  <span>{link.label}</span>
                  <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                </a>
              ))}
            </div>
          </div>

          <EvidenceSummary data={pricing.data} />
          <EvidenceRows rows={pricing.data.headline} />
          <CaptureForm
            disabled={capture.isPending}
            error={error || errorText(capture.error)}
            form={form}
            onChange={setForm}
            onSubmit={submitCapture}
          />
          <div className="pricing-grid-layout">
            <PricingGrid title="Condition / grade" rows={pricing.data.grids.condition_grade} />
            <PricingGrid title="Sale format" rows={pricing.data.grids.sale_format} />
            <PricingGrid title="Recency" rows={pricing.data.grids.recency} />
            <PricingGrid title="Source" rows={pricing.data.grids.source} />
          </div>
        </>
      ) : null}
    </section>
  );
}

function EvidenceSummary({ data }: { data: PricingEvidence }) {
  if (data.summary.empty) {
    return <EmptyState title={data.empty_state.title} detail={data.empty_state.detail} />;
  }
  return (
    <div className="pricing-summary-row">
      <div>
        <strong>{data.summary.priced_count}</strong>
      <span>priced rows</span>
      </div>
      {data.summary.basis_uncertain_count ? (
        <div>
          <strong>{data.summary.basis_uncertain_count}</strong>
          <span>basis uncertain</span>
        </div>
      ) : null}
      <div>
        <strong>{data.summary.own_sale_count}</strong>
        <span>own sales</span>
      </div>
      <div>
        <strong>{data.summary.exact_count}</strong>
        <span>exact</span>
      </div>
      <div>
        <strong>{data.summary.similar_count}</strong>
        <span>similar</span>
      </div>
      {data.summary.thin ? <p>Thin sample. Treat the table as evidence, not a valuation.</p> : null}
    </div>
  );
}

function EvidenceRows({ rows }: { rows: PricingEvidenceRow[] }) {
  if (rows.length === 0) {
    return null;
  }
  return (
    <div className="pricing-evidence-table-wrap">
      <table className="pricing-evidence-table">
        <thead>
          <tr>
            <th>Evidence</th>
            <th>Source</th>
            <th>Match</th>
            <th>Format</th>
            <th>Date</th>
            <th className="numeric">Price</th>
            <th>Basis</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td data-label="Evidence">
                <div className="pricing-title-cell">
                  <strong>{row.title || row.sku || "Untitled evidence"}</strong>
                  {row.own_sale ? <span className="own-sale-pill"><Star className="h-3 w-3" aria-hidden="true" /> Own sale</span> : null}
                </div>
              </td>
              <td data-label="Source">{row.source_label}</td>
              <td data-label="Match">
                <span className={row.match_scope === "exact" ? "match-pill exact" : "match-pill"}>{row.match_scope}</span>
                <small>{row.match_reason}</small>
              </td>
              <td data-label="Format">{label(row.sale_format)}</td>
              <td data-label="Date">{row.date ?? "undated"}</td>
              <td data-label="Price" className="numeric">{row.price ? `${money(row.price)} ${row.currency}` : "-"}</td>
              <td data-label="Basis">
                <span className={row.basis_uncertain ? "match-pill" : "match-pill exact"}>{row.basis_label}</span>
                {row.canonical_price ? <small>seller receives {money(row.canonical_price)}</small> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CaptureForm({
  disabled,
  error,
  form,
  onChange,
  onSubmit
}: {
  disabled: boolean;
  error: string;
  form: typeof blankCapture;
  onChange: (value: typeof blankCapture) => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <form className="pricing-capture-form" onSubmit={onSubmit}>
      <div className="pricing-capture-title">
        <Plus className="h-4 w-4" aria-hidden="true" />
        <h3>Capture verified comp</h3>
      </div>
      {error ? <p className="pricing-error">{error}</p> : null}
      <div className="pricing-capture-grid">
        <label className="label">
          <span>Source tag</span>
          <select className="field" value={form.source_tag} onChange={(event) => onChange({ ...form, source_tag: event.target.value })}>
            <option value="ebay_sold">eBay sold</option>
            <option value="facebook_marketplace">Facebook</option>
            <option value="auction_archive">Auction archive</option>
            <option value="price_guide">Price guide</option>
            <option value="manual">Manual</option>
          </select>
        </label>
        <label className="label">
          <span>Source label</span>
          <input className="field" value={form.source} onChange={(event) => onChange({ ...form, source: event.target.value })} />
        </label>
        <label className="label">
          <span>Sold price</span>
          <input className="field" inputMode="decimal" value={form.price} onChange={(event) => onChange({ ...form, price: event.target.value })} />
        </label>
        <label className="label">
          <span>Price basis</span>
          <select className="field" value={form.price_basis} onChange={(event) => onChange({ ...form, price_basis: event.target.value as typeof form.price_basis })}>
            <option value="unknown">Unknown / review</option>
            <option value="seller_receives">Seller receives</option>
            <option value="buyer_visible">Buyer-visible total</option>
          </select>
        </label>
        <label className="label">
          <span>Shipping</span>
          <input className="field" inputMode="decimal" value={form.shipping} onChange={(event) => onChange({ ...form, shipping: event.target.value })} />
        </label>
        <label className="label">
          <span>Format</span>
          <select className="field" value={form.sale_format} onChange={(event) => onChange({ ...form, sale_format: event.target.value as typeof form.sale_format })}>
            <option value="unknown">Unknown</option>
            <option value="auction">Auction</option>
            <option value="fixed_price">Fixed price</option>
            <option value="dealer">Dealer / guide</option>
            <option value="other">Other</option>
          </select>
        </label>
        <label className="label">
          <span>Match</span>
          <select className="field" value={form.match_scope} onChange={(event) => onChange({ ...form, match_scope: event.target.value as typeof form.match_scope })}>
            <option value="exact">Exact item</option>
            <option value="similar">Similar item</option>
          </select>
        </label>
        <label className="label">
          <span>Condition</span>
          <input className="field" value={form.condition} onChange={(event) => onChange({ ...form, condition: event.target.value })} />
        </label>
        <label className="label">
          <span>Grade</span>
          <input className="field" value={form.grade} onChange={(event) => onChange({ ...form, grade: event.target.value })} />
        </label>
        <label className="label">
          <span>Observed on</span>
          <input className="field" type="date" value={form.observed_on} onChange={(event) => onChange({ ...form, observed_on: event.target.value })} />
        </label>
        <label className="label">
          <span>Evidence URL</span>
          <input className="field" value={form.url} onChange={(event) => onChange({ ...form, url: event.target.value })} />
        </label>
        <label className="label pricing-span-2">
          <span>Title</span>
          <input className="field" value={form.title} onChange={(event) => onChange({ ...form, title: event.target.value })} />
        </label>
        <label className="label pricing-span-2">
          <span>Match reason</span>
          <input className="field" value={form.match_reason} onChange={(event) => onChange({ ...form, match_reason: event.target.value })} placeholder="same category; same year; same denomination" />
        </label>
      </div>
      <button className="ledger-button ledger-button-primary" disabled={disabled} type="submit">
        <Plus className="h-4 w-4" aria-hidden="true" />
        Add to grid
      </button>
    </form>
  );
}

function PricingGrid({ rows, title }: { rows: PricingGridCell[]; title: string }) {
  if (rows.length === 0) {
    return (
      <div className="pricing-grid-card">
        <h3>{title}</h3>
        <p className="pricing-muted">No priced evidence yet.</p>
      </div>
    );
  }
  return (
    <div className="pricing-grid-card">
      <h3>{title}</h3>
      <table>
        <thead>
          <tr>
            <th>Cut</th>
            <th>Low</th>
            <th>Median</th>
            <th>High</th>
            <th>n</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key}>
              <td>
                <span>{row.label}</span>
                {row.own_sale_count ? <small>{row.own_sale_count} own</small> : null}
                {row.basis_uncertain_count ? <small>{row.basis_uncertain_count} basis uncertain</small> : null}
                {row.thin ? <small>thin</small> : null}
              </td>
              <td>{money(row.low)}</td>
              <td>{money(row.median)}</td>
              <td>{money(row.high)}</td>
              <td>{row.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function money(value: string | null) {
  if (!value) {
    return "-";
  }
  return Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function label(value: string) {
  return value.replace(/_/g, " ");
}

function errorText(error: unknown) {
  if (!error) {
    return "";
  }
  return error instanceof Error ? error.message : "Request failed.";
}
