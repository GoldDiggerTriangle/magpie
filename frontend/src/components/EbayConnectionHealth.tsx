import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { ClipboardCopy, RefreshCw } from "lucide-react";
import { ApiError } from "../api/client";
import { checkEbayConnection, getEbayHealth, type EbayDiagnostic } from "../api/ebayHealth";
import { AuthRequiredState } from "./AuthRequiredState";

const key = ["ebay-connection-health"];
const date = (value: string | null) => value ? new Date(value).toLocaleString("en-AU") : "Unknown";
const scope = (value: string) => value.split("/oauth/api_scope/")[1] || "Base application scope";

function useHealth() {
  return useQuery({ queryKey: key, queryFn: getEbayHealth, retry: false, staleTime: 30_000, refetchOnWindowFocus: false });
}

export function EbayDiagnostics({ value, onField }: { value: EbayDiagnostic; onField?: (field: string) => void }) {
  const [copied, setCopied] = useState(false);
  const raw = useRef<HTMLTextAreaElement>(null);
  const copy = async () => {
    try {
      if (navigator.clipboard) { await navigator.clipboard.writeText(JSON.stringify(value, null, 2)); setCopied(true); return; }
    } catch { /* HTTP LAN/iOS may not expose clipboard; keep selectable diagnostics available. */ }
    raw.current?.focus(); raw.current?.select();
    setCopied(Boolean(document.execCommand?.("copy")));
  };
  // The server has already allowlisted this payload; Details is not the privacy boundary.
  return <div className="min-w-0 space-y-2 [overflow-wrap:anywhere]">
    {value.issues.map((issue, index) => <div key={index}>
      <p>{issue.severity === "warning" ? "Warning: " : ""}{issue.message}</p>
      {issue.kind === "validation" && issue.field && onField ? <button className="row-link min-h-11 text-left" type="button" onClick={() => onField(issue.field!)}>Go to {issue.field.replace(/_/g, " ")}</button> : null}
    </div>)}
    <details><summary className="min-h-11 cursor-pointer font-semibold">Sanitised diagnostics</summary>
      <p>{value.operation} · {date(value.time)} · HTTP {value.http_status ?? "not confirmed"}</p>
      {value.issues.map((issue, index) => <p key={index}>{issue.domain} · {issue.category} · eBay ID {issue.error_id ?? "not supplied"}</p>)}
      <textarea aria-label="Sanitised diagnostic text" className="field min-h-32 w-full" ref={raw} readOnly value={JSON.stringify(value, null, 2)} onFocus={(event) => event.currentTarget.select()} />
      <button className="btn-secondary gap-2" type="button" onClick={() => void copy()}><ClipboardCopy size={18} aria-hidden="true" />{copied ? "Copied diagnostics" : "Copy diagnostics"}</button>
    </details>
  </div>;
}

export function EbayConnectionBanner() {
  const health = useHealth();
  const client = useQueryClient();
  useEffect(() => {
    const refresh = () => void client.invalidateQueries({ queryKey: key });
    window.addEventListener("magpie:ebay-health-changed", refresh);
    return () => window.removeEventListener("magpie:ebay-health-changed", refresh);
  }, [client]);
  if (!health.data) return null; // eBay/auth failure must never block owned inventory work.
  const data = health.data;
  const alerts = data.alerts.filter((row) => row.issues.some((i) => ["reconnect", "renewal_temporary", "configuration", "permission", "missing_scope", "outage", "network", "rate_limit"].includes(i.kind)));
  if (data.connected && !data.refresh.expiring_soon && data.refresh.state !== "expired" && !alerts.length && !data.legacy_refresh_failure_unverified) return null;
  return <aside aria-label="eBay connection notice" className="m-4 min-w-0 space-y-2 border-l-4 border-amber-700 bg-amber-50 p-4 [overflow-wrap:anywhere]">
    {!data.connected ? <p>eBay is disconnected. Local inventory work remains available.</p> : null}
    {data.refresh.state === "expired" ? <p>Seller authorisation has expired. Reconnect eBay.</p> : data.refresh.expiring_soon ? <p>Seller authorisation expires soon: {date(data.refresh.expires_at)}. Reconnect before expiry.</p> : null}
    {data.legacy_refresh_failure_unverified ? <p>A previous renewal failure has not been diagnosed. Check connection before deciding whether to reconnect.</p> : null}
    {alerts.map((value) => <EbayDiagnostics key={value.operation} value={value} />)}
    <a className="row-link min-h-11" href="/settings/ebay">{!data.connected || data.refresh.state === "expired" || alerts.some((row) => row.issues.some((i) => i.kind === "reconnect")) ? "Reconnect eBay" : "Check eBay connection in Settings"}</a>
  </aside>;
}

export function EbayConnectionHealth({ compact = false }: { compact?: boolean }) {
  const health = useHealth();
  const client = useQueryClient();
  const [now, setNow] = useState(Date.now);
  const deadline = health.data?.checks.seller.next_check_at;
  useEffect(() => {
    if (!deadline) return;
    const timer = window.setTimeout(() => setNow(Date.now()), Math.min(2_147_483_647, Math.max(0, Date.parse(deadline) - Date.now()) + 20));
    return () => window.clearTimeout(timer);
  }, [deadline]);
  const check = useMutation({ mutationFn: checkEbayConnection, retry: false, onSuccess: (value) => client.setQueryData(key, value.health),
    onError: (error) => {
      if (error instanceof ApiError && error.status === 429 && error.data && typeof error.data === "object" && "health" in error.data) client.setQueryData(key, error.data.health);
    } });
  if (health.isPending) return <p>Loading saved connection health...</p>;
  if (health.error || !health.data) return health.error instanceof ApiError && [401, 403].includes(health.error.status)
    ? <AuthRequiredState detail="Sign in to view saved eBay connection health." />
    : <p role="status">Saved health unavailable. No eBay check was performed.</p>;
  const data = health.data;
  const next = data.checks.seller.next_check_at;
  const throttled = Boolean(next && Date.parse(next) > now);
  return <section className="min-w-0 space-y-4 border-y border-slate-300 py-4 [overflow-wrap:anywhere]" aria-label="eBay connection health">
    <h2 className="section-title">eBay connection health</h2>
    <p>{data.connected ? data.account : "Not connected"} · {data.marketplace} · {data.environment}</p>
    <p>Last checked: {data.checks.seller.completed_at ? date(data.checks.seller.completed_at) : "Not yet checked"}</p>
    {data.checks.seller.started_at && !data.checks.seller.completed_at ? <p>Check started {date(data.checks.seller.started_at)}; completion not confirmed.</p> : null}
    {compact ? <><p>{data.alerts.length ? `${data.alerts.length} operation(s) need attention; unrelated successes do not clear failures.` : "No recorded current failures. Unchecked APIs are not proven healthy."}</p><a className="row-link min-h-11" href="/settings/ebay">Open connection health and checks</a></> : <>
      <div className="flex min-w-0 flex-wrap gap-3"><button className="btn-secondary gap-2" type="button" disabled={check.isPending || throttled} onClick={() => check.mutate()}><RefreshCw size={18} aria-hidden="true" />{check.isPending ? "Checking connection..." : "Check connection"}</button><a className="row-link min-h-11" href="/settings/ebay#ebay-connect">Reconnect eBay</a></div>
      {throttled ? <p>Next check available {date(next)}. Checks are limited to once every five minutes.</p> : null}
      {check.error ? <p role="alert">{check.error instanceof ApiError && check.error.status === 429 ? "Connection check throttled. The saved results are shown below." : "Connection check did not finish. No listing action was requested."}</p> : null}
      <dl className="grid min-w-0 gap-3 sm:grid-cols-2">
        <div><dt className="font-semibold">Seller access expiry</dt><dd>{date(data.access.expires_at)} · {data.access.state.replace(/_/g, " ")}</dd><dd>Expired access is renewed automatically when needed; expiry alone does not require reconnection.</dd></div>
        <div><dt className="font-semibold">Seller refresh expiry</dt><dd>{date(data.refresh.expires_at)} · {data.refresh.state.replace(/_/g, " ")}</dd></div>
        <div><dt className="font-semibold">Application access expiry</dt><dd>{date(data.application_access.expires_at)} · separate from seller authorisation</dd></div>
      </dl>
      <details><summary className="min-h-11 cursor-pointer font-semibold">Requested / required scopes (not proof of grant)</summary><p>Required: {data.scopes.required.map(scope).join(", ")}</p><p>Requested: {data.scopes.requested.map(scope).join(", ") || "Not recorded"}</p><p>Application required: {data.scopes.application_required.map(scope).join(", ")}</p><p>Dated successful operations below are separate evidence for this connection, not a complete granted-scope claim.</p></details>
      {(["Inventory", "Account", "Fulfilment", "Finances", "Media/EPS", "Taxonomy", "OAuth renewal", "Application authorisation"] as const).map((api) => {
        const rows = data.operations.filter((row) => row.api === api);
        return <div className="min-w-0 space-y-2 border-t border-slate-300 pt-3" key={api}><h3 className="font-semibold">{api}{api === "Taxonomy" ? " - application token" : ""}</h3>
          {!rows.length ? <p>Not yet checked{api === "Media/EPS" ? `. ${data.media_probe}` : "."}</p> : rows.map((row) => <div className="min-w-0 space-y-2" key={row.operation}><p>{row.operation} · {row.principal}</p><p>Last success: {row.last_success ? `${date(row.last_success.time)} · HTTP ${row.last_success.http_status}${row.last_success.count !== null ? ` · ${row.last_success.count} records` : ""}` : "None recorded"}</p>
            {row.current_failure ? <EbayDiagnostics value={row.current_failure} /> : <p>No recorded current failure for this operation.</p>}{row.warnings ? <EbayDiagnostics value={row.warnings} /> : null}</div>)}
        </div>;
      })}
      <div className="space-y-2 border-t border-slate-300 pt-3"><h3 className="font-semibold">Saved metadata snapshots</h3>{Object.entries(data.snapshots).map(([name, time]) => <p key={name}>{name.replace(/_/g, " ")}: {time ? `${date(time)} · ${Math.max(0, Math.floor((Date.now() - Date.parse(time)) / 86_400_000))} days old` : "No saved snapshot"}</p>)}</div>
    </>}
  </section>;
}
