import { apiRequest } from "./client";
import type { PaginatedResponse, ResearchLink, ResearchRecord, ResearchRecordPayload, UUID } from "../types";

export interface ResearchRecordQuery {
  item?: UUID;
}

function queryString(query: ResearchRecordQuery = {}) {
  const params = new URLSearchParams();
  if (query.item) {
    params.set("item", query.item);
  }
  const text = params.toString();
  return text ? `?${text}` : "";
}

export function listResearchRecords(query: ResearchRecordQuery = {}) {
  return apiRequest<PaginatedResponse<ResearchRecord>>(`/api/research-records/${queryString(query)}`);
}

export function createResearchRecord(payload: ResearchRecordPayload) {
  return apiRequest<ResearchRecord>("/api/research-records/", {
    method: "POST",
    body: payload
  });
}

export function updateResearchRecord(id: UUID, payload: Partial<ResearchRecordPayload>) {
  return apiRequest<ResearchRecord>(`/api/research-records/${id}/`, {
    method: "PATCH",
    body: payload
  });
}

export function deleteResearchRecord(id: UUID) {
  return apiRequest<void>(`/api/research-records/${id}/`, { method: "DELETE" });
}

export function getResearchLinks(itemId: UUID) {
  return apiRequest<{ item: UUID; links: ResearchLink[] }>(`/api/items/${itemId}/research-links/`);
}

