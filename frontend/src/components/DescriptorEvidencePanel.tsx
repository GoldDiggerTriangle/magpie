import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ExternalLink, Plus, Search } from "lucide-react";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";

import { captureDescriptorComparable, getDescriptorEvidence } from "../api/evidence";
import type { DescriptorCapturePayload, DescriptorEvidenceRow, PriceBasis, ProductCategory, UUID } from "../types";
import { AuthRequiredState } from "./AuthRequiredState";
import { EmptyState } from "./EmptyState";

const blankCapture = {
  price: "",
  price_basis: "unknown" as PriceBasis,
  source: "",
  source_tag: "manual",
  title: "",
  observed_on: "",
  url: "",
  note: ""
};

export function DescriptorEvidencePanel({
  attributes = {},
  categories = [],
  categoryId,
  itemId = null,
  onCategoryChange,
  onTermsChange,
  onUsePrice,
  terms,
  title = "Descriptor evidence"
}: {
  attributes?: Record<string, unknown>;
  categories?: ProductCategory[];
  categoryId: UUID | "";
  itemId?: UUID | null;
  onCategoryChange?: (value: UUID | "") => void;
  onTermsChange?: (value: string) => void;
  onUsePrice?: (row: DescriptorEvidenceRow) => void;
  terms: string;
  title?: string;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return true;
    return !window.matchMedia("(max-width: 640px)").matches;
  });
  const [capture, setCapture] = useState(blankCapture);
  const [error, setError] = useState("");
  const queryKey = ["descriptor-evidence", categoryId, terms, JSON.stringify(attributes)];
  const enabled = Boolean(categoryId || terms.trim());
  const evidence = useQuery({
    queryKey,
    queryFn: () => getDescriptorEvidence({ category: categoryId, terms, attributes }),
    enabled
  });
  const captureMutation = useMutation({
    mutationFn: (payload: DescriptorCapturePayload) => captureDescriptorComparable(payload),
    onSuccess: (result) => {
      setCapture(blankCapture);
      queryClient.setQueryData(queryKey, result.lookup);
      queryClient.invalidateQueries({ queryKey: ["descriptor-evidence"] });
    }
  });

  useEffect(() => {
    setError("");
  }, [categoryId, terms]);

  function submitCapture(event: FormEvent) {
    event.preventDefault();
    if (!capture.price || Number.isNaN(Number(capture.price))) {
      setError("Enter the human-recorded sold price.");
      return;
    }
    if (!capture.source.trim()) {
      setError("Add the source you read this from.");
      return;
    }
    setError("");
    captureMutation.mutate({
      item: itemId,
      category: categoryId || null,
      terms,
      attributes,
      price: capture.price,
      price_basis: capture.price_basis,
      source: capture.source,
      source_tag: capture.source_tag,
      title: capture.title || terms || "Captured comparable",
      observed_on: capture.observed_on || null,
      url: capture.url,
      notes: capture.note,
      match_scope: "similar",
      match_reason: "user-captured from descriptor lookup"
    });
  }

  const rows = evidence.data?.rows ?? [];
  const stats = evidence.data?.stats;
  const strength = evidence.data?.strength;

  return (
    <section className="descriptor-evidence-panel">
      <button
        aria-expanded={open}
        className="descriptor-evidence-summary"
        onClick={() => setOpen((current) => !current)}
        type="button"
      >
        <span>
          <span className="ledger-kicker">Evidence lookup</span>
          <strong>{title}</strong>
        </span>
        <Search className="h-5 w-5" aria-hidden="true" />
      </button>

      {open ? (
        <div className="descriptor-evidence-body">
          <div className="descriptor-lookup-grid">
            {onCategoryChange ? (
              <label className="label">
                <span>Category</span>
                <select className="field" value={categoryId} onChange={(event) => onCategoryChange(event.target.value)}>
                  <option value="">Any category</option>
                  {categories.map((category) => (
                    <option key={category.id} value={category.id}>{category.name}</option>
                  ))}
                </select>
              </label>
            ) : null}
            {onTermsChange ? (
              <label className="label">
                <span>Lookup terms</span>
                <input className="field" value={terms} onChange={(event) => onTermsChange(event.target.value)} />
              </label>
            ) : (
              <div className="descriptor-static-context">
                <span>Lookup terms</span>
                <strong>{terms || "No terms yet"}</strong>
              </div>
            )}
          </div>

          {evidence.error ? <AuthRequiredState detail="Descriptor evidence needs your Magpie session. Typed what-if calculations still work." /> : null}
          {evidence.isLoading ? <div className="descriptor-skeleton" /> : null}
          {!enabled ? <EmptyState title="Add category or terms" detail="Use a lookup context before capturing evidence." /> : null}
          {evidence.data?.empty ? <EmptyState title={evidence.data.empty_state.title} detail={evidence.data.empty_state.detail} /> : null}

          {stats ? (
            <div className="descriptor-stats" title={strength?.tooltip}>
              <div>
                <span>{strength?.label ?? "THIN"}</span>
                <strong>n = {stats.count}</strong>
                <small>{stats.newest_age_days === null ? "newest age unknown" : `newest ${stats.newest_age_days}d ago`}</small>
              </div>
              <div>
                <span>Low</span>
                <strong>{money(stats.low)}</strong>
              </div>
              <div>
                <span>Median</span>
                <strong>{money(stats.median)}</strong>
              </div>
              <div>
                <span>High</span>
                <strong>{money(stats.high)}</strong>
              </div>
              {stats.unknown_basis_count ? <p>{stats.unknown_basis_count} basis-uncertain row{stats.unknown_basis_count === 1 ? "" : "s"} excluded from precise stats.</p> : null}
            </div>
          ) : null}

          <div className="descriptor-row-list">
            {rows.slice(0, 8).map((row) => (
              <div className="descriptor-row" key={row.id}>
                <div>
                  <strong>{row.label}</strong>
                  <small>{row.source_label} · {row.match_reason}</small>
                  <small>{row.own_sale ? "own sale" : "approved comp"} · {row.date ?? "undated"}</small>
                </div>
                <div className="descriptor-row-actions">
                  <span>{row.seller_receives ? money(row.seller_receives) : "basis-uncertain"}</span>
                  {row.url ? (
                    <a aria-label={`Open source for ${row.label}`} href={row.url} rel="noreferrer" target="_blank">
                      <ExternalLink className="h-4 w-4" aria-hidden="true" />
                    </a>
                  ) : null}
                  {onUsePrice ? (
                    <button
                      className="ledger-button ledger-button-small"
                      disabled={!row.seller_receives || row.basis_uncertain}
                      onClick={() => onUsePrice(row)}
                      type="button"
                    >
                      Use this
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>

          <form className="descriptor-capture-form" onSubmit={submitCapture}>
            <div className="pricing-capture-title">
              <Plus className="h-4 w-4" aria-hidden="true" />
              <h3>Fast capture comp</h3>
            </div>
            {error || captureMutation.error ? <p className="pricing-error">{error || errorText(captureMutation.error)}</p> : null}
            <div className="descriptor-capture-grid">
              <label className="label">
                <span>Human-entered price</span>
                <input className="field" inputMode="decimal" value={capture.price} onChange={(event) => setCapture({ ...capture, price: event.target.value })} />
              </label>
              <label className="label">
                <span>Basis quick-pick</span>
                <select className="field" value={capture.price_basis} onChange={(event) => setCapture({ ...capture, price_basis: event.target.value as PriceBasis })}>
                  <option value="unknown">Unknown / review</option>
                  <option value="seller_receives">Seller receives</option>
                  <option value="buyer_visible">Buyer-visible total</option>
                </select>
              </label>
              <label className="label">
                <span>Source</span>
                <input className="field" value={capture.source} onChange={(event) => setCapture({ ...capture, source: event.target.value })} />
              </label>
              <label className="label">
                <span>Date</span>
                <input className="field" type="date" value={capture.observed_on} onChange={(event) => setCapture({ ...capture, observed_on: event.target.value })} />
              </label>
              <label className="label descriptor-span-2">
                <span>Source link</span>
                <input className="field" value={capture.url} onChange={(event) => setCapture({ ...capture, url: event.target.value })} />
              </label>
              <label className="label descriptor-span-2">
                <span>Note</span>
                <input className="field" value={capture.note} onChange={(event) => setCapture({ ...capture, note: event.target.value })} />
              </label>
            </div>
            <button className="ledger-button ledger-button-primary" disabled={captureMutation.isPending} type="submit">
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              Save approved comp
            </button>
          </form>
        </div>
      ) : null}
    </section>
  );
}

function money(value: string | null | undefined) {
  if (!value) return "-";
  return `$${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function errorText(error: unknown) {
  if (!error) return "";
  return error instanceof Error ? error.message : "Request failed.";
}
