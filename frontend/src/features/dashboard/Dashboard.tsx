import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Calculator, DownloadCloud, PlusCircle, Search, ShoppingBag, SlidersHorizontal, ReceiptText, ArrowRight } from "lucide-react";
import { useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { getAnalyticsSummary, getDashboardPreferences, updateDashboardPreferences } from "../../api/dashboard";
import { AuthRequiredState } from "../../components/AuthRequiredState";
import { ApiError } from "../../api/client";
import { DEFAULT_ROW, KpiPicker, KpiSkeleton, KpiTile, sanitizeSelectedTiles } from "./KpiRegister";
import type { DashboardKpiId } from "../../types";

const quickActions = [
  { label:"Add item", to:"/add", icon:PlusCircle },
  { label:"Find an item", to:"/inventory", icon:Search },
  { label:"eBay hub", to:"/ebay", icon:DownloadCloud },
  { label:"Buy calculator", to:"/buy-calculator", icon:Calculator },
  { label:"Record a sale", to:"/inventory?task=record-sale", icon:ReceiptText },
  { label:"eBay orders", to:"/ebay/orders", icon:ShoppingBag },
];
const anchors: Record<string,string> = { "pnl":"pnl", "profit":"pnl", "realised-p-l-over-time":"pnl", "estimate":"estimate-vs-actual", "estimate-vs-actual":"estimate-vs-actual", "revenue":"revenue", "net-proceeds":"revenue", "by-category":"by-category", "margin-by-category":"by-category", "sell-through":"sell-through", "time-to-sale":"sell-through", "aging":"aging", "aging-inventory":"aging", "listing-opportunities":"listing-opportunities", "what-to-list-next":"listing-opportunities", "charts-trends":"charts-trends" };

export function Dashboard() {
  const location = useLocation();
  const target = anchors[location.hash.slice(1)];
  if (target) {
    const old = new URLSearchParams(location.search), next = new URLSearchParams();
    for (const key of ["range","start","end","channel","unknown","category"]) for (const v of old.getAll(key)) next.append("chart_"+key,v);
    return <Navigate replace to={`/profit${next.size ? "?"+next : ""}#${target}`} />;
  }
  return <Home />;
}
function Home() {
  const queryClient = useQueryClient();
  const summary = useQuery({ queryKey:["analytics-summary",{range:"this_month"}], queryFn:() => getAnalyticsSummary({range:"this_month"}) });
  const preferences = useQuery({ queryKey:["dashboard-preferences"], queryFn:getDashboardPreferences });
  const selected = sanitizeSelectedTiles(preferences.data?.kpi_tiles ?? DEFAULT_ROW, preferences.data?.available_tiles ?? []);
  const [picker, setPicker] = useState(false), [draft, setDraft] = useState<DashboardKpiId[]>(DEFAULT_ROW);
  const save = useMutation({ mutationFn:updateDashboardPreferences, onSuccess:() => { queryClient.invalidateQueries({queryKey:["dashboard-preferences"]}); setPicker(false); } });
  return <div className="dashboard-ledger-page home-page">
    <header className="home-header"><h1 className="page-title">Home</h1><Link className="row-link" to="/profit?chart_range=this_month#listing-opportunities">What to list next<ArrowRight size={18} aria-hidden="true" /></Link></header>
    <section aria-label="Quick statistics" className="kpi-ledger-row">
      <div className="kpi-row-header"><h2 className="section-title">Quick stats</h2><button type="button" className="icon-button" title="Customise statistics" aria-label="Customise statistics" onClick={() => {setDraft(selected);setPicker(v=>!v);}}><SlidersHorizontal size={20} aria-hidden="true" /></button></div>
      {picker ? <KpiPicker availableTiles={preferences.data?.available_tiles ?? []} draftTiles={draft} setDraftTiles={setDraft} onSave={() => save.mutate(draft)} isSaving={save.isPending} error={save.error?.message || ""} /> : null}
      {summary.isLoading || preferences.isLoading ? <KpiSkeleton count={selected.length} /> : summary.error ? <div role="alert"><p>Quick stats are unavailable.</p>{summary.error instanceof ApiError && [401,403].includes(summary.error.status) ? <AuthRequiredState detail="Sign in to load statistics. Quick actions remain available." /> : null}<button className="btn-secondary" type="button" onClick={() => void summary.refetch()}>Retry stats</button></div> :
        <div className="kpi-grid">{selected.map(id => {const tile=summary.data?.tiles[id]; return tile ? <KpiTile key={id} tile={tile} /> : <article key={id} className="ledger-kpi-tile"><span>{id.replace(/_/g," ")}</span><strong>Unavailable</strong></article>;})}</div>}
      {preferences.error ? <p role="status">Saved tile choices are unavailable; showing the default row without saving changes.</p> : null}
    </section>
    <section aria-label="Quick actions" className="home-actions"><h2 className="section-title">Quick actions</h2><div className="home-action-grid">{quickActions.map(({label,to,icon:Icon})=><Link key={to} className="btn-secondary" to={to}><Icon size={20} aria-hidden="true" /><span>{label}</span></Link>)}</div></section>
    {summary.data?.alerts?.length ? <section className="home-alerts" aria-label="Needs attention"><h2 className="section-title">Needs attention</h2><ul>{summary.data.alerts.map(row=><li key={row.id}><Link className="row-link" to={row.href}><strong>{row.count}</strong> {row.label}<ArrowRight size={18} aria-hidden="true" /></Link></li>)}</ul></section> : null}
  </div>;
}
