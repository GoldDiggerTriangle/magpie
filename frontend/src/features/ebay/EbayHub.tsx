import { useMutation, useQuery } from "@tanstack/react-query";
import { ExternalLink, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import { draftDestination, getEbayHub, type HubDraft } from "../../api/ebayHub";
import { reconcileListing } from "../../api/listingWorkflow";
import { AuthRequiredState } from "../../components/AuthRequiredState";
import { ApiError } from "../../api/client";
import { EbayConnectionHealth } from "../../components/EbayConnectionHealth";

const inflight = (row: HubDraft) => ["publishing", "publish_unknown"].includes(row.status);
const active = (row: HubDraft) => !["published", "archived"].includes(row.status) && !row.listing_id;
const staged = (row: HubDraft) => row.status === "staged" || Boolean(row.offer_id);
const date = (value: string | null) => value ? new Date(value).toLocaleString("en-AU") : "Unavailable";

export function EbayHub() {
  const hub = useQuery({ queryKey: ["ebay-hub"], queryFn: getEbayHub });
  const reconcile = useMutation({ mutationFn: reconcileListing, onSuccess: () => hub.refetch() });
  if (hub.isPending) return <div className="item-page-frame"><p>Loading eBay records...</p></div>;
  if (hub.error || !hub.data) return <div className="item-page-frame">{hub.error instanceof ApiError && [401, 403].includes(hub.error.status)
    ? <AuthRequiredState detail="Sign in to see your saved eBay records." />
    : <div role="alert"><p>eBay records are unavailable. Connection status has not been checked.</p><button className="btn-secondary" type="button" onClick={() => void hub.refetch()}>Retry</button></div>}</div>;
  const data = hub.data;
  const connection = data.connection;
  const needsConnection = !connection.connected || connection.requires_reconsent || connection.has_refresh_error;
  const groups = [
    { name: "Check publish result", rows: data.drafts.filter((row) => active(row) && inflight(row)) },
    { name: "Drafts in progress", rows: data.drafts.filter((row) => active(row) && !inflight(row) && !staged(row)) },
    { name: "Staged offers", rows: data.drafts.filter((row) => active(row) && !inflight(row) && staged(row)) },
  ];
  return <div className="item-page-frame ebay-hub min-w-0 space-y-6">
    <header className="flex min-w-0 flex-wrap items-center justify-between gap-3"><h1 className="page-title">eBay</h1><Link className="btn-secondary" to="/settings/ebay">eBay settings</Link></header>
    <p>{data.provenance}. Loaded {date(data.as_of)}.</p>
    <EbayConnectionHealth compact />
    <section className="space-y-3 border-y border-slate-300 py-4" aria-label="Connection health">
      <h2 className="section-title">Connection health</h2>
      <p>{needsConnection ? "Connection needs attention" : "Connected in saved records - not live-verified"}</p>
      <p>Environment: {connection.environment || "not configured"}</p>
      <p>Access expiry: {date(connection.access_token_expires_at)}{connection.access_token_expires_at && Date.parse(connection.access_token_expires_at) <= Date.now() ? " (expired; renewal not checked here)" : ""}</p>
      <p>Policy snapshot: {date(connection.policies_fetched_at)}{!connection.policies_fetched_at ? " - no saved snapshot" : Date.now() - Date.parse(connection.policies_fetched_at) > 7 * 86_400_000 ? " - stale (older than 7 days); refresh in Settings" : " - saved snapshot"}</p>
      <Link className="row-link" to="/settings/ebay">{!connection.connected ? "Reconnect eBay" : "Manage connection and policies"}</Link>
    </section>
    {reconcile.error ? <p role="alert">{reconcile.error instanceof Error ? reconcile.error.message : "Reconciliation was not confirmed. Do not publish again."}</p> : null}
    {groups.map((group) => <section key={group.name} aria-label={group.name} className="min-w-0 space-y-3">
      <h2 className="section-title">{group.name}</h2>
      {!group.rows.length ? <p>{group.name === "Check publish result" ? "No publish results need checking." : `No ${group.name.toLowerCase()}.`}</p> : <ul className="min-w-0 divide-y divide-slate-300">{group.rows.map((row) => <li key={row.id} className="min-w-0 space-y-2 py-3">
        <Link className="row-link listing-title" to={draftDestination(row)}>{row.sku} - {row.title || "Untitled draft"}</Link>
        <p>{row.status.replace(/_/g, " ")}{row.has_publish_error ? " - last attempt failed; open draft for details" : ""}</p>
        {row.offer_id ? <p>Unpublished offer {row.offer_id}</p> : null}
        {inflight(row) ? <><p>Started: {date(row.publish_started_at)}. Do not retry publishing until the outcome is known.</p><button className="btn-secondary gap-2" type="button" disabled={reconcile.isPending} onClick={() => reconcile.mutate(row.id)}><RefreshCw size={18} aria-hidden="true" />Reconcile {row.sku}</button></> : null}
      </li>)}</ul>}
    </section>)}
    <section className="min-w-0 space-y-3" aria-label="Live listings"><h2 className="section-title">Live listings</h2>
      <p>Active local listing records; current marketplace state is not fetched here.</p>
      {!data.listings.length ? <p>No active eBay listing records.</p> : <ul className="min-w-0 divide-y divide-slate-300">{data.listings.map((row) => <li key={row.id} className="min-w-0 space-y-2 py-3">
        <Link className="row-link listing-title" to={row.draft_id ? draftDestination({ item_id: row.item_id, id: row.draft_id }) : `/inventory/${row.item_id}#listings-channels`}>{row.sku} - {row.title}</Link>
        <p>Listed {date(row.listed_at)}</p>
        {row.listing_id ? <a className="row-link gap-2" href={`https://www.ebay.com.au/itm/${encodeURIComponent(row.listing_id)}`} target="_blank" rel="noreferrer"><ExternalLink size={18} aria-hidden="true" />View on eBay</a> : <p>Manual tracking record; listing ID not recorded.</p>}
      </li>)}</ul>}
      <Link className="row-link" to="/listings">Open channel listings board</Link>
    </section>
    <section className="space-y-3 border-t border-slate-300 py-4" aria-label="Orders"><h2 className="section-title">Orders</h2><p>{data.orders.pending} unmatched orders; {data.orders.duplicates} duplicate candidates.</p><p>Last sync: {date(data.orders.last_synced_at)}. No sync runs when this page opens.</p><Link className="btn-secondary" to="/ebay/orders">Open eBay orders</Link></section>
    <details className="border-t border-slate-300 py-4"><summary className="min-h-11 cursor-pointer font-semibold">Published and archived draft history</summary><ul className="min-w-0 divide-y divide-slate-300">{data.drafts.filter((row) => !active(row)).map((row) => <li className="min-w-0 py-3" key={row.id}><Link className="row-link listing-title" to={draftDestination(row)}>{row.sku} - {row.title || "Untitled draft"} ({row.status})</Link></li>)}</ul></details>
  </div>;
}
