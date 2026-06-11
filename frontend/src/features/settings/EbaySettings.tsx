import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  CircleAlert,
  ExternalLink,
  Link2,
  RefreshCw,
  ShieldCheck,
  Unplug
} from "lucide-react";
import { useState } from "react";

import { listAuditLogs } from "../../api/audit";
import {
  completeEbayConnect,
  disconnectEbay,
  getEbayStatus,
  refreshEbayPolicies,
  startEbayConnect
} from "../../api/ebay";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { EmptyState } from "../../components/EmptyState";
import type { AuditLogEntry, EbayStatus } from "../../types";

export function EbaySettings() {
  const queryClient = useQueryClient();
  const [consentUrl, setConsentUrl] = useState("");
  const [pastedUrl, setPastedUrl] = useState("");
  const [auditPrefix, setAuditPrefix] = useState("ebay.");
  const [disconnectOpen, setDisconnectOpen] = useState(false);

  const status = useQuery({ queryKey: ["ebay-status"], queryFn: getEbayStatus });
  const audit = useQuery({
    queryKey: ["audit-log", auditPrefix],
    queryFn: () => listAuditLogs({ actionPrefix: auditPrefix })
  });

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ["ebay-status"] });
    queryClient.invalidateQueries({ queryKey: ["audit-log"] });
  };

  const startMutation = useMutation({
    mutationFn: startEbayConnect,
    onSuccess: (data) => setConsentUrl(data.consent_url)
  });
  const completeMutation = useMutation({
    mutationFn: () => completeEbayConnect({ pasted_url: pastedUrl }),
    onSuccess: () => {
      setPastedUrl("");
      setConsentUrl("");
      refreshAll();
    }
  });
  const policyMutation = useMutation({
    mutationFn: refreshEbayPolicies,
    onSuccess: refreshAll
  });
  const disconnectMutation = useMutation({
    mutationFn: disconnectEbay,
    onSuccess: () => {
      setDisconnectOpen(false);
      refreshAll();
    }
  });

  return (
    <div className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="mt-1 text-sm text-slate-500">eBay channel connection</p>
        </div>
        <EnvironmentBadge status={status.data} />
      </div>

      {status.isLoading ? <div className="mt-5"><EmptyState title="Loading eBay settings" /></div> : null}
      {status.error ? <div className="mt-5"><EmptyState title="Sign in through Django admin" detail="The settings API needs your Django session." /></div> : null}

      <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4">
          <EbayConnectPanel
            completeError={errorText(completeMutation.error)}
            completePending={completeMutation.isPending}
            consentUrl={consentUrl}
            onComplete={() => completeMutation.mutate()}
            onPastedUrlChange={setPastedUrl}
            onStart={() => startMutation.mutate()}
            pastedUrl={pastedUrl}
            startError={errorText(startMutation.error)}
            startPending={startMutation.isPending}
          />
          <PolicyReadinessCard
            onRefresh={() => policyMutation.mutate()}
            pending={policyMutation.isPending}
            status={status.data}
            error={errorText(policyMutation.error)}
          />
          <AuditLogTable
            entries={audit.data?.results ?? []}
            filter={auditPrefix}
            loading={audit.isLoading}
            onFilterChange={setAuditPrefix}
          />
        </div>

        <aside className="space-y-4">
          <EbayStatusCard status={status.data} />
          <section className="rounded border border-slate-800 bg-slate-950/40 p-4">
            <div className="flex items-center gap-2">
              <Unplug className="h-4 w-4 text-rose-200" aria-hidden="true" />
              <h2 className="section-title">Disconnect</h2>
            </div>
            <p className="mt-2 text-sm text-slate-400">Remove the stored credential for this environment.</p>
            <button
              className="btn-danger mt-4 w-full gap-2"
              disabled={!status.data?.connected || disconnectMutation.isPending}
              onClick={() => setDisconnectOpen(true)}
              type="button"
            >
              <Unplug className="h-4 w-4" aria-hidden="true" />
              Disconnect
            </button>
            {errorText(disconnectMutation.error) ? <p className="mt-2 text-sm text-rose-200">{errorText(disconnectMutation.error)}</p> : null}
          </section>
        </aside>
      </div>

      <ConfirmDialog
        open={disconnectOpen}
        title="Disconnect eBay?"
        detail="This deletes the encrypted credential. Audit history remains read-only."
        confirmLabel="Disconnect"
        onCancel={() => setDisconnectOpen(false)}
        onConfirm={() => disconnectMutation.mutate()}
      />
    </div>
  );
}

function EbayConnectPanel({
  completeError,
  completePending,
  consentUrl,
  onComplete,
  onPastedUrlChange,
  onStart,
  pastedUrl,
  startError,
  startPending
}: {
  completeError: string;
  completePending: boolean;
  consentUrl: string;
  onComplete: () => void;
  onPastedUrlChange: (value: string) => void;
  onStart: () => void;
  pastedUrl: string;
  startError: string;
  startPending: boolean;
}) {
  return (
    <section className="rounded border border-slate-800 bg-slate-950/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="section-title">Connect</h2>
          <p className="mt-1 text-xs text-slate-500">Paste-back OAuth capture</p>
        </div>
        <button className="btn-primary gap-2" disabled={startPending} onClick={onStart} type="button">
          <Link2 className="h-4 w-4" aria-hidden="true" />
          Connect
        </button>
      </div>
      {startError ? <p className="mt-3 text-sm text-rose-200">{startError}</p> : null}
      {consentUrl ? (
        <div className="mt-4 rounded border border-cyan-300/30 bg-cyan-300/10 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="break-all text-sm text-cyan-50">{consentUrl}</p>
            <a className="btn-secondary gap-2" href={consentUrl} rel="noreferrer" target="_blank">
              <ExternalLink className="h-4 w-4" aria-hidden="true" />
              Open
            </a>
          </div>
        </div>
      ) : null}
      <label className="label mt-4">
        <span>Redirected URL</span>
        <textarea
          className="field min-h-24"
          onChange={(event) => onPastedUrlChange(event.target.value)}
          placeholder="https://..."
          value={pastedUrl}
        />
      </label>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button className="btn-secondary gap-2" disabled={!pastedUrl || completePending} onClick={onComplete} type="button">
          <ShieldCheck className="h-4 w-4" aria-hidden="true" />
          Complete
        </button>
        {completeError ? <span className="text-sm text-rose-200">{completeError}</span> : null}
      </div>
    </section>
  );
}

function EbayStatusCard({ status }: { status?: EbayStatus }) {
  return (
    <section className="rounded border border-slate-800 bg-slate-950/40 p-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="section-title">Status</h2>
        <EnvironmentBadge status={status} />
      </div>
      <dl className="mt-4 space-y-3 text-sm">
        <Row label="Connected" value={status?.connected ? "Yes" : "No"} />
        <Row label="Account" value={status?.ebay_username || "-"} />
        <Row label="Access expires" value={formatDate(status?.access_token_expires_at)} />
        <Row label="Refresh expires" value={formatDate(status?.refresh_token_expires_at)} />
      </dl>
      {status?.last_refresh_error ? (
        <div className="mt-4 rounded border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100">
          {status.last_refresh_error}
        </div>
      ) : null}
      {status?.scopes.length ? (
        <div className="mt-4 space-y-1">
          <p className="text-xs font-semibold uppercase tracking-normal text-slate-500">Scopes</p>
          {status.scopes.map((scope) => <p className="break-all text-xs text-slate-300" key={scope}>{scope}</p>)}
        </div>
      ) : null}
    </section>
  );
}

function PolicyReadinessCard({ error, onRefresh, pending, status }: { error: string; onRefresh: () => void; pending: boolean; status?: EbayStatus }) {
  const snapshot = status?.snapshot;
  return (
    <section className="rounded border border-slate-800 bg-slate-950/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {snapshot?.opted_in ? <CheckCircle2 className="h-4 w-4 text-emerald-200" aria-hidden="true" /> : <CircleAlert className="h-4 w-4 text-amber-200" aria-hidden="true" />}
          <h2 className="section-title">Policy Readiness</h2>
        </div>
        <button className="btn-secondary gap-2" disabled={!status?.connected || pending} onClick={onRefresh} type="button">
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Refresh
        </button>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-4">
        <Metric label="Opted in" value={snapshot?.opted_in === null || snapshot?.opted_in === undefined ? "-" : snapshot.opted_in ? "Yes" : "No"} />
        <Metric label="Payment" value={snapshot?.policy_counts.payment ?? 0} />
        <Metric label="Fulfillment" value={snapshot?.policy_counts.fulfillment ?? 0} />
        <Metric label="Return" value={snapshot?.policy_counts.return ?? 0} />
      </div>
      <p className="mt-3 text-xs text-slate-500">Fetched {formatDate(snapshot?.fetched_at)}</p>
      {error ? <p className="mt-2 text-sm text-rose-200">{error}</p> : null}
    </section>
  );
}

function AuditLogTable({ entries, filter, loading, onFilterChange }: { entries: AuditLogEntry[]; filter: string; loading: boolean; onFilterChange: (value: string) => void }) {
  return (
    <section className="rounded border border-slate-800 bg-slate-950/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="section-title">Audit Log</h2>
        <label className="label w-full sm:w-64">
          <span>Action prefix</span>
          <input className="field" value={filter} onChange={(event) => onFilterChange(event.target.value)} />
        </label>
      </div>
      {loading ? <EmptyState title="Loading audit log" /> : null}
      {!loading && entries.length === 0 ? <EmptyState title="No audit entries" /> : null}
      {entries.length ? (
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-normal text-slate-500">
              <tr>
                <th className="px-3 py-2">Time</th>
                <th className="px-3 py-2">Action</th>
                <th className="px-3 py-2">Actor</th>
                <th className="px-3 py-2">Target</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {entries.map((entry) => (
                <tr key={entry.id}>
                  <td className="whitespace-nowrap px-3 py-2 text-slate-400">{formatDate(entry.created_at)}</td>
                  <td className="whitespace-nowrap px-3 py-2 font-medium text-slate-100">{entry.action}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-slate-300">{entry.actor}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-slate-400">{entry.target_type || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

function EnvironmentBadge({ status }: { status?: EbayStatus }) {
  const value = status?.environment ? status.environment.toUpperCase() : "NOT CONFIGURED";
  const classes = status?.environment === "production"
    ? "border-rose-300/50 bg-rose-400/10 text-rose-100"
    : status?.environment === "sandbox"
      ? "border-amber-300/50 bg-amber-300/10 text-amber-100"
      : "border-slate-700 bg-slate-900 text-slate-300";
  return <span className={`rounded border px-2 py-1 text-xs font-semibold ${classes}`}>{value}</span>;
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right text-slate-100">{value}</dd>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded border border-slate-800 bg-slate-900 p-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-2 text-xl font-semibold text-slate-50">{value}</p>
    </div>
  );
}

function formatDate(value?: string | null) {
  if (!value) {
    return "-";
  }
  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
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
