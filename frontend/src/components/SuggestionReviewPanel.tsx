import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Eye, FileText, Pencil, ScanText, ShieldCheck, X } from "lucide-react";
import { useMemo, useState } from "react";

import {
  approveFieldSuggestion,
  editFieldSuggestion,
  listFieldSuggestions,
  rejectFieldSuggestion,
  runItemOcr,
  scanItemDuplicates
} from "../api/intelligence";
import type { FieldSuggestion, UUID } from "../types";
import { EmptyState } from "./EmptyState";

export function SuggestionReviewPanel({ itemId }: { itemId: UUID }) {
  const queryClient = useQueryClient();
  const [editValues, setEditValues] = useState<Record<string, string>>({});
  const suggestions = useQuery({
    queryKey: ["field-suggestions", itemId, "pending"],
    queryFn: () => listFieldSuggestions(itemId, "pending")
  });

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["field-suggestions", itemId] });
    queryClient.invalidateQueries({ queryKey: ["item", itemId] });
  }

  const ocrMutation = useMutation({
    mutationFn: () => runItemOcr(itemId),
    onSuccess: refresh
  });
  const duplicateMutation = useMutation({
    mutationFn: () => scanItemDuplicates(itemId),
    onSuccess: refresh
  });
  const approveMutation = useMutation({
    mutationFn: (suggestion: FieldSuggestion) => approveFieldSuggestion(suggestion.id),
    onSuccess: refresh
  });
  const editMutation = useMutation({
    mutationFn: (suggestion: FieldSuggestion) => editFieldSuggestion(
      suggestion.id,
      editValues[suggestion.id] || stringifyValue(suggestion.proposed_value)
    ),
    onSuccess: refresh
  });
  const rejectMutation = useMutation({
    mutationFn: (suggestion: FieldSuggestion) => rejectFieldSuggestion(suggestion.id),
    onSuccess: refresh
  });

  const rows = suggestions.data?.results ?? [];
  const mainRows = useMemo(
    () => rows.filter((row) => row.confidence_band === "high" || row.confidence_band === "medium"),
    [rows]
  );
  const leadRows = useMemo(
    () => rows.filter((row) => row.confidence_band === "low" || row.confidence_band === "candidate"),
    [rows]
  );
  const busy = approveMutation.isPending || editMutation.isPending || rejectMutation.isPending;
  const error = errorText(suggestions.error) || errorText(ocrMutation.error) || errorText(duplicateMutation.error) || errorText(approveMutation.error) || errorText(editMutation.error) || errorText(rejectMutation.error);
  const ocrUnavailable = ocrMutation.data && !ocrMutation.data.available ? ocrMutation.data.detail : "";

  return (
    <section className="intelligence-panel">
      <div className="intelligence-panel-header">
        <div>
          <p className="intelligence-kicker">Human review</p>
          <h2>Suggested fields</h2>
          <p>OCR and duplicate checks stage leads here. Item data only changes when you approve or edit a field.</p>
        </div>
        <ShieldCheck className="h-5 w-5 text-[#2E7D5B]" aria-hidden="true" />
      </div>

      <div className="intelligence-actions">
        <button
          className="ledger-button"
          disabled={ocrMutation.isPending}
          onClick={() => ocrMutation.mutate()}
          type="button"
        >
          <ScanText className="h-4 w-4" aria-hidden="true" />
          Run OCR
        </button>
        <button
          className="ledger-button"
          disabled={duplicateMutation.isPending}
          onClick={() => duplicateMutation.mutate()}
          type="button"
        >
          <Eye className="h-4 w-4" aria-hidden="true" />
          Scan duplicates
        </button>
      </div>

      {ocrMutation.data?.available ? (
        <div className="intelligence-success">{ocrMutation.data.detail} {ocrMutation.data.suggestions.length} staged.</div>
      ) : null}
      {ocrUnavailable ? <div className="intelligence-warning">{ocrUnavailable}</div> : null}
      {duplicateMutation.data ? (
        <div className="intelligence-success">{duplicateMutation.data.suggestions.length} duplicate candidate leads staged.</div>
      ) : null}
      {error ? <div className="intelligence-error">{error}</div> : null}

      {suggestions.isLoading ? <div className="intelligence-skeleton" /> : null}
      {!suggestions.isLoading && !suggestions.error && rows.length === 0 ? (
        <EmptyState title="No pending suggestions" detail="Run OCR or scan duplicates to stage local review leads." />
      ) : null}

      {mainRows.length ? (
        <SuggestionSection
          busy={busy}
          editValues={editValues}
          onApprove={(row) => approveMutation.mutate(row)}
          onEdit={(row) => editMutation.mutate(row)}
          onReject={(row) => rejectMutation.mutate(row)}
          onValueChange={(id, value) => setEditValues((current) => ({ ...current, [id]: value }))}
          rows={mainRows}
          title="Reviewable field suggestions"
        />
      ) : null}

      {leadRows.length ? (
        <SuggestionSection
          busy={busy}
          editValues={editValues}
          lead
          onApprove={(row) => approveMutation.mutate(row)}
          onEdit={(row) => editMutation.mutate(row)}
          onReject={(row) => rejectMutation.mutate(row)}
          onValueChange={(id, value) => setEditValues((current) => ({ ...current, [id]: value }))}
          rows={leadRows}
          title="Low-confidence leads"
        />
      ) : null}
    </section>
  );
}

function SuggestionSection({
  busy,
  editValues,
  lead = false,
  onApprove,
  onEdit,
  onReject,
  onValueChange,
  rows,
  title
}: {
  busy: boolean;
  editValues: Record<string, string>;
  lead?: boolean;
  onApprove: (row: FieldSuggestion) => void;
  onEdit: (row: FieldSuggestion) => void;
  onReject: (row: FieldSuggestion) => void;
  onValueChange: (id: string, value: string) => void;
  rows: FieldSuggestion[];
  title: string;
}) {
  return (
    <div className="suggestion-section">
      <div className="suggestion-section-title">
        <FileText className="h-4 w-4" aria-hidden="true" />
        <h3>{title}</h3>
      </div>
      <div className="suggestion-list">
        {rows.map((row) => (
          <article className={lead ? "suggestion-row suggestion-row-lead" : "suggestion-row"} key={row.id}>
            <div className="suggestion-row-main">
              {row.photo_thumb_url ? <img src={row.photo_thumb_url} alt="" /> : null}
              <div>
                <div className="suggestion-meta">
                  <span>{labelForField(row.field)}</span>
                  <span>{sourceLabel(row.source)}</span>
                  <span>{bandLabel(row.confidence_band)}</span>
                </div>
                <strong>{stringifyValue(row.proposed_value)}</strong>
                <p>{row.evidence}</p>
              </div>
            </div>
            {row.field !== "duplicate_candidate" ? (
              <label className="suggestion-edit">
                <span>Edit value</span>
                <input
                  className="field"
                  onChange={(event) => onValueChange(row.id, event.target.value)}
                  value={editValues[row.id] ?? stringifyValue(row.proposed_value)}
                />
              </label>
            ) : null}
            <div className="suggestion-actions">
              <button className="ledger-button ledger-button-primary" disabled={busy} onClick={() => onApprove(row)} type="button">
                <Check className="h-4 w-4" aria-hidden="true" />
                {row.field === "duplicate_candidate" ? "Mark reviewed" : "Approve"}
              </button>
              {row.field !== "duplicate_candidate" ? (
                <button className="ledger-button" disabled={busy} onClick={() => onEdit(row)} type="button">
                  <Pencil className="h-4 w-4" aria-hidden="true" />
                  Edit
                </button>
              ) : null}
              <button className="ledger-button" disabled={busy} onClick={() => onReject(row)} type="button">
                <X className="h-4 w-4" aria-hidden="true" />
                Reject
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function stringifyValue(value: unknown) {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function labelForField(field: string) {
  if (field === "duplicate_candidate") {
    return "Possible duplicate";
  }
  return field.replace(/^attributes\./, "").replace(/_/g, " ");
}

function sourceLabel(source: FieldSuggestion["source"]) {
  if (source === "ocr") {
    return "OCR";
  }
  if (source === "duplicate") {
    return "Duplicate image";
  }
  return "Later AI";
}

function bandLabel(band: FieldSuggestion["confidence_band"]) {
  return band.charAt(0).toUpperCase() + band.slice(1);
}

function errorText(error: unknown) {
  if (!error) {
    return "";
  }
  return error instanceof Error ? error.message : "Request failed.";
}
