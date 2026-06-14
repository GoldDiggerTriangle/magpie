import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, DownloadCloud, Link2, RefreshCw, XCircle } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  getEbayStatus,
  listEbayOrderDuplicates,
  listEbayOrderStaging,
  resolveEbayOrderDuplicate,
  resolveEbayOrderStaging,
  syncEbayOrders
} from "../../api/ebay";
import { listItems } from "../../api/items";
import { EmptyState } from "../../components/EmptyState";
import type { EbayOrderDuplicateCandidate, EbayOrderStaging, EbayOrderSyncResult, InventoryItemList, SaleRecord } from "../../types";

interface StagingInput {
  item: string;
  title: string;
  cost: string;
  notes: string;
}

const blankInput: StagingInput = {
  item: "",
  title: "",
  cost: "",
  notes: ""
};

export function EbayOrders() {
  const queryClient = useQueryClient();
  const [stagingInputs, setStagingInputs] = useState<Record<string, StagingInput>>({});
  const [itemSearch, setItemSearch] = useState("");
  const [resolvedIds, setResolvedIds] = useState<Set<string>>(() => new Set());
  const [lastResolvedSale, setLastResolvedSale] = useState<SaleRecord | null>(null);

  const status = useQuery({ queryKey: ["ebay-status"], queryFn: getEbayStatus });
  const staging = useQuery({ queryKey: ["ebay-order-staging", "pending"], queryFn: () => listEbayOrderStaging("pending") });
  const duplicates = useQuery({ queryKey: ["ebay-order-duplicates", "pending"], queryFn: () => listEbayOrderDuplicates("pending") });
  const items = useQuery({
    queryKey: ["items", "ebay-order-picker", itemSearch],
    queryFn: () => listItems({ search: itemSearch })
  });

  const pendingRows = useMemo(
    () => (staging.data?.results ?? []).filter((row) => !resolvedIds.has(row.id)),
    [resolvedIds, staging.data?.results]
  );
  const duplicateRows = duplicates.data?.results ?? [];
  const itemOptions = items.data?.results ?? [];

  function refreshOrderQueues() {
    queryClient.invalidateQueries({ queryKey: ["ebay-status"] });
    queryClient.invalidateQueries({ queryKey: ["ebay-order-staging"] });
    queryClient.invalidateQueries({ queryKey: ["ebay-order-duplicates"] });
    queryClient.invalidateQueries({ queryKey: ["sales"] });
  }

  function updateInput(id: string, patch: Partial<StagingInput>) {
    setStagingInputs((current) => ({
      ...current,
      [id]: { ...(current[id] ?? blankInput), ...patch }
    }));
  }

  const syncMutation = useMutation({
    mutationFn: () => syncEbayOrders(),
    onSuccess: refreshOrderQueues
  });

  const resolveStagingMutation = useMutation({
    mutationFn: ({ row, action }: { row: EbayOrderStaging; action: "link" | "quick_create" | "mark_external" }) => {
      const input = stagingInputs[row.id] ?? blankInput;
      if (action === "link") {
        return resolveEbayOrderStaging(row.id, {
          action,
          item: input.item,
          cost_basis_override: input.cost || null,
          notes: input.notes
        });
      }
      if (action === "quick_create") {
        return resolveEbayOrderStaging(row.id, {
          action,
          title: input.title || row.sku || `eBay order ${row.ebay_order_id}`,
          quantity_total: row.quantity,
          acquisition_cost: input.cost || null,
          notes: input.notes
        });
      }
      return resolveEbayOrderStaging(row.id, {
        action,
        cost_basis_override: input.cost || null,
        notes: input.notes
      });
    },
    onSuccess: (sale, variables) => {
      setResolvedIds((current) => new Set(current).add(variables.row.id));
      setLastResolvedSale(sale);
      refreshOrderQueues();
    }
  });

  const resolveDuplicateMutation = useMutation({
    mutationFn: ({ row, action }: { row: EbayOrderDuplicateCandidate; action: "link" | "dismiss" }) => resolveEbayOrderDuplicate(row.id, { action }),
    onSuccess: refreshOrderQueues
  });

  const error = errorText(syncMutation.error) || errorText(resolveStagingMutation.error) || errorText(resolveDuplicateMutation.error);

  return (
    <div className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="page-title">eBay Orders</h1>
          <p className="mt-1 text-sm text-slate-500">Manual read-only import review</p>
        </div>
        <button
          className="btn-primary gap-2"
          disabled={!status.data?.connected || syncMutation.isPending}
          onClick={() => syncMutation.mutate()}
          type="button"
        >
          {syncMutation.isPending ? <RefreshCw className="h-4 w-4 animate-spin" aria-hidden="true" /> : <DownloadCloud className="h-4 w-4" aria-hidden="true" />}
          Sync eBay orders
        </button>
      </div>

      {status.isLoading ? <div className="mt-5"><EmptyState title="Loading eBay order sync status" /></div> : null}
      {status.error ? <div className="mt-5"><EmptyState title="Sign in through Django admin" detail="The order sync API needs your Django session." /></div> : null}
      {status.data?.requires_reconsent ? (
        <div className="mt-5 rounded border border-amber-300/30 bg-amber-300/10 p-4 text-sm text-amber-50">
          Re-consent is required before order sync. Complete the paste-back connection flow in Settings.
        </div>
      ) : null}
      {error ? <div className="mt-5 rounded border border-rose-400/30 bg-rose-500/10 p-4 text-sm text-rose-100">{error}</div> : null}

      {syncMutation.data ? <SyncResult result={syncMutation.data} /> : null}
      {lastResolvedSale ? <ResolutionNotice sale={lastResolvedSale} /> : null}

      <div className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section className="rounded border border-slate-800 bg-slate-950/40 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="section-title">Unmatched Orders</h2>
              <p className="mt-1 text-xs text-slate-500">{pendingRows.length} pending staged rows</p>
            </div>
            <label className="label w-full sm:w-72">
              <span>Search inventory for linking</span>
              <input
                className="field"
                onChange={(event) => setItemSearch(event.target.value)}
                placeholder="SKU or title"
                value={itemSearch}
              />
            </label>
          </div>

          {staging.isLoading ? <div className="mt-4"><EmptyState title="Loading staging queue" /></div> : null}
          {staging.error ? <div className="mt-4"><EmptyState title="Unable to load staged orders" detail="Check your Django admin session." /></div> : null}
          {!staging.isLoading && !staging.error && pendingRows.length === 0 ? (
            <div className="mt-4"><EmptyState title="No pending staged orders" detail="Unmatched eBay order lines will appear here after sync." /></div>
          ) : null}

          <div className="mt-4 space-y-3">
            {pendingRows.map((row) => (
              <StagingRow
                busy={resolveStagingMutation.isPending}
                input={stagingInputs[row.id] ?? blankInput}
                itemOptions={itemOptions}
                itemsLoading={items.isLoading}
                key={row.id}
                onInputChange={(patch) => updateInput(row.id, patch)}
                onResolve={(action) => resolveStagingMutation.mutate({ row, action })}
                row={row}
              />
            ))}
          </div>
        </section>

        <section className="rounded border border-slate-800 bg-slate-950/40 p-4">
          <h2 className="section-title">Duplicate Candidates</h2>
          <p className="mt-1 text-xs text-slate-500">Matched orders that look like an existing manual sale</p>

          {duplicates.isLoading ? <div className="mt-4"><EmptyState title="Loading duplicate candidates" /></div> : null}
          {duplicates.error ? <div className="mt-4"><EmptyState title="Unable to load duplicate candidates" detail="Check your Django admin session." /></div> : null}
          {!duplicates.isLoading && !duplicates.error && duplicateRows.length === 0 ? (
            <div className="mt-4"><EmptyState title="No duplicate candidates" detail="Clean matched imports do not need review here." /></div>
          ) : null}

          <div className="mt-4 space-y-3">
            {duplicateRows.map((row) => (
              <DuplicateCandidateRow
                busy={resolveDuplicateMutation.isPending}
                key={row.id}
                onResolve={(action) => resolveDuplicateMutation.mutate({ row, action })}
                row={row}
              />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function SyncResult({ result }: { result: EbayOrderSyncResult }) {
  return (
    <section className="mt-5 rounded border border-emerald-300/30 bg-emerald-300/10 p-4">
      <div className="flex items-center gap-2">
        <CheckCircle2 className="h-4 w-4 text-emerald-100" aria-hidden="true" />
        <h2 className="section-title text-emerald-50">Sync completed</h2>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3 xl:grid-cols-6">
        <Metric label="Created" value={result.counts.created} />
        <Metric label="Staged" value={result.counts.staged} />
        <Metric label="Duplicates" value={result.counts.duplicate_flagged} />
        <Metric label="Skipped" value={result.counts.skipped} />
        <Metric label="Fee actual" value={result.counts.fee_authoritative} />
        <Metric label="Fee review" value={result.counts.fee_estimated_or_unmapped} />
      </div>
    </section>
  );
}

function ResolutionNotice({ sale }: { sale: SaleRecord }) {
  return (
    <div className="mt-5 rounded border border-cyan-300/30 bg-cyan-300/10 p-4 text-sm text-cyan-50">
      Sale recorded{sale.cost_basis_unknown ? " with unknown cost basis" : ""}.{" "}
      <Link className="font-semibold text-cyan-100 underline underline-offset-2" to="/sales">
        View it on Sales
      </Link>
      .
    </div>
  );
}

function StagingRow({
  busy,
  input,
  itemOptions,
  itemsLoading,
  onInputChange,
  onResolve,
  row
}: {
  busy: boolean;
  input: StagingInput;
  itemOptions: InventoryItemList[];
  itemsLoading: boolean;
  onInputChange: (patch: Partial<StagingInput>) => void;
  onResolve: (action: "link" | "quick_create" | "mark_external") => void;
  row: EbayOrderStaging;
}) {
  const feeText = row.actual_fee ? `$${row.actual_fee}` : "-";
  return (
    <article className="rounded border border-slate-800 bg-slate-900 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-100">{row.sku || "No SKU"}</h3>
          <p className="mt-1 text-xs text-slate-500">
            {row.sale_date} · Qty {row.quantity} · ${row.line_price} · Fees {feeText}
          </p>
          <p className={row.fee_status === "estimated_or_unmapped" ? "mt-1 text-xs text-amber-200" : "mt-1 text-xs text-emerald-200"}>
            {row.fee_status === "estimated_or_unmapped" ? "Fees need review" : "Fees confidently mapped"}
          </p>
          {row.buyer_region ? <p className="mt-1 text-xs text-slate-500">Buyer region: {row.buyer_region}</p> : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-secondary gap-2" disabled={!input.item || busy} onClick={() => onResolve("link")} type="button">
            <Link2 className="h-4 w-4" aria-hidden="true" />
            Link to item
          </button>
          <button className="btn-secondary" disabled={busy} onClick={() => onResolve("quick_create")} type="button">
            Quick-create item
          </button>
          <button className="btn-secondary" disabled={busy} onClick={() => onResolve("mark_external")} type="button">
            Mark external
          </button>
        </div>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-4">
        <label className="label">
          <span>Existing item</span>
          <select
            aria-label={`Existing item for ${row.sku || row.id}`}
            className="field"
            disabled={itemsLoading}
            onChange={(event) => onInputChange({ item: event.target.value })}
            value={input.item}
          >
            <option value="">{itemsLoading ? "Loading inventory..." : "Choose item"}</option>
            {itemOptions.map((item) => (
              <option key={item.id} value={item.id}>
                {item.sku} - {item.title}
              </option>
            ))}
          </select>
        </label>
        <label className="label">
          <span>Quick-create title</span>
          <input
            className="field"
            onChange={(event) => onInputChange({ title: event.target.value })}
            placeholder={row.sku || "External order"}
            value={input.title}
          />
        </label>
        <label className="label">
          <span>Cost basis</span>
          <input
            className="field"
            inputMode="decimal"
            onChange={(event) => onInputChange({ cost: event.target.value })}
            placeholder="Blank = unknown"
            value={input.cost}
          />
        </label>
        <label className="label">
          <span>Notes</span>
          <input
            className="field"
            onChange={(event) => onInputChange({ notes: event.target.value })}
            placeholder="Optional"
            value={input.notes}
          />
        </label>
      </div>
    </article>
  );
}

function DuplicateCandidateRow({
  busy,
  onResolve,
  row
}: {
  busy: boolean;
  onResolve: (action: "link" | "dismiss") => void;
  row: EbayOrderDuplicateCandidate;
}) {
  return (
    <article className="rounded border border-slate-800 bg-slate-900 p-4">
      <h3 className="text-sm font-semibold text-slate-100">{row.item_sku} - {row.item_title}</h3>
      <p className="mt-1 text-xs text-slate-500">
        {row.sale_date} · Qty {row.quantity} · ${row.line_price}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button className="btn-secondary gap-2" disabled={busy} onClick={() => onResolve("link")} type="button">
          <Link2 className="h-4 w-4" aria-hidden="true" />
          Link candidate
        </button>
        <button className="btn-secondary gap-2" disabled={busy} onClick={() => onResolve("dismiss")} type="button">
          <XCircle className="h-4 w-4" aria-hidden="true" />
          Dismiss
        </button>
      </div>
    </article>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded border border-slate-700 bg-slate-950/50 p-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-2 text-xl font-semibold text-slate-50">{value}</p>
    </div>
  );
}

function errorText(error: unknown) {
  if (!error) {
    return "";
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Request failed.";
}
