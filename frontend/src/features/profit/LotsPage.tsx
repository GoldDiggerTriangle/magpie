import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Boxes, LockKeyhole, PlusCircle, Scale, Trash2 } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { allocateLotEqual, allocateLotManual, allocateLotProportional, createLot, getLot, listLots, listSources, scrapLotMember } from "../../api/lots";
import { AuthRequiredState } from "../../components/AuthRequiredState";
import { EmptyState } from "../../components/EmptyState";
import type { LotMember, LotSummary, Source, UUID } from "../../types";

const currencyFormatter = new Intl.NumberFormat("en-AU", { style: "currency", currency: "AUD" });

export function LotsPage() {
  const lots = useQuery({ queryKey: ["lots"], queryFn: listLots });
  const sources = useQuery({ queryKey: ["sources"], queryFn: listSources });
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ label: "", purchase_date: "", total_cost: "", source: "", note: "" });
  const create = useMutation({
    mutationFn: () => createLot({
      label: form.label,
      purchase_date: form.purchase_date,
      total_cost: form.total_cost,
      source: form.source || null,
      note: form.note
    }),
    onSuccess: () => {
      setForm({ label: "", purchase_date: "", total_cost: "", source: "", note: "" });
      queryClient.invalidateQueries({ queryKey: ["lots"] });
    }
  });

  if (lots.error) {
    return <LotFrame><AuthRequiredState detail="Lots need your Magpie session. Sign in, then return to Lots." /></LotFrame>;
  }

  return (
    <LotFrame>
      <header className="lot-hero">
        <div>
          <p className="ledger-kicker">Lot manager</p>
          <h1 className="ledger-title">Purchase lots</h1>
          <p className="ledger-subtitle">One purchase event, human-driven allocations, and locked costs after sale or scrap.</p>
        </div>
        <Boxes className="h-8 w-8 text-[#1d4ed8]" aria-hidden="true" />
      </header>

      <section className="lot-card">
        <h2>Create lot</h2>
        <div className="lot-form-grid">
          <label className="label">
            <span>Label</span>
            <input className="field" value={form.label} onChange={(event) => setForm({ ...form, label: event.target.value })} />
          </label>
          <label className="label">
            <span>Purchase date</span>
            <input className="field" type="date" value={form.purchase_date} onChange={(event) => setForm({ ...form, purchase_date: event.target.value })} />
          </label>
          <label className="label">
            <span>Total all-in cost</span>
            <input className="field" inputMode="decimal" value={form.total_cost} onChange={(event) => setForm({ ...form, total_cost: event.target.value })} />
          </label>
          <label className="label">
            <span>Source</span>
            <select className="field" value={form.source} onChange={(event) => setForm({ ...form, source: event.target.value })}>
              <option value="">No source yet</option>
              {(sources.data?.results ?? []).map((source) => <option key={source.id} value={source.id}>{source.name}</option>)}
            </select>
          </label>
          <label className="label lot-span-2">
            <span>Note</span>
            <textarea className="field min-h-24" value={form.note} onChange={(event) => setForm({ ...form, note: event.target.value })} />
          </label>
        </div>
        <button className="ledger-button ledger-button-primary" disabled={!form.label || !form.purchase_date || !form.total_cost || create.isPending} onClick={() => create.mutate()} type="button">
          <PlusCircle className="h-4 w-4" aria-hidden="true" />
          Create lot
        </button>
      </section>

      <section className="lot-card">
        <h2>Open lots</h2>
        <div className="lot-list">
          {lots.isLoading ? <EmptyState title="Loading lots" /> : null}
          {(lots.data?.results ?? []).length === 0 ? <EmptyState title="No lots yet" detail="Create a purchase lot, add items to it from item edit, then allocate cost." /> : null}
          {(lots.data?.results ?? []).map((lot) => <LotListRow key={lot.id} lot={lot} />)}
        </div>
      </section>
    </LotFrame>
  );
}

export function LotDetail() {
  const { id } = useParams();
  const lotId = id as UUID;
  const queryClient = useQueryClient();
  const lot = useQuery({ queryKey: ["lot", lotId], queryFn: () => getLot(lotId), enabled: Boolean(lotId) });
  const [manual, setManual] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!lot.data) return;
    setManual(Object.fromEntries(lot.data.members.map((member) => [member.id, member.acquisition_cost ?? "0.00"])));
  }, [lot.data]);

  const refresh = (data?: LotSummary) => {
    if (data) queryClient.setQueryData(["lot", lotId], data);
    queryClient.invalidateQueries({ queryKey: ["lots"] });
    queryClient.invalidateQueries({ queryKey: ["profit-ledger"] });
  };
  const equal = useMutation({ mutationFn: () => allocateLotEqual(lotId), onSuccess: refresh });
  const proportional = useMutation({ mutationFn: () => allocateLotProportional(lotId), onSuccess: refresh });
  const manualSave = useMutation({
    mutationFn: () => allocateLotManual(
      lotId,
      Object.entries(manual).map(([item, amount]) => ({ item, amount }))
    ),
    onSuccess: refresh
  });
  const scrap = useMutation({ mutationFn: (item: UUID) => scrapLotMember(lotId, item), onSuccess: refresh });

  if (lot.error) {
    return <LotFrame><AuthRequiredState detail="This lot needs your Magpie session. Sign in, then return to Lots." /></LotFrame>;
  }
  if (lot.isLoading || !lot.data) {
    return <LotFrame><EmptyState title="Loading lot" /></LotFrame>;
  }

  const data = lot.data;
  const live = liveTally(data, manual);

  return (
    <LotFrame>
      <header className="lot-hero">
        <div>
          <p className="ledger-kicker">Lot allocation</p>
          <h1 className="ledger-title">{data.label}</h1>
          <p className="ledger-subtitle">{data.source ? `${data.source.name} · ${sourceTypeLabel(data.source.type)}` : "No source tagged"} · bought {data.purchase_date}</p>
        </div>
      </header>

      <section className={`lot-tally ${live.remainder < 0 ? "lot-tally-warning" : ""}`} aria-label="Allocation tally">
        <strong>{live.label}</strong>
        {data.is_partially_allocated ? <span>Partially allocated lot. Remainder stays visible until you finish.</span> : null}
        {live.remainder < 0 ? <span>Over-allocation warning: member shares exceed the lot total.</span> : null}
      </section>

      <section className="lot-card lot-pnl-card">
        <div className="lot-card-title">
          <Scale className="h-5 w-5" aria-hidden="true" />
          <h2>Lot P&amp;L</h2>
        </div>
        <dl className="lot-metrics">
          <Metric label="Total cost" value={formatCurrency(data.pnl.total_cost)} />
          <Metric label="Allocated" value={formatCurrency(data.pnl.allocated)} />
          <Metric label="Unallocated" value={formatCurrency(data.pnl.unallocated)} />
          <Metric label="Realised revenue" value={formatCurrency(data.pnl.realised_revenue)} />
          <Metric label="Realised profit" value={formatCurrency(data.pnl.realised_profit)} tone={Number(data.pnl.realised_profit) < 0 ? "loss" : "normal"} />
          <Metric label="Unsold basis" value={formatCurrency(data.pnl.remaining_cost_basis)} />
        </dl>
        <p className="lot-recovered">{data.pnl.recovered_label}</p>
      </section>

      <section className="lot-card">
        <div className="lot-card-title">
          <LockKeyhole className="h-5 w-5" aria-hidden="true" />
          <h2>Members</h2>
        </div>
        <div className="lot-actions">
          <button className="ledger-button" onClick={() => equal.mutate()} type="button">Equal split unlocked</button>
          <button className="ledger-button" disabled={!data.proportional_available} onClick={() => proportional.mutate()} type="button">Proportional to estimates</button>
          <button className="ledger-button ledger-button-primary" onClick={() => manualSave.mutate()} type="button">Save manual allocation</button>
        </div>
        <div className="lot-member-list">
          {data.members.map((member) => (
            <article className={`lot-member lot-member-${member.state} ${member.locked ? "lot-member-locked" : ""}`} key={member.id}>
              <div>
                <Link to={member.detail_url}>{member.sku}</Link>
                <strong>{member.title || member.category}</strong>
                <small>{member.state}{member.locked ? " · cost locked" : ""}</small>
              </div>
              <label className="label">
                <span>Allocated share</span>
                <input className="field" disabled={member.locked} inputMode="decimal" value={manual[member.id] ?? ""} onChange={(event) => setManual({ ...manual, [member.id]: event.target.value })} />
              </label>
              {member.state === "unsold" ? (
                <button className="ledger-button" disabled={scrap.isPending} onClick={() => scrap.mutate(member.id)} type="button">
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                  Mark scrapped
                </button>
              ) : null}
            </article>
          ))}
        </div>
      </section>
    </LotFrame>
  );
}

function LotListRow({ lot }: { lot: LotSummary }) {
  return (
    <Link className={`lot-list-row ${lot.is_over_allocated ? "lot-list-row-warning" : ""}`} to={`/lots/${lot.id}`}>
      <span>
        <strong>{lot.label}</strong>
        <small>{lot.source?.name ?? "No source"} · {lot.purchase_date}</small>
      </span>
      <span>{lot.tally_label}</span>
    </Link>
  );
}

function liveTally(lot: LotSummary, manual: Record<string, string>) {
  const allocated = lot.members.reduce((total, member) => total + decimal(manual[member.id] ?? member.acquisition_cost ?? "0"), 0);
  const total = decimal(lot.total_cost);
  const remainder = round(total - allocated);
  return {
    allocated: round(allocated),
    remainder,
    label: `allocated ${formatCurrency(allocated)} of ${formatCurrency(total)} · remainder ${formatCurrency(remainder)}`
  };
}

function decimal(value: string | number | null | undefined) {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function round(value: number) {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

function Metric({ label, value, tone = "normal" }: { label: string; value: string; tone?: "normal" | "loss" }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className={tone === "loss" ? "lot-loss" : ""}>{value}</dd>
    </div>
  );
}

function LotFrame({ children }: { children: ReactNode }) {
  return <div className="lot-page">{children}</div>;
}

function formatCurrency(value: string | number) {
  return currencyFormatter.format(Number(value || 0));
}

function sourceTypeLabel(value: Source["type"]) {
  return value.replace("_", " ");
}
