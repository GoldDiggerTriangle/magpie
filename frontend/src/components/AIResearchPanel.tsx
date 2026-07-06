import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BrainCircuit, ExternalLink, KeyRound, Search, ShieldCheck, Sparkles, Unplug } from "lucide-react";
import type { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";

import {
  configureAICredential,
  disconnectAICredential,
  getAIReferences,
  getAIStatus,
  runAIIdentify,
  runAIPriceAssist
} from "../api/intelligence";
import type { AIResearchRunResult, UUID } from "../types";
import { formatUsd } from "../utils/currency";
import { EmptyState } from "./EmptyState";

export function AIResearchPanel({
  itemId,
  onReviewSuggestions
}: {
  itemId: UUID;
  onReviewSuggestions?: () => void;
}) {
  const queryClient = useQueryClient();
  const status = useQuery({ queryKey: ["ai-status"], queryFn: getAIStatus });
  const references = useQuery({
    queryKey: ["ai-references", itemId],
    queryFn: () => getAIReferences(itemId)
  });
  const [apiKey, setApiKey] = useState("");
  const [provider, setProvider] = useState("openai");
  const [modelId, setModelId] = useState("gpt-5.4-mini");
  const [monthlyCap, setMonthlyCap] = useState("5.00");

  useEffect(() => {
    if (!status.data) {
      return;
    }
    setProvider(status.data.provider);
    setModelId(status.data.model_id);
    setMonthlyCap(status.data.monthly_budget_cap_usd);
  }, [status.data]);

  function refreshAfterRun() {
    queryClient.invalidateQueries({ queryKey: ["field-suggestions", itemId] });
    queryClient.invalidateQueries({ queryKey: ["ai-references", itemId] });
    queryClient.invalidateQueries({ queryKey: ["ai-status"] });
    queryClient.invalidateQueries({ queryKey: ["pricing-evidence", itemId] });
  }

  const identify = useMutation({
    mutationFn: () => runAIIdentify(itemId),
    onSuccess: refreshAfterRun
  });
  const priceAssist = useMutation({
    mutationFn: () => runAIPriceAssist(itemId),
    onSuccess: refreshAfterRun
  });
  const configure = useMutation({
    mutationFn: () => configureAICredential({
      provider,
      model_id: modelId,
      monthly_budget_cap_usd: monthlyCap,
      api_key: apiKey
    }),
    onSuccess: () => {
      setApiKey("");
      queryClient.invalidateQueries({ queryKey: ["ai-status"] });
    }
  });
  const disconnect = useMutation({
    mutationFn: disconnectAICredential,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ai-status"] })
  });

  const enabled = Boolean(status.data?.enabled);
  const busy = identify.isPending || priceAssist.isPending;
  const runResult = identify.data ?? priceAssist.data;
  const terms = references.data?.search_terms ?? [];
  const links = references.data?.reference_links ?? [];
  const error = errorText(status.error)
    || errorText(references.error)
    || errorText(identify.error)
    || errorText(priceAssist.error)
    || errorText(configure.error)
    || errorText(disconnect.error);
  const disabledReason = status.data?.disabled_reason || "AI deep-dive is not configured.";
  const statusLine = useMemo(() => {
    if (!status.data) {
      return "Checking AI provider status.";
    }
    if (!status.data.configured) {
      return "Connect an AI provider to enable one-item-at-a-time deep-dives.";
    }
    return `${status.data.provider} / ${status.data.model_id} · ${formatUsd(status.data.monthly_usage_usd)} used of ${formatUsd(status.data.monthly_budget_cap_usd)} monthly cap`;
  }, [status.data]);

  function submitConfig(event: FormEvent) {
    event.preventDefault();
    configure.mutate();
  }

  return (
    <section className="ai-research-panel">
      <div className="ai-research-header">
        <div>
          <p className="intelligence-kicker">Cloud AI deep-dive</p>
          <h2>Identify, then sharpen searches</h2>
          <p>
            AI can stage identification suggestions and improve search terms. It never writes item data, creates prices, or stores reference images.
          </p>
        </div>
        <BrainCircuit className="h-5 w-5 text-[#9A7B2E]" aria-hidden="true" />
      </div>

      <div className="ai-status-card">
        <div>
          <strong>{status.data?.enabled ? "Ready" : "Disabled"}</strong>
          <span>{statusLine}</span>
        </div>
        <ShieldCheck className="h-4 w-4" aria-hidden="true" />
      </div>

      {status.isLoading ? <div className="ai-skeleton" /> : null}
      {error ? <div className="intelligence-error">{error}</div> : null}

      <div className="ai-action-grid">
        <button
          className="ledger-button ledger-button-primary"
          disabled={!enabled || busy}
          onClick={() => identify.mutate()}
          type="button"
        >
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          Identify & fill
        </button>
        <button
          className="ledger-button"
          disabled={!enabled || busy}
          onClick={() => priceAssist.mutate()}
          type="button"
        >
          <Search className="h-4 w-4" aria-hidden="true" />
          Price-assist search terms
        </button>
      </div>

      {!enabled ? <div className="intelligence-warning">{disabledReason}</div> : null}
      {runResult ? <RunSummary onReviewSuggestions={onReviewSuggestions} result={runResult} /> : null}

      {!status.data?.configured ? (
        <form className="ai-config-form" onSubmit={submitConfig}>
          <div className="ai-config-title">
            <KeyRound className="h-4 w-4" aria-hidden="true" />
            <h3>Connect provider</h3>
          </div>
          <label className="label">
            <span>Provider</span>
            <select className="field" value={provider} onChange={(event) => setProvider(event.target.value)}>
              <option value="openai">OpenAI</option>
            </select>
          </label>
          <label className="label">
            <span>Model</span>
            <input className="field" value={modelId} onChange={(event) => setModelId(event.target.value)} />
          </label>
          <label className="label">
            <span>Monthly cap USD</span>
            <input className="field" inputMode="decimal" value={monthlyCap} onChange={(event) => setMonthlyCap(event.target.value)} />
          </label>
          <label className="label">
            <span>API key</span>
            <input
              autoComplete="off"
              className="field"
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
            />
          </label>
          <button className="ledger-button ledger-button-primary" disabled={configure.isPending || !apiKey.trim()} type="submit">
            <KeyRound className="h-4 w-4" aria-hidden="true" />
            Save encrypted key
          </button>
        </form>
      ) : (
        <button
          className="ledger-button ai-disconnect"
          disabled={disconnect.isPending}
          onClick={() => disconnect.mutate()}
          type="button"
        >
          <Unplug className="h-4 w-4" aria-hidden="true" />
          Disconnect AI provider
        </button>
      )}

      <div className="ai-reference-grid">
        <div>
          <h3>Sharpened search terms</h3>
          {terms.length ? (
            <ul className="ai-term-list">
              {terms.map((term) => <li key={term.id}>{term.phrase}</li>)}
            </ul>
          ) : (
            <EmptyState title="No AI search terms yet" detail="Run price-assist after identifying the item; the pricing source links will use the newest safe term." />
          )}
        </div>
        <div>
          <h3>Reference lookups</h3>
          {links.length ? (
            <div className="ai-reference-links">
              {links.map((link) => (
                <a href={link.url} key={link.id} rel="noreferrer" target="_blank">
                  <span>
                    <strong>{link.label}</strong>
                    <small>{link.source_basis}</small>
                  </span>
                  <ExternalLink className="h-4 w-4" aria-hidden="true" />
                </a>
              ))}
            </div>
          ) : (
            <EmptyState title="No reference lookups yet" detail="Reference links open in a new tab. Magpie never copies or stores third-party images." />
          )}
        </div>
      </div>
    </section>
  );
}

function RunSummary({
  onReviewSuggestions,
  result
}: {
  onReviewSuggestions?: () => void;
  result: AIResearchRunResult;
}) {
  const suggestionCount = result.suggestions.length;
  return (
    <div className="intelligence-success">
      <span>
        {result.call.phase === "identify" ? "Identify & fill" : "Price-assist"} completed:
        {" "}{suggestionCount} suggestions, {result.search_terms.length} search terms, {result.reference_links.length} reference links staged.
      </span>
      {suggestionCount > 0 ? (
        <button className="intelligence-inline-action" onClick={onReviewSuggestions} type="button">
          Review {suggestionCount} staged suggestions -&gt;
        </button>
      ) : null}
    </div>
  );
}

function errorText(error: unknown) {
  if (!error) {
    return "";
  }
  return error instanceof Error ? error.message : "Request failed.";
}
