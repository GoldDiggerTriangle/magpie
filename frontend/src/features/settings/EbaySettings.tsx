import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BrainCircuit,
  CheckCircle2,
  CircleAlert,
  DownloadCloud,
  ExternalLink,
  KeyRound,
  Link2,
  RefreshCw,
  ShieldCheck,
  Unplug,
  XCircle
} from "lucide-react";
import { useEffect, useState } from "react";

import { listAuditLogs } from "../../api/audit";
import {
  completeEbayConnect,
  disconnectEbay,
  getEbayStatus,
  listEbayOrderDuplicates,
  listEbayOrderStaging,
  refreshEbayPolicies,
  resolveEbayOrderDuplicate,
  resolveEbayOrderStaging,
  startEbayConnect,
  syncEbayOrders
} from "../../api/ebay";
import { configureAICredential, disconnectAICredential, getAIStatus } from "../../api/intelligence";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { EmptyState } from "../../components/EmptyState";
import type { AIStatus, AuditLogEntry, EbayOrderDuplicateCandidate, EbayOrderStaging, EbayOrderSyncResult, EbayStatus } from "../../types";

export function EbaySettings() {
  const queryClient = useQueryClient();
  const [consentUrl, setConsentUrl] = useState("");
  const [pastedUrl, setPastedUrl] = useState("");
  const [auditPrefix, setAuditPrefix] = useState("ebay.");
  const [disconnectOpen, setDisconnectOpen] = useState(false);
  const [aiDisconnectOpen, setAiDisconnectOpen] = useState(false);
  const [aiApiKey, setAiApiKey] = useState("");
  const [aiProvider, setAiProvider] = useState("openai");
  const [aiModelId, setAiModelId] = useState("gpt-5.4-mini");
  const [aiMonthlyCap, setAiMonthlyCap] = useState("5.00");
  const [stagingInputs, setStagingInputs] = useState<Record<string, { item: string; title: string; cost: string }>>({});

  const status = useQuery({ queryKey: ["ebay-status"], queryFn: getEbayStatus });
  const aiStatus = useQuery({ queryKey: ["ai-status"], queryFn: getAIStatus });
  const staging = useQuery({ queryKey: ["ebay-order-staging", "pending"], queryFn: () => listEbayOrderStaging("pending") });
  const duplicates = useQuery({ queryKey: ["ebay-order-duplicates", "pending"], queryFn: () => listEbayOrderDuplicates("pending") });
  const audit = useQuery({
    queryKey: ["audit-log", auditPrefix],
    queryFn: () => listAuditLogs({ actionPrefix: auditPrefix })
  });

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ["ebay-status"] });
    queryClient.invalidateQueries({ queryKey: ["ai-status"] });
    queryClient.invalidateQueries({ queryKey: ["ebay-order-staging"] });
    queryClient.invalidateQueries({ queryKey: ["ebay-order-duplicates"] });
    queryClient.invalidateQueries({ queryKey: ["audit-log"] });
  };

  useEffect(() => {
    if (!aiStatus.data) {
      return;
    }
    setAiProvider(aiStatus.data.provider);
    setAiModelId(aiStatus.data.model_id);
    setAiMonthlyCap(aiStatus.data.monthly_budget_cap_usd);
  }, [aiStatus.data]);

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
  const syncMutation = useMutation({
    mutationFn: () => syncEbayOrders(),
    onSuccess: refreshAll
  });
  const resolveStagingMutation = useMutation({
    mutationFn: ({ row, action }: { row: EbayOrderStaging; action: "link" | "quick_create" | "mark_external" }) => {
      const input = stagingInputs[row.id] ?? { item: "", title: "", cost: "" };
      if (action === "link") {
        return resolveEbayOrderStaging(row.id, {
          action,
          item: input.item,
          cost_basis_override: input.cost || null
        });
      }
      if (action === "quick_create") {
        return resolveEbayOrderStaging(row.id, {
          action,
          title: input.title || row.sku || `eBay order ${row.ebay_order_id}`,
          quantity_total: row.quantity,
          acquisition_cost: input.cost || null
        });
      }
      return resolveEbayOrderStaging(row.id, {
        action,
        cost_basis_override: input.cost || null
      });
    },
    onSuccess: refreshAll
  });
  const resolveDuplicateMutation = useMutation({
    mutationFn: ({ row, action }: { row: EbayOrderDuplicateCandidate; action: "link" | "dismiss" }) => resolveEbayOrderDuplicate(row.id, { action }),
    onSuccess: refreshAll
  });
  const disconnectMutation = useMutation({
    mutationFn: disconnectEbay,
    onSuccess: () => {
      setDisconnectOpen(false);
      refreshAll();
    }
  });
  const aiConfigureMutation = useMutation({
    mutationFn: () => configureAICredential({
      provider: aiProvider,
      model_id: aiModelId,
      monthly_budget_cap_usd: aiMonthlyCap,
      api_key: aiApiKey
    }),
    onSuccess: () => {
      setAiApiKey("");
      refreshAll();
    }
  });
  const aiDisconnectMutation = useMutation({
    mutationFn: disconnectAICredential,
    onSuccess: () => {
      setAiApiKey("");
      setAiDisconnectOpen(false);
      refreshAll();
    }
  });

  return (
    <div className="settings-page mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="mt-1 text-sm text-slate-500">eBay and AI provider connections</p>
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
          <AIProviderPanel
            apiKey={aiApiKey}
            configureError={errorText(aiConfigureMutation.error)}
            configured={Boolean(aiStatus.data?.configured)}
            disconnectError={errorText(aiDisconnectMutation.error)}
            disconnectPending={aiDisconnectMutation.isPending}
            modelId={aiModelId}
            monthlyCap={aiMonthlyCap}
            onApiKeyChange={setAiApiKey}
            onDisconnect={() => setAiDisconnectOpen(true)}
            onModelIdChange={setAiModelId}
            onMonthlyCapChange={setAiMonthlyCap}
            onProviderChange={setAiProvider}
            onSave={() => aiConfigureMutation.mutate()}
            pending={aiConfigureMutation.isPending}
            provider={aiProvider}
            status={aiStatus.data}
            statusError={errorText(aiStatus.error)}
          />
          <OrderSyncPanel
            duplicateRows={duplicates.data?.results ?? []}
            duplicatesLoading={duplicates.isLoading}
            duplicatePending={resolveDuplicateMutation.isPending}
            error={errorText(syncMutation.error) || errorText(resolveStagingMutation.error) || errorText(resolveDuplicateMutation.error)}
            onDuplicateResolve={(row, action) => resolveDuplicateMutation.mutate({ row, action })}
            onInputChange={(id, patch) => setStagingInputs((current) => ({ ...current, [id]: { ...(current[id] ?? { item: "", title: "", cost: "" }), ...patch } }))}
            onResolve={(row, action) => resolveStagingMutation.mutate({ row, action })}
            onSync={() => syncMutation.mutate()}
            pending={syncMutation.isPending}
            result={syncMutation.data}
            stagingInputs={stagingInputs}
            stagingLoading={staging.isLoading}
            stagingRows={staging.data?.results ?? []}
            stagingPending={resolveStagingMutation.isPending}
            status={status.data}
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
      <ConfirmDialog
        open={aiDisconnectOpen}
        title="Disconnect AI provider?"
        detail="This deletes the encrypted AI key. Staged suggestions, usage records, and audit history remain."
        confirmLabel="Disconnect"
        onCancel={() => setAiDisconnectOpen(false)}
        onConfirm={() => aiDisconnectMutation.mutate()}
      />
    </div>
  );
}

function AIProviderPanel({
  apiKey,
  configureError,
  configured,
  disconnectError,
  disconnectPending,
  modelId,
  monthlyCap,
  onApiKeyChange,
  onDisconnect,
  onModelIdChange,
  onMonthlyCapChange,
  onProviderChange,
  onSave,
  pending,
  provider,
  status,
  statusError
}: {
  apiKey: string;
  configureError: string;
  configured: boolean;
  disconnectError: string;
  disconnectPending: boolean;
  modelId: string;
  monthlyCap: string;
  onApiKeyChange: (value: string) => void;
  onDisconnect: () => void;
  onModelIdChange: (value: string) => void;
  onMonthlyCapChange: (value: string) => void;
  onProviderChange: (value: string) => void;
  onSave: () => void;
  pending: boolean;
  provider: string;
  status?: AIStatus;
  statusError: string;
}) {
  const canSave = Boolean(apiKey.trim() || configured);
  return (
    <section className="settings-card ai-settings-card">
      <div className="settings-card-header">
        <div className="flex items-center gap-2">
          <BrainCircuit className="h-4 w-4 text-[#9A7B2E]" aria-hidden="true" />
          <div>
            <h2 className="section-title">AI Provider</h2>
            <p className="mt-1 text-xs text-slate-500">Encrypted key, model, and monthly cap</p>
          </div>
        </div>
        <span className={`settings-pill ${status?.enabled ? "settings-pill-good" : "settings-pill-muted"}`}>
          {status?.configured ? "Configured" : "Not configured"}
        </span>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Provider" value={status?.provider || provider} />
        <Metric label="Model" value={status?.model_id || modelId} />
        <Metric label="Used" value={money(status?.monthly_usage_usd ?? "0.00")} />
        <Metric label="Remaining" value={money(status?.budget_remaining_usd ?? monthlyCap)} />
      </div>

      <form
        className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-[0.75fr_1fr_0.75fr_1.35fr_auto]"
        onSubmit={(event) => {
          event.preventDefault();
          onSave();
        }}
      >
        <label className="label">
          <span>Provider</span>
          <select className="field" value={provider} onChange={(event) => onProviderChange(event.target.value)}>
            <option value="openai">OpenAI</option>
          </select>
        </label>
        <label className="label">
          <span>Model</span>
          <input className="field" value={modelId} onChange={(event) => onModelIdChange(event.target.value)} />
        </label>
        <label className="label">
          <span>Monthly cap USD</span>
          <input className="field" inputMode="decimal" value={monthlyCap} onChange={(event) => onMonthlyCapChange(event.target.value)} />
        </label>
        <label className="label">
          <span>{configured ? "Replace key" : "API key"}</span>
          <input
            autoComplete="off"
            className="field"
            placeholder={configured ? "Configured; paste a new key to replace" : "Paste API key"}
            type="password"
            value={apiKey}
            onChange={(event) => onApiKeyChange(event.target.value)}
          />
        </label>
        <button className="btn-primary gap-2" disabled={!canSave || pending} type="submit">
          <KeyRound className="h-4 w-4" aria-hidden="true" />
          Save AI
        </button>
      </form>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-sm text-slate-400">
        <span>{configured ? "Stored key is encrypted and never displayed." : "No key is stored yet."}</span>
        <button className="btn-secondary gap-2" disabled={!configured || disconnectPending} onClick={onDisconnect} type="button">
          <Unplug className="h-4 w-4" aria-hidden="true" />
          Disconnect AI
        </button>
      </div>

      {status?.disabled_reason ? <p className="mt-3 rounded border border-amber-300/30 bg-amber-300/10 px-3 py-2 text-sm text-amber-100">{status.disabled_reason}</p> : null}
      {statusError ? <p className="mt-3 text-sm text-rose-200">{statusError}</p> : null}
      {configureError ? <p className="mt-3 text-sm text-rose-200">{configureError}</p> : null}
      {disconnectError ? <p className="mt-3 text-sm text-rose-200">{disconnectError}</p> : null}
    </section>
  );
}

function OrderSyncPanel({
  duplicatePending,
  duplicateRows,
  duplicatesLoading,
  error,
  onDuplicateResolve,
  onInputChange,
  onResolve,
  onSync,
  pending,
  result,
  stagingInputs,
  stagingLoading,
  stagingPending,
  stagingRows,
  status
}: {
  duplicatePending: boolean;
  duplicateRows: EbayOrderDuplicateCandidate[];
  duplicatesLoading: boolean;
  error: string;
  onDuplicateResolve: (row: EbayOrderDuplicateCandidate, action: "link" | "dismiss") => void;
  onInputChange: (id: string, patch: { item?: string; title?: string; cost?: string }) => void;
  onResolve: (row: EbayOrderStaging, action: "link" | "quick_create" | "mark_external") => void;
  onSync: () => void;
  pending: boolean;
  result?: EbayOrderSyncResult;
  stagingInputs: Record<string, { item: string; title: string; cost: string }>;
  stagingLoading: boolean;
  stagingPending: boolean;
  stagingRows: EbayOrderStaging[];
  status?: EbayStatus;
}) {
  return (
    <section className="rounded border border-slate-800 bg-slate-950/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="section-title">Order Sync</h2>
          <p className="mt-1 text-xs text-slate-500">Manual read-only eBay import</p>
        </div>
        <button className="btn-primary gap-2" disabled={!status?.connected || pending} onClick={onSync} type="button">
          <DownloadCloud className="h-4 w-4" aria-hidden="true" />
          Sync eBay Orders
        </button>
      </div>
      {status?.requires_reconsent ? (
        <div className="mt-3 rounded border border-amber-300/30 bg-amber-300/10 p-3 text-sm text-amber-50">
          Re-consent is required before order sync. Start Connect again and complete the paste-back flow.
        </div>
      ) : null}
      {result ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-4">
          <Metric label="Created" value={result.counts.created} />
          <Metric label="Staged" value={result.counts.staged} />
          <Metric label="Duplicates" value={result.counts.duplicate_flagged} />
          <Metric label="Skipped" value={result.counts.skipped} />
        </div>
      ) : null}
      {error ? <p className="mt-3 text-sm text-rose-200">{error}</p> : null}

      <div className="mt-5">
        <h3 className="text-sm font-semibold text-slate-100">Unmatched Orders</h3>
        {stagingLoading ? <EmptyState title="Loading staging queue" /> : null}
        {!stagingLoading && stagingRows.length === 0 ? <EmptyState title="No pending staged orders" /> : null}
        <div className="mt-3 space-y-3">
          {stagingRows.map((row) => {
            const input = stagingInputs[row.id] ?? { item: "", title: "", cost: "" };
            return (
              <div className="rounded border border-slate-800 bg-slate-900 p-3" key={row.id}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-slate-100">{row.sku || "No SKU"} · {row.quantity} · ${row.line_price}</p>
                    <p className="mt-1 text-xs text-slate-500">{row.sale_date} · {row.ebay_order_id}/{row.ebay_line_item_id}</p>
                    {row.fee_status === "estimated_or_unmapped" ? <p className="mt-1 text-xs text-amber-200">Fees need review</p> : null}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button className="btn-secondary" disabled={!input.item || stagingPending} onClick={() => onResolve(row, "link")} type="button">Link</button>
                    <button className="btn-secondary" disabled={stagingPending} onClick={() => onResolve(row, "quick_create")} type="button">Quick-create</button>
                    <button className="btn-secondary" disabled={stagingPending} onClick={() => onResolve(row, "mark_external")} type="button">Mark external</button>
                  </div>
                </div>
                <div className="mt-3 grid gap-2 sm:grid-cols-3">
                  <label className="label">
                    <span>Item ID</span>
                    <input className="field" onChange={(event) => onInputChange(row.id, { item: event.target.value })} value={input.item} />
                  </label>
                  <label className="label">
                    <span>Quick title</span>
                    <input className="field" onChange={(event) => onInputChange(row.id, { title: event.target.value })} value={input.title} />
                  </label>
                  <label className="label">
                    <span>Cost basis</span>
                    <input className="field" onChange={(event) => onInputChange(row.id, { cost: event.target.value })} value={input.cost} />
                  </label>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="mt-5">
        <h3 className="text-sm font-semibold text-slate-100">Duplicate Candidates</h3>
        {duplicatesLoading ? <EmptyState title="Loading duplicate candidates" /> : null}
        {!duplicatesLoading && duplicateRows.length === 0 ? <EmptyState title="No duplicate candidates" /> : null}
        <div className="mt-3 space-y-3">
          {duplicateRows.map((row) => (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded border border-slate-800 bg-slate-900 p-3" key={row.id}>
              <div>
                <p className="font-medium text-slate-100">{row.item_sku} · {row.quantity} · ${row.line_price}</p>
                <p className="mt-1 text-xs text-slate-500">{row.sale_date} · {row.ebay_order_id}/{row.ebay_line_item_id}</p>
              </div>
              <div className="flex gap-2">
                <button className="btn-secondary gap-2" disabled={duplicatePending} onClick={() => onDuplicateResolve(row, "link")} type="button">
                  <Link2 className="h-4 w-4" aria-hidden="true" />
                  Link
                </button>
                <button className="btn-secondary gap-2" disabled={duplicatePending} onClick={() => onDuplicateResolve(row, "dismiss")} type="button">
                  <XCircle className="h-4 w-4" aria-hidden="true" />
                  Dismiss
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
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
        <div className="mt-4 hidden overflow-x-auto sm:block">
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
      {entries.length ? (
        <div className="mt-4 space-y-2 sm:hidden">
          {entries.map((entry) => (
            <article className="rounded border border-slate-800 bg-slate-900 p-3" key={entry.id}>
              <p className="break-words text-sm font-medium text-slate-100">{entry.action}</p>
              <dl className="mt-2 grid gap-1 text-xs text-slate-400">
                <Row label="Time" value={formatDate(entry.created_at)} />
                <Row label="Actor" value={entry.actor || "-"} />
                <Row label="Target" value={entry.target_type || "-"} />
              </dl>
            </article>
          ))}
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
    <div className="flex min-w-0 items-center justify-between gap-3">
      <dt className="shrink-0 text-slate-500">{label}</dt>
      <dd className="min-w-0 break-words text-right text-slate-100">{value}</dd>
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

function money(value: string) {
  return `$${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
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
