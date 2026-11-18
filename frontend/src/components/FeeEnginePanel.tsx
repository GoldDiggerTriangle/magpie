import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Plus, ReceiptText, Trash2 } from "lucide-react";
import { useState } from "react";
import { calculateOrderFees, getFeeCalendar, saveFeeCalendar } from "../api/feeEngine";
import type { FeeOrder, PlanPeriod, TierRate } from "../api/feeEngine";
import { AuthRequiredState } from "./AuthRequiredState";

const blankPeriod = (): PlanPeriod => ({ plan: "pro_basic", effective_from: "", effective_to: null, per_order_fee: "", international_pct: "", gst_treatment: "inclusive", source_note: "", rates: [] });
const blankRate = (): TierRate => ({ tier: "tier4", fvf_pct: "", threshold: "", above_pct: "" });
export function FeeEnginePanel() {
  const queryClient = useQueryClient();
  const calendar = useQuery({ queryKey: ["fee-calendar"], queryFn: getFeeCalendar });
  const [periods, setPeriods] = useState<PlanPeriod[] | null>(null);
  const [label, setLabel] = useState(""); const [source, setSource] = useState(""); const [url, setUrl] = useState("");
  const [review, setReview] = useState(false);
  const [baseId, setBaseId] = useState<string | null>(null);
  const current = calendar.data?.current;
  const save = useMutation({ mutationFn: () => saveFeeCalendar({ previous_id: baseId, label, source_note: source, source_url: url, periods: (periods ?? []).map(({ mapping: _mapping, ...period }) => period) }),
    onSuccess: () => { setPeriods(null); setReview(false); queryClient.invalidateQueries({ queryKey: ["fee-calendar"] }); } });
  function patchPeriod(i: number, patch: Partial<PlanPeriod>) { setReview(false); setPeriods((ps) => (ps ?? []).map((p, n) => n === i ? { ...p, ...patch } : p)); }
  function start() { setBaseId(current?.id ?? null); setPeriods(current ? structuredClone(current.periods) : []); setLabel(""); setSource(""); setUrl(current?.source_url ?? ""); setReview(false); }
  if (calendar.isPending) return <section className="settings-card" role="status">Loading fee calendar...</section>;
  if (calendar.isError) return <section className="settings-card"><AuthRequiredState detail="Fee calendar needs your Magpie session." /></section>;
  return <section className="settings-card fee-engine-panel" aria-labelledby="fee-engine-title">
    <header className="flex flex-wrap items-center justify-between gap-3"><h2 id="fee-engine-title" className="section-title inline-flex items-center gap-2"><ReceiptText aria-hidden="true" size={20} />Pro Basic fee calendar</h2><strong>{current ? `Version ${current.number}` : "schedule unknown"}</strong></header>
    <p className="mt-3">{calendar.data?.gst_note}</p>
    {current ? <div className="mt-3"><strong>{current.label}</strong>{current.periods.map((p, i) => <p key={i}>{p.plan} · {p.effective_from} → {p.effective_to ?? "open-ended"} · {p.rates.length} configured tiers</p>)}</div> : null}
    {periods === null ? <button className="btn-secondary mt-4" onClick={start}><Plus size={18} aria-hidden="true" />{current ? "Create revised calendar" : "Enter plan periods and rates"}</button> : <form className="mt-4 grid min-w-0 gap-4" onSubmit={(e) => { e.preventDefault(); setReview(true); }}>
      <label className="label">Version label<input required className="field" maxLength={120} value={label} onChange={(e) => { setLabel(e.target.value); setReview(false); }} /></label>
      <label className="label">Source / provenance<textarea required className="field" value={source} onChange={(e) => { setSource(e.target.value); setReview(false); }} /></label>
      <label className="label">Source link<input className="field" type="url" value={url} onChange={(e) => { setUrl(e.target.value); setReview(false); }} /></label>
      {(periods ?? []).map((p, i) => <fieldset className="fee-period" key={i}><legend>Plan period {i + 1}</legend>
        <div className="fee-form-grid"><label className="label">Plan<select className="field" value={p.plan} onChange={(e) => patchPeriod(i, { plan: e.target.value })}><option value="pro_basic">Pro Basic</option><option value="pro_starter">Pro Starter (no API)</option><option value="free_selling">Free selling (no API)</option></select></label>
          <label className="label">Effective from<input required type="date" className="field" value={p.effective_from} onChange={(e) => patchPeriod(i, { effective_from: e.target.value })} /></label>
          <label className="label">End date (exclusive, optional)<input type="date" className="field" value={p.effective_to ?? ""} onChange={(e) => patchPeriod(i, { effective_to: e.target.value || null })} /></label>
          <label className="label">Fixed fee per order<input required className="field" inputMode="decimal" value={p.per_order_fee} onChange={(e) => patchPeriod(i, { per_order_fee: e.target.value })} /></label>
          <label className="label">International fee %<input required className="field" inputMode="decimal" value={p.international_pct} onChange={(e) => patchPeriod(i, { international_pct: e.target.value })} /></label>
          <label className="label">Period source / date confirmation<input required className="field" value={p.source_note} onChange={(e) => patchPeriod(i, { source_note: e.target.value })} /></label></div>
        {p.rates.map((r, j) => <fieldset className="fee-rate" key={j}><legend>Tier rate {j + 1} · GST-inclusive</legend><div className="fee-form-grid">
          <label className="label">Tier<select className="field" value={r.tier} onChange={(e) => patchPeriod(i, { rates: p.rates.map((v, n) => n === j ? { ...v, tier: e.target.value } : v) })}>{[1, 2, 3, 4].map((v) => <option key={v} value={`tier${v}`}>Tier {v}</option>)}</select></label>
          {([['fvf_pct', 'FVF % up to threshold'], ['threshold', 'Per-item threshold'], ['above_pct', 'FVF % above threshold']] as const).map(([k, name]) => <label className="label" key={k}>{name}<input required className="field" inputMode="decimal" value={r[k]} onChange={(e) => patchPeriod(i, { rates: p.rates.map((v, n) => n === j ? { ...v, [k]: e.target.value } : v) })} /></label>)}</div>
          <button className="btn-secondary mt-2" type="button" aria-label={`Remove rate ${j + 1} from period ${i + 1}`} onClick={() => patchPeriod(i, { rates: p.rates.filter((_, n) => n !== j) })}><Trash2 size={18} /></button></fieldset>)}
        <div className="mt-3 flex flex-wrap gap-3"><button type="button" className="btn-secondary" onClick={() => patchPeriod(i, { rates: [...p.rates, blankRate()] })}><Plus size={18} />Add tier</button><button type="button" className="btn-secondary" onClick={() => { setPeriods(periods.filter((_, n) => n !== i)); setReview(false); }}><Trash2 size={18} />Remove period</button></div>
      </fieldset>)}
      <div className="flex flex-wrap gap-3"><button className="btn-secondary" type="button" onClick={() => { setPeriods([...(periods ?? []), blankPeriod()]); setReview(false); }}><Plus size={18} />Add period</button><button type="submit" className="btn-primary">Review new version</button><button className="btn-secondary" type="button" onClick={() => { setPeriods(null); setReview(false); }}>Cancel</button></div>
      {review ? <div className="fee-review" role="region" aria-label="Review fee calendar"><h3>Confirm new immutable version</h3><p>{label} · {source}</p>{periods.map((p, i) => <div key={i}><strong>{p.plan} · {p.effective_from} → {p.effective_to ?? "open-ended"}</strong><p>Fixed ${p.per_order_fee} per order · international {p.international_pct}% · GST-inclusive</p><p>{p.source_note}</p>{p.rates.map((r) => <p key={r.tier}>{r.tier}: {r.fvf_pct}% up to ${r.threshold} per item; {r.above_pct}% above</p>)}</div>)}<p>Gaps and missing tiers stay unknown. Existing sale results are unchanged.</p><button className="btn-primary mt-3" type="button" disabled={save.isPending} onClick={() => save.mutate()}><Check size={18} />Save confirmed version</button></div> : null}
      {save.error ? <p role="alert">{save.error.message}</p> : null}
    </form>}
    <FeeSample />
    <details className="mt-5"><summary>Legacy schedules — unverified history</summary>{calendar.data?.legacy.map((v) => <p key={v.id}>{v.name} · {v.label}</p>)}</details>
    <details className="mt-3"><summary>Immutable version history</summary>{calendar.data?.versions.map((v) => <details className="mt-3" key={v.id}><summary>Version {v.number} · {v.label}</summary><p>{v.source_note}</p>{v.source_url ? <a href={v.source_url} target="_blank" rel="noreferrer">Source</a> : null}{v.periods.map((p, i) => <div className="mt-3" key={i}><strong>{p.plan} · {p.effective_from} → {p.effective_to ?? "open-ended"}</strong><p>{p.source_note}</p><p>Fixed ${p.per_order_fee} per order · international {p.international_pct}% · GST-inclusive</p>{p.rates.map((r) => <p key={r.tier}>{r.tier}: {r.fvf_pct}% up to ${r.threshold} per item; {r.above_pct}% above</p>)}</div>)}</details>)}</details>
  </section>;
}

function FeeSample() {
  const [price, setPrice] = useState(""); const [cost, setCost] = useState("");
  const [category, setCategory] = useState("gold"); const [country, setCountry] = useState("AU");
  const [day, setDay] = useState(""); const [postage, setPostage] = useState("0.00");
  const preview = useMutation({ mutationFn: () => calculateOrderFees({ sale_date: day, destination_country: country, postage, lines: [{ key: "sample", item_total: price, quantity: 1, category_slug: category }] } satisfies FeeOrder) });
  const result = preview.data;
  const revenue = result?.lines.sample?.revenue;
  return <details className="mt-5"><summary>Check a what-if profit figure</summary><form className="fee-form-grid mt-3" onSubmit={(e) => { e.preventDefault(); preview.mutate(); }}>
    <label className="label">Sale date<input required className="field" type="date" value={day} onChange={(e) => { setDay(e.target.value); preview.reset(); }} /></label>
    <label className="label">Category<select className="field" value={category} onChange={(e) => { setCategory(e.target.value); preview.reset(); }}>{["gold", "coins", "stamps", "banknotes", "collectibles", "phones-electronics", "tools"].map((c) => <option key={c}>{c}</option>)}</select></label>
    <label className="label">Seller-receives item price<input required className="field" inputMode="decimal" value={price} onChange={(e) => { setPrice(e.target.value); preview.reset(); }} /></label>
    <label className="label">All-in direct costs<input required className="field" inputMode="decimal" value={cost} onChange={(e) => { setCost(e.target.value); preview.reset(); }} /></label>
    <label className="label">Buyer-paid postage<input className="field" inputMode="decimal" value={postage} onChange={(e) => { setPostage(e.target.value); preview.reset(); }} /></label>
    <label className="label">Delivery country (ISO code)<input required className="field" maxLength={2} value={country} onChange={(e) => { setCountry(e.target.value.toUpperCase()); preview.reset(); }} /></label>
    <button className="btn-secondary" type="submit" disabled={preview.isPending}><ReceiptText size={18} />Calculate what-if</button>
  </form>{result ? <div className="fee-review mt-3" role="status"><strong>{result.label}</strong><p>Fees: {result.fee_total === null ? result.state : `$${result.fee_total}`}</p><p>What-if profit: {result.fee_total !== null && revenue && cost && Number.isFinite(Number(cost)) ? `$${(Number(revenue) - Number(result.fee_total) - Number(cost)).toFixed(2)}` : "Unknown"}</p><p>GST added: $0.00 · calculation only, not saved as evidence</p></div> : null}{preview.error ? <p role="alert">{preview.error.message}</p> : null}</details>;
}
