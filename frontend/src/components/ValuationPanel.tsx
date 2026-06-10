import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, RefreshCw, Wifi } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { listComparables } from "../api/comparables";
import { ApiError } from "../api/client";
import { listFeeSchedules } from "../api/fees";
import { createValuationReport, getMetalSpot, listItemValuationReports, setCurrentValuationReport } from "../api/valuation";
import type { InventoryItemDetail, MetalSpotQuote, UUID, ValuationReportPayload } from "../types";
import { ConfidenceControl } from "./ConfidenceControl";

interface Selection {
  included: boolean;
  exclude_reason: string;
}

const commodityDefaults = {
  metal: "gold",
  currency: "AUD",
  weight_g: "",
  fineness: "",
  karat: "",
  spot_price_per_g: "",
  buy_margin_pct: ""
};

type Strategy = "comp_based" | "commodity_manual" | "commodity_live";

export function ValuationPanel({ item }: { item: InventoryItemDetail }) {
  const queryClient = useQueryClient();
  const defaultStrategy: Strategy = item.category_name?.toLowerCase().includes("gold") ? "commodity_live" : "comp_based";
  const comparables = useQuery({ queryKey: ["comparables", item.id], queryFn: () => listComparables({ item: item.id }) });
  const reports = useQuery({ queryKey: ["valuation-reports", item.id], queryFn: () => listItemValuationReports(item.id) });
  const schedules = useQuery({ queryKey: ["fee-schedules"], queryFn: listFeeSchedules });
  const [strategy, setStrategy] = useState<Strategy>(defaultStrategy);
  const [selection, setSelection] = useState<Record<UUID, Selection>>({});
  const [commodityInputs, setCommodityInputs] = useState<Record<string, string>>(commodityDefaults);
  const [liveQuote, setLiveQuote] = useState<MetalSpotQuote | null>(null);
  const [liveFallback, setLiveFallback] = useState(false);
  const [liveMessage, setLiveMessage] = useState("");
  const [feeSchedule, setFeeSchedule] = useState<UUID | "">("");
  const [makeCurrent, setMakeCurrent] = useState(true);
  const [confidence, setConfidence] = useState<{ score: number | null; reason: string }>({ score: null, reason: "" });
  const [isOverridden, setIsOverridden] = useState(false);
  const [overrideReason, setOverrideReason] = useState("");
  const [prices, setPrices] = useState({
    suggested_price: "",
    fast_sale_price: "",
    patient_price: "",
    min_acceptable_price: ""
  });
  const [error, setError] = useState("");

  useEffect(() => setStrategy(defaultStrategy), [defaultStrategy, item.id]);
  useEffect(() => {
    setLiveQuote(null);
    setLiveFallback(false);
    setLiveMessage("");
  }, [item.id]);

  useEffect(() => {
    const next: Record<UUID, Selection> = {};
    for (const comp of comparables.data?.results ?? []) {
      next[comp.id] = selection[comp.id] ?? { included: true, exclude_reason: "" };
    }
    setSelection(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [comparables.data?.results]);

  useEffect(() => {
    const active = schedules.data?.results.find((schedule) => schedule.is_active) ?? schedules.data?.results[0];
    if (active && !feeSchedule) {
      setFeeSchedule(active.id);
    }
  }, [feeSchedule, schedules.data?.results]);

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["valuation-reports", item.id] });
    queryClient.invalidateQueries({ queryKey: ["item", item.id] });
  };

  const createMutation = useMutation({
    mutationFn: (payload: ValuationReportPayload) => createValuationReport(item.id, payload),
    onSuccess: refresh,
    onError: (mutationError) => {
      if (isManualSpotFallback(mutationError)) {
        setLiveFallback(true);
        setLiveMessage(fallbackMessage(mutationError));
        setStrategy("commodity_manual");
      }
    }
  });
  const setCurrentMutation = useMutation({
    mutationFn: (reportId: UUID) => setCurrentValuationReport(reportId),
    onSuccess: refresh
  });
  const spotMutation = useMutation({
    mutationFn: (refreshSpot: boolean) => getMetalSpot(
      commodityInputs.metal || "gold",
      commodityInputs.currency || "AUD",
      refreshSpot
    ),
    onSuccess: (quote) => {
      setLiveQuote(quote);
      setLiveFallback(false);
      setLiveMessage("");
      setCommodityInputs((current) => ({
        ...current,
        metal: quote.metal,
        currency: quote.currency,
        spot_price_per_g: quote.price_per_gram
      }));
    },
    onError: (mutationError) => {
      setLiveQuote(null);
      setLiveFallback(true);
      setLiveMessage(fallbackMessage(mutationError));
    }
  });

  const includedCount = useMemo(
    () => Object.values(selection).filter((entry) => entry.included).length,
    [selection]
  );
  const intrinsicPreview = useMemo(
    () => commodityIntrinsicPreview(commodityInputs, liveQuote),
    [commodityInputs, liveQuote]
  );

  function updateSelection(id: UUID, patch: Partial<Selection>) {
    setSelection({ ...selection, [id]: { ...selection[id], ...patch } });
  }

  function submitReport() {
    if (isOverridden && !overrideReason.trim()) {
      setError("Override reason is required when manual override is enabled.");
      return;
    }
    if (strategy === "comp_based") {
      const missingExcludeReason = Object.values(selection).some((entry) => !entry.included && !entry.exclude_reason.trim());
      if (missingExcludeReason) {
        setError("Excluded comparables require an exclusion reason.");
        return;
      }
    }
    if (strategy === "commodity_manual" || strategy === "commodity_live") {
      if (!commodityInputs.weight_g || (!commodityInputs.fineness && !commodityInputs.karat)) {
        setError("Commodity valuation requires weight and fineness or karat.");
        return;
      }
      if (strategy === "commodity_manual" && !commodityInputs.spot_price_per_g) {
        setError("Manual commodity valuation requires a spot price.");
        return;
      }
    }

    setError("");
    const inputs = commodityInputsForStrategy(commodityInputs, strategy);
    const payload: ValuationReportPayload = {
      strategy,
      is_current: makeCurrent,
      fee_schedule: feeSchedule || null,
      confidence_score: confidence.score,
      confidence_reason: confidence.reason,
      is_overridden: isOverridden,
      override_reason: overrideReason,
      suggested_price: prices.suggested_price || null,
      fast_sale_price: prices.fast_sale_price || null,
      patient_price: prices.patient_price || null,
      min_acceptable_price: prices.min_acceptable_price || null,
      inputs,
      comp_links: strategy === "comp_based"
        ? (comparables.data?.results ?? []).map((comp) => ({
          comparable: comp.id,
          included: selection[comp.id]?.included ?? true,
          exclude_reason: selection[comp.id]?.exclude_reason ?? ""
        }))
        : []
    };
    createMutation.mutate(payload);
  }

  return (
    <section className="rounded border border-slate-800 bg-slate-950/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="section-title">Valuation</h2>
        <span className="text-sm text-slate-400">{includedCount} comparable{includedCount === 1 ? "" : "s"} included</span>
      </div>

      {error ? <p className="mt-3 rounded border border-rose-400/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-100">{error}</p> : null}
      {createMutation.error && !isManualSpotFallback(createMutation.error) ? <p className="mt-3 rounded border border-rose-400/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-100">Unable to create valuation report.</p> : null}

      <div className="mt-4 grid gap-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="label">
            <span>Strategy</span>
            <select className="field" value={strategy} onChange={(event) => setStrategy(event.target.value as Strategy)}>
              <option value="comp_based">Comparable-based</option>
              <option value="commodity_live">Commodity live</option>
              <option value="commodity_manual">Commodity manual</option>
            </select>
          </label>
          <label className="label">
            <span>Fee schedule</span>
            <select className="field" value={feeSchedule} onChange={(event) => setFeeSchedule(event.target.value as UUID)}>
              <option value="">Active schedule</option>
              {(schedules.data?.results ?? []).map((schedule) => <option key={schedule.id} value={schedule.id}>{schedule.name}</option>)}
            </select>
          </label>
          <label className="flex items-end gap-2 text-sm font-medium text-slate-300">
            <input checked={makeCurrent} type="checkbox" onChange={(event) => setMakeCurrent(event.target.checked)} />
            Make current
          </label>
        </div>

        {strategy === "comp_based" ? (
          <div className="space-y-3">
            {(comparables.data?.results ?? []).map((comp) => {
              const entry = selection[comp.id] ?? { included: true, exclude_reason: "" };
              return (
                <div key={comp.id} className="rounded border border-slate-800 bg-slate-900 p-3">
                  <label className="flex items-start gap-3 text-sm text-slate-200">
                    <input checked={entry.included} type="checkbox" onChange={(event) => updateSelection(comp.id, { included: event.target.checked })} />
                    <span className="min-w-0">
                      <span className="block font-semibold">{comp.title || comp.source || comp.kind}</span>
                      <span className="block text-xs text-slate-400">{comp.kind} · {comp.price ?? "-"} {comp.currency}</span>
                    </span>
                  </label>
                  {!entry.included ? (
                    <label className="label mt-3">
                      <span>Exclusion reason</span>
                      <input className="field" value={entry.exclude_reason} onChange={(event) => updateSelection(comp.id, { exclude_reason: event.target.value })} />
                    </label>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="grid gap-3">
            <div className="grid gap-3 sm:grid-cols-6">
              <label className="label">
                <span>Metal</span>
                <select className="field" value={commodityInputs.metal} onChange={(event) => setCommodityInputs({ ...commodityInputs, metal: event.target.value })}>
                  <option value="gold">Gold</option>
                  <option value="silver">Silver</option>
                  <option value="platinum">Platinum</option>
                  <option value="palladium">Palladium</option>
                </select>
              </label>
              <label className="label">
                <span>Currency</span>
                <input className="field" maxLength={3} value={commodityInputs.currency} onChange={(event) => setCommodityInputs({ ...commodityInputs, currency: event.target.value.toUpperCase() })} />
              </label>
              <label className="label">
                <span>Weight g</span>
                <input className="field" inputMode="decimal" value={commodityInputs.weight_g} onChange={(event) => setCommodityInputs({ ...commodityInputs, weight_g: event.target.value })} />
              </label>
              <label className="label">
                <span>Fineness</span>
                <input className="field" inputMode="decimal" value={commodityInputs.fineness} onChange={(event) => setCommodityInputs({ ...commodityInputs, fineness: event.target.value })} />
              </label>
              <label className="label">
                <span>Karat</span>
                <input className="field" inputMode="decimal" value={commodityInputs.karat} onChange={(event) => setCommodityInputs({ ...commodityInputs, karat: event.target.value })} />
              </label>
              <label className="label">
                <span>Buy margin %</span>
                <input className="field" inputMode="decimal" value={commodityInputs.buy_margin_pct} onChange={(event) => setCommodityInputs({ ...commodityInputs, buy_margin_pct: event.target.value })} />
              </label>
            </div>

            {strategy === "commodity_live" ? (
              <div className="rounded border border-slate-800 bg-slate-900 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <button className="btn-secondary gap-2" disabled={spotMutation.isPending} type="button" onClick={() => spotMutation.mutate(false)}>
                    <Wifi className="h-4 w-4" aria-hidden="true" />
                    Fetch live spot
                  </button>
                  <button className="btn-secondary gap-2" disabled={spotMutation.isPending} type="button" onClick={() => spotMutation.mutate(true)}>
                    <RefreshCw className="h-4 w-4" aria-hidden="true" />
                    Refresh
                  </button>
                </div>
                {liveQuote ? (
                  <div className="mt-3 grid gap-1 text-sm text-slate-300">
                    <p>
                      {liveQuote.price_per_gram} {liveQuote.currency}/g · {liveQuote.source} · As of {formatTimestamp(liveQuote.as_of)}
                    </p>
                    <p className="text-xs text-slate-500">
                      Fetched {formatTimestamp(liveQuote.fetched_at)} · {liveQuote.cache_hit ? "cache hit" : "fresh fetch"} · Provider {liveQuote.provider_price} {liveQuote.provider_units}
                    </p>
                  </div>
                ) : null}
                {liveFallback ? (
                  <p className="mt-3 rounded border border-amber-300/30 bg-amber-300/10 px-3 py-2 text-sm text-amber-100">
                    {liveMessage || "Live spot is unavailable. Enter a manual spot price."}
                  </p>
                ) : null}
              </div>
            ) : null}

            {(strategy === "commodity_manual" || liveFallback) ? (
              <label className="label max-w-xs">
                <span>Manual spot / g</span>
                <input className="field" inputMode="decimal" value={commodityInputs.spot_price_per_g} onChange={(event) => setCommodityInputs({ ...commodityInputs, spot_price_per_g: event.target.value })} />
              </label>
            ) : null}

            {intrinsicPreview ? (
              <p className="text-sm text-slate-300">
                Intrinsic {intrinsicPreview} {commodityInputs.currency || "AUD"}
              </p>
            ) : null}
          </div>
        )}

        <ConfidenceControl score={confidence.score} reason={confidence.reason} onChange={setConfidence} />

        <div className="grid gap-3 sm:grid-cols-4">
          {Object.entries({
            fast_sale_price: "Fast sale",
            suggested_price: "Suggested",
            patient_price: "Patient",
            min_acceptable_price: "Minimum"
          }).map(([key, label]) => (
            <label className="label" key={key}>
              <span>{label}</span>
              <input className="field" inputMode="decimal" value={prices[key as keyof typeof prices]} onChange={(event) => setPrices({ ...prices, [key]: event.target.value })} />
            </label>
          ))}
        </div>

        <label className="flex items-center gap-2 text-sm font-medium text-slate-300">
          <input checked={isOverridden} type="checkbox" onChange={(event) => setIsOverridden(event.target.checked)} />
          Manual override
        </label>
        {isOverridden ? (
          <label className="label">
            <span>Override reason</span>
            <textarea className="field min-h-20" value={overrideReason} onChange={(event) => setOverrideReason(event.target.value)} />
          </label>
        ) : null}

        <button className="btn-primary w-fit" disabled={createMutation.isPending} type="button" onClick={submitReport}>
          Create valuation report
        </button>
      </div>

      <div className="mt-6 space-y-3">
        {(reports.data?.results ?? []).map((report) => (
          <div key={report.id} className="rounded border border-slate-800 bg-slate-900 p-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold text-slate-100">{report.strategy}</p>
                  {report.is_current ? <CheckCircle2 className="h-4 w-4 text-cyan-200" aria-label="Current valuation" /> : null}
                </div>
                <p className="mt-1 text-xs text-slate-400">
                  Low {report.estimate_low ?? "-"} · Median {report.estimate_median ?? "-"} · High {report.estimate_high ?? "-"}
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  Fast {report.fast_sale_price ?? "-"} · Suggested {report.suggested_price ?? "-"} · Patient {report.patient_price ?? "-"} · Min {report.min_acceptable_price ?? "-"}
                </p>
                {report.confidence_score !== null ? <p className="mt-2 text-sm text-slate-300">Confidence {report.confidence_score}: {report.confidence_reason}</p> : null}
              </div>
              {!report.is_current ? (
                <button className="btn-secondary" disabled={setCurrentMutation.isPending} type="button" onClick={() => setCurrentMutation.mutate(report.id)}>
                  Make current
                </button>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function commodityInputsForStrategy(inputs: Record<string, string>, strategy: Strategy) {
  if (strategy === "comp_based") {
    return {};
  }
  const payload = Object.fromEntries(
    Object.entries(inputs).filter(([, value]) => value.trim() !== "")
  );
  if (strategy === "commodity_live") {
    delete payload.spot_price_per_g;
  }
  return payload;
}

function commodityIntrinsicPreview(
  inputs: Record<string, string>,
  liveQuote: MetalSpotQuote | null
) {
  const weight = Number(inputs.weight_g);
  const spot = Number(liveQuote?.price_per_gram ?? inputs.spot_price_per_g);
  const fineness = inputs.fineness
    ? Number(inputs.fineness)
    : inputs.karat
      ? Number(inputs.karat) / 24
      : NaN;
  if (!Number.isFinite(weight) || !Number.isFinite(spot) || !Number.isFinite(fineness)) {
    return "";
  }
  if (weight <= 0 || spot <= 0 || fineness <= 0) {
    return "";
  }
  return (weight * fineness * spot).toFixed(2);
}

function formatTimestamp(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function isManualSpotFallback(error: unknown) {
  if (!(error instanceof ApiError) || typeof error.data !== "object" || error.data === null) {
    return false;
  }
  return (error.data as { needs_manual_spot?: unknown }).needs_manual_spot === true;
}

function fallbackMessage(error: unknown) {
  if (error instanceof ApiError && typeof error.data === "object" && error.data !== null) {
    const detail = (error.data as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
  }
  return "Live spot is unavailable. Enter a manual spot price.";
}

