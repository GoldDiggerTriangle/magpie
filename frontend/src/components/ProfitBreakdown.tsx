import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Calculator, Save } from "lucide-react";
import { useEffect, useState } from "react";

import { updateItem } from "../api/items";
import { getReportProfit, getValuationReport } from "../api/valuation";
import type { InventoryItemDetail, ProfitBreakdown as ProfitBreakdownType, UUID } from "../types";

function money(value: string | null | undefined) {
  return value ?? "-";
}

function margin(value: string) {
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function ProjectionRow({ row }: { row: ProfitBreakdownType }) {
  return (
    <div className="rounded border border-slate-800 bg-slate-900 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-slate-100">{row.label ?? "Manual"} · {row.sale_price}</p>
        <p className={Number(row.net_profit) >= 0 ? "text-sm font-semibold text-emerald-200" : "text-sm font-semibold text-rose-200"}>
          {row.net_profit} ({margin(row.margin_pct)})
        </p>
      </div>
      <p className="mt-2 text-xs text-slate-400">
        Fees {row.final_value_fee} + {row.per_order_fee} + {row.promoted_fee}; GST {row.gst_on_fees}; ship {row.outbound_shipping}; pack {row.packaging}; cost {row.true_cost}
      </p>
    </div>
  );
}

export function ProfitBreakdown({ item, reportId }: { item: InventoryItemDetail; reportId: UUID | null }) {
  const queryClient = useQueryClient();
  const report = useQuery({
    queryKey: ["valuation-report", reportId],
    queryFn: () => getValuationReport(reportId!),
    enabled: Boolean(reportId)
  });
  const [costs, setCosts] = useState({
    acquisition_cost: item.acquisition_cost ?? "",
    refurb_cost: item.refurb_cost ?? "",
    inbound_shipping_cost: item.inbound_shipping_cost ?? "",
    est_outbound_shipping: item.est_outbound_shipping ?? "",
    est_packaging_cost: item.est_packaging_cost ?? ""
  });
  const [manualPrice, setManualPrice] = useState("");
  const manualProfit = useQuery({
    queryKey: ["valuation-profit", reportId, manualPrice],
    queryFn: () => getReportProfit(reportId!, manualPrice),
    enabled: false
  });

  useEffect(() => {
    setCosts({
      acquisition_cost: item.acquisition_cost ?? "",
      refurb_cost: item.refurb_cost ?? "",
      inbound_shipping_cost: item.inbound_shipping_cost ?? "",
      est_outbound_shipping: item.est_outbound_shipping ?? "",
      est_packaging_cost: item.est_packaging_cost ?? ""
    });
  }, [item]);

  const saveCosts = useMutation({
    mutationFn: () => updateItem(item.id, {
      acquisition_cost: costs.acquisition_cost || null,
      refurb_cost: costs.refurb_cost || null,
      inbound_shipping_cost: costs.inbound_shipping_cost || null,
      est_outbound_shipping: costs.est_outbound_shipping || null,
      est_packaging_cost: costs.est_packaging_cost || null
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["item", item.id] });
      queryClient.invalidateQueries({ queryKey: ["valuation-report", reportId] });
    }
  });

  return (
    <section className="rounded border border-slate-800 bg-slate-950/40 p-4">
      <h2 className="section-title">Profit breakdown</h2>
      <div className="mt-4 grid gap-3 sm:grid-cols-5">
        {Object.entries({
          acquisition_cost: "Acquisition",
          refurb_cost: "Refurb",
          inbound_shipping_cost: "Inbound ship",
          est_outbound_shipping: "Outbound ship",
          est_packaging_cost: "Packaging"
        }).map(([key, label]) => (
          <label className="label" key={key}>
            <span>{label}</span>
            <input className="field" inputMode="decimal" value={costs[key as keyof typeof costs]} onChange={(event) => setCosts({ ...costs, [key]: event.target.value })} />
          </label>
        ))}
      </div>
      <button className="btn-secondary mt-3 gap-2" disabled={saveCosts.isPending} type="button" onClick={() => saveCosts.mutate()}>
        <Save className="h-4 w-4" aria-hidden="true" />
        Save costs
      </button>

      {!reportId ? <p className="mt-4 text-sm text-slate-400">No current valuation report.</p> : null}
      <div className="mt-4 space-y-3">
        {(report.data?.profit_projection ?? []).map((row) => <ProjectionRow key={row.label} row={row} />)}
      </div>

      {reportId ? (
        <div className="mt-4">
          <div className="flex flex-col gap-3 sm:flex-row">
            <label className="label sm:w-48">
              <span>Manual price</span>
              <input className="field" inputMode="decimal" value={manualPrice} onChange={(event) => setManualPrice(event.target.value)} />
            </label>
            <button className="btn-secondary mt-6 gap-2 sm:mt-auto" disabled={!manualPrice || manualProfit.isFetching} type="button" onClick={() => manualProfit.refetch()}>
              <Calculator className="h-4 w-4" aria-hidden="true" />
              Calculate
            </button>
          </div>
          {manualProfit.data ? <div className="mt-3"><ProjectionRow row={{ ...manualProfit.data, label: `Manual ${money(manualPrice)}` }} /></div> : null}
        </div>
      ) : null}
    </section>
  );
}
