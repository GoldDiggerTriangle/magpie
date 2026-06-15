import { apiRequest } from "./client";
import type {
  AICredentialPayload,
  AIReferencesResult,
  AIResearchRunResult,
  AIStatus,
  FieldSuggestion,
  OcrRunResult,
  PaginatedResponse,
  SoldSearchLink,
  UUID
} from "../types";

export function getSoldSearchLinks(itemId: UUID) {
  return apiRequest<{ links: SoldSearchLink[] }>(`/api/items/${itemId}/sold-searches/`);
}

export function listFieldSuggestions(itemId: UUID, status = "pending") {
  const params = new URLSearchParams({ item: itemId, status });
  return apiRequest<PaginatedResponse<FieldSuggestion>>(`/api/field-suggestions/?${params.toString()}`);
}

export function runItemOcr(itemId: UUID) {
  return apiRequest<OcrRunResult>(`/api/items/${itemId}/ocr/`, { method: "POST" });
}

export function scanItemDuplicates(itemId: UUID) {
  return apiRequest<{ suggestions: FieldSuggestion[] }>(`/api/items/${itemId}/duplicate-scan/`, { method: "POST" });
}

export function approveFieldSuggestion(id: UUID) {
  return apiRequest<FieldSuggestion>(`/api/field-suggestions/${id}/approve/`, { method: "POST" });
}

export function editFieldSuggestion(id: UUID, value: unknown) {
  return apiRequest<FieldSuggestion>(`/api/field-suggestions/${id}/edit/`, {
    method: "POST",
    body: { value }
  });
}

export function rejectFieldSuggestion(id: UUID) {
  return apiRequest<FieldSuggestion>(`/api/field-suggestions/${id}/reject/`, { method: "POST" });
}

export function getAIStatus() {
  return apiRequest<AIStatus>("/api/ai/status/");
}

export function configureAICredential(payload: AICredentialPayload) {
  return apiRequest<AIStatus>("/api/ai/credential/", { method: "POST", body: payload });
}

export function disconnectAICredential() {
  return apiRequest<AIStatus>("/api/ai/credential/", { method: "DELETE" });
}

export function runAIIdentify(itemId: UUID) {
  return apiRequest<AIResearchRunResult>(`/api/items/${itemId}/ai/identify/`, { method: "POST" });
}

export function runAIPriceAssist(itemId: UUID) {
  return apiRequest<AIResearchRunResult>(`/api/items/${itemId}/ai/price-assist/`, { method: "POST" });
}

export function getAIReferences(itemId: UUID) {
  return apiRequest<AIReferencesResult>(`/api/items/${itemId}/ai/references/`);
}
