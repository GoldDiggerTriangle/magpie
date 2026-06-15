import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ReceiptText, RotateCcw, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { listFeeSchedules } from "../api/fees";
import { listItemListingDrafts } from "../api/listing";
import { correctSaleRecord, createItemSale, listItemSales } from "../api/sales";
import type { FeeSchedule, InventoryItemDetail, SaleRecord, SaleRecordPayload } from "../types";
import { EmptyState } from "./EmptyState";

interface SaleFormState {
  sale_date: string;
  quantity: string;
  sale_price: string;
  channel: SaleRecord["channel"];
  actual_fees_total: string;
  actual_shipping_cost: string;
  cost_basis_override: string;
  listing_draft: string;
  notes: string;
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function emptyForm(item: InventoryItemDetail): SaleFormState {
  const defaultPrice = item.target_price ?? item.current_valuation?.suggested_price ?? item.estimated_value ?? "";
  return {
    sale_date: todayIso(),
    quantity: item.quantity_remaining > 0 ? "1" : "0",
    sale_price: defaultPrice,
    channel: "manual",
    actual_fees_total: "",
    actual_shipping_cost: "0.00",
    cost_basis_override: "",
    listing_draft: "",
    notes: ""
  };
}

function toNumber(value: string | null | undefined) {
  const parsed = Number(value ?? "");
  return Number.isFinite(parsed) ? parsed : 0;
}

function rounded(value: number) {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

function moneyText(value: number) {
  return rounded(value).toLocaleString("en-AU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

function estimateFees(schedule: FeeSchedule | undefined, salePrice: number) {
  if (!schedule || salePrice <= 0) {
    return 0;
  }
  const finalValueFee = salePrice * (toNumber(schedule.final_value_pct) / 100);
  const promotedFee = salePrice * (toNumber(schedule.promoted_pct) / 100);
  const perOrderFee = toNumber(schedule.per_order_fee);
  const gstOnFees = (finalValueFee + promotedFee + perOrderFee) * (toNumber(schedule.gst_pct) / 100);
  return rounded(finalValueFee + promotedFee + perOrderFee + gstOnFees);
}

function saleToForm(sale: SaleRecord): SaleFormState {
  return {
    sale_date: sale.sale_date,
    quantity: String(sale.quantity),
    sale_price: sale.sale_price,
    channel: sale.channel,
    actual_fees_total: sale.actual_fees_total,
    actual_shipping_cost: sale.actual_shipping_cost,
    cost_basis_override: sale.cost_basis_override ?? "",
    listing_draft: sale.listing_draft ?? "",
    notes: sale.notes
  };
}

export function SalesPanel({ item }: { item: InventoryItemDetail }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<SaleFormState>(() => emptyForm(item));
  const [feesTouched, setFeesTouched] = useState(false);
  const [correctionTarget, setCorrectionTarget] = useState<SaleRecord | null>(null);

  const sales = useQuery({ queryKey: ["item-sales", item.id], queryFn: () => listItemSales(item.id) });
  const feeSchedules = useQuery({ queryKey: ["fee-schedules"], queryFn: listFeeSchedules });
  const listingDrafts = useQuery({ queryKey: ["item-listing-drafts", item.id], queryFn: () => listItemListingDrafts(item.id) });

  const activeSchedule = feeSchedules.data?.results.find((schedule) => schedule.is_active) ?? feeSchedules.data?.results[0];
  const estimatedFees = useMemo(() => estimateFees(activeSchedule, toNumber(form.sale_price)), [activeSchedule, form.sale_price]);

  useEffect(() => {
    if (!feesTouched) {
      setForm((current) => ({ ...current, actual_fees_total: estimatedFees ? moneyText(estimatedFees) : "0.00" }));
    }
  }, [estimatedFees, feesTouched]);

  useEffect(() => {
    if (!correctionTarget) {
      setForm(emptyForm(item));
      setFeesTouched(false);
    }
  }, [item.id, item.quantity_remaining, correctionTarget]);

  const salePrice = toNumber(form.sale_price);
  const actualFees = toNumber(form.actual_fees_total);
  const shipping = toNumber(form.actual_shipping_cost);
  const quantity = Math.max(0, Number(form.quantity) || 0);
  const netProceeds = salePrice - actualFees - shipping;
  const defaultCostBasis = item.acquisition_cost
    ? (toNumber(item.acquisition_cost) / Math.max(1, item.quantity_total)) * quantity
    : 0;
  const allocatedCostBasis = form.cost_basis_override ? toNumber(form.cost_basis_override) : defaultCostBasis;
  const realisedProfit = netProceeds - allocatedCostBasis;
  const activeSales = sales.data?.results.filter((sale) => !sale.is_superseded) ?? [];
  const activeProfit = activeSales.reduce((total, sale) => total + toNumber(sale.realised_profit), 0);
  const maxQuantity = correctionTarget ? item.quantity_remaining + correctionTarget.quantity : item.quantity_remaining;

  const submit = useMutation({
    mutationFn: () => {
      const payload: SaleRecordPayload = {
        sale_date: form.sale_date,
        quantity,
        sale_price: form.sale_price || "0.00",
        channel: form.channel,
        actual_fees_total: form.actual_fees_total || null,
        actual_shipping_cost: form.actual_shipping_cost || "0.00",
        cost_basis_override: form.cost_basis_override || null,
        listing_draft: form.listing_draft || null,
        notes: form.notes
      };
      return correctionTarget
        ? correctSaleRecord(correctionTarget.id, payload)
        : createItemSale(item.id, payload);
    },
    onSuccess: () => {
      setCorrectionTarget(null);
      setForm(emptyForm(item));
      setFeesTouched(false);
      queryClient.invalidateQueries({ queryKey: ["item", item.id] });
      queryClient.invalidateQueries({ queryKey: ["item-sales", item.id] });
      queryClient.invalidateQueries({ queryKey: ["sales"] });
    }
  });

  function startCorrection(sale: SaleRecord) {
    setCorrectionTarget(sale);
    setForm(saleToForm(sale));
    setFeesTouched(true);
  }

  function cancelCorrection() {
    setCorrectionTarget(null);
    setForm(emptyForm(item));
    setFeesTouched(false);
  }

  return (
    <section className="rounded border border-slate-800 bg-slate-900 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="section-title inline-flex items-center gap-2">
            <ReceiptText className="h-4 w-4" aria-hidden="true" />
            Sales
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            {item.quantity_sold} sold / {item.quantity_remaining} remaining from {item.quantity_total}
          </p>
        </div>
        <div className="text-left text-sm text-slate-300 sm:text-right">
          <p>Active realised P&L ${moneyText(activeProfit)}</p>
          {!item.acquisition_cost ? <p className="text-amber-200">No item cost basis set</p> : null}
        </div>
      </div>

      <form className="mt-4 grid gap-4 lg:grid-cols-6" onSubmit={(event) => { event.preventDefault(); submit.mutate(); }}>
        {correctionTarget ? (
          <div className="rounded border border-amber-400/30 bg-amber-400/10 p-3 text-sm text-amber-100 lg:col-span-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span>Correction for sale {correctionTarget.sale_date}</span>
              <button className="btn-secondary" type="button" onClick={cancelCorrection}>
                <X className="h-4 w-4" aria-hidden="true" />
                Cancel
              </button>
            </div>
          </div>
        ) : null}

        <label className="label">
          <span>Sale date</span>
          <input className="field" type="date" value={form.sale_date} onChange={(event) => setForm({ ...form, sale_date: event.target.value })} />
        </label>
        <label className="label">
          <span>Quantity</span>
          <input
            className="field"
            min={1}
            max={Math.max(1, maxQuantity)}
            type="number"
            value={form.quantity}
            onChange={(event) => setForm({ ...form, quantity: event.target.value })}
          />
          <span className="text-xs font-normal text-slate-500">Max {maxQuantity}</span>
        </label>
        <label className="label">
          <span>Sale price</span>
          <input className="field" inputMode="decimal" value={form.sale_price} onChange={(event) => setForm({ ...form, sale_price: event.target.value })} />
        </label>
        <label className="label">
          <span>Channel</span>
          <select className="field" value={form.channel} onChange={(event) => setForm({ ...form, channel: event.target.value as SaleRecord["channel"] })}>
            <option value="manual">Manual</option>
            <option value="ebay_au">eBay AU</option>
            <option value="other">Other</option>
          </select>
        </label>
        <label className="label">
          <span>Fees</span>
          <input
            className="field"
            inputMode="decimal"
            value={form.actual_fees_total}
            onChange={(event) => {
              setFeesTouched(true);
              setForm({ ...form, actual_fees_total: event.target.value });
            }}
          />
        </label>
        <label className="label">
          <span>Shipping cost</span>
          <input className="field" inputMode="decimal" value={form.actual_shipping_cost} onChange={(event) => setForm({ ...form, actual_shipping_cost: event.target.value })} />
        </label>
        <label className="label lg:col-span-2">
          <span>Listing</span>
          <select className="field" value={form.listing_draft} onChange={(event) => setForm({ ...form, listing_draft: event.target.value })}>
            <option value="">None</option>
            {(listingDrafts.data?.results ?? []).map((draft) => (
              <option key={draft.id} value={draft.id}>
                {draft.title || draft.channel} ({draft.status})
              </option>
            ))}
          </select>
        </label>
        <label className="label lg:col-span-2">
          <span>Cost basis override</span>
          <input className="field" inputMode="decimal" value={form.cost_basis_override} onChange={(event) => setForm({ ...form, cost_basis_override: event.target.value })} />
        </label>
        <label className="label lg:col-span-2">
          <span>Notes</span>
          <input className="field" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} />
        </label>

        <div className="grid gap-2 rounded border border-slate-800 bg-slate-950 p-3 text-sm text-slate-300 sm:grid-cols-3 lg:col-span-4">
          <p>Net ${moneyText(netProceeds)}</p>
          <p>Cost basis ${moneyText(allocatedCostBasis)}</p>
          <p>Realised P&L ${moneyText(realisedProfit)}</p>
        </div>
        <button className="btn-primary lg:col-span-2" disabled={submit.isPending || quantity < 1 || quantity > maxQuantity} type="submit">
          {correctionTarget ? "Save correction" : "Record sale"}
        </button>
      </form>

      {submit.error ? <EmptyState title="Unable to record sale" detail={(submit.error as Error).message} /> : null}

      <div className="mt-5 hidden overflow-x-auto sm:block">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="text-xs uppercase tracking-normal text-slate-500">
            <tr>
              <th className="py-2 pr-3">Date</th>
              <th className="py-2 pr-3">Qty</th>
              <th className="py-2 pr-3">Gross</th>
              <th className="py-2 pr-3">Net</th>
              <th className="py-2 pr-3">Cost</th>
              <th className="py-2 pr-3">P&L</th>
              <th className="py-2 pr-3">State</th>
              <th className="py-2 pr-0 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {(sales.data?.results ?? []).map((sale) => (
              <tr key={sale.id} className={sale.is_superseded ? "text-slate-500" : "text-slate-200"}>
                <td className="py-2 pr-3">{sale.sale_date}</td>
                <td className="py-2 pr-3">{sale.quantity}</td>
                <td className="py-2 pr-3">${sale.sale_price}</td>
                <td className="py-2 pr-3">${sale.net_proceeds}</td>
                <td className="py-2 pr-3">${sale.allocated_cost_basis}</td>
                <td className="py-2 pr-3">${sale.realised_profit}</td>
                <td className="py-2 pr-3">{sale.is_superseded ? "Superseded" : sale.corrected_from ? "Correction" : "Active"}</td>
                <td className="py-2 pr-0 text-right">
                  <button
                    className="btn-secondary"
                    disabled={sale.is_superseded}
                    type="button"
                    onClick={() => startCorrection(sale)}
                  >
                    <RotateCcw className="h-4 w-4" aria-hidden="true" />
                    Correct
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-5 space-y-3 sm:hidden">
        {(sales.data?.results ?? []).map((sale) => (
          <article key={sale.id} className={`rounded border border-slate-800 bg-slate-950/70 p-3 ${sale.is_superseded ? "text-slate-500" : "text-slate-200"}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-mono text-sm text-slate-100">{sale.sale_date}</p>
                <p className="mt-1 text-xs text-slate-500">Qty {sale.quantity}</p>
              </div>
              <span className="shrink-0 rounded border border-slate-700 px-2 py-1 text-xs text-slate-300">
                {sale.is_superseded ? "Superseded" : sale.corrected_from ? "Correction" : "Active"}
              </span>
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
              <MobileSaleMetric label="Gross" value={`$${sale.sale_price}`} />
              <MobileSaleMetric label="Net" value={`$${sale.net_proceeds}`} />
              <MobileSaleMetric label="Cost" value={`$${sale.allocated_cost_basis}`} />
              <MobileSaleMetric label="P&L" value={`$${sale.realised_profit}`} />
            </dl>
            <button
              className="btn-secondary mt-3 w-full"
              disabled={sale.is_superseded}
              type="button"
              onClick={() => startCorrection(sale)}
            >
              <RotateCcw className="h-4 w-4" aria-hidden="true" />
              Correct
            </button>
          </article>
        ))}
      </div>
      {sales.isLoading ? <EmptyState title="Loading sales" /> : null}
      {sales.data && sales.data.results.length === 0 ? <EmptyState title="No sales recorded" /> : null}
    </section>
  );
}

function MobileSaleMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded border border-slate-800 bg-slate-900 px-2 py-2">
      <dt className="text-xs uppercase tracking-normal text-slate-500">{label}</dt>
      <dd className="mt-1 break-words font-mono text-slate-100">{value}</dd>
    </div>
  );
}
