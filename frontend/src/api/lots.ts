import { apiRequest } from "./client";
import type { LotSummary, PaginatedResponse, Source, UUID } from "../types";

export interface LotPayload {
  label: string;
  purchase_date: string;
  total_cost: string;
  source?: UUID | null;
  note?: string;
}

export interface SourcePayload {
  name: string;
  type: Source["type"];
}

export function listSources() {
  return apiRequest<PaginatedResponse<Source>>("/api/sources/?ordering=name");
}

export function createSource(payload: SourcePayload) {
  return apiRequest<Source>("/api/sources/", { method: "POST", body: payload });
}

export function listLots() {
  return apiRequest<PaginatedResponse<LotSummary>>("/api/lots/");
}

export function getLot(id: UUID) {
  return apiRequest<LotSummary>(`/api/lots/${id}/`);
}

export function createLot(payload: LotPayload) {
  return apiRequest<LotSummary>("/api/lots/", { method: "POST", body: payload });
}

export function allocateLotEqual(id: UUID) {
  return apiRequest<LotSummary>(`/api/lots/${id}/allocate/equal/`, { method: "POST", body: {} });
}

export function allocateLotProportional(id: UUID) {
  return apiRequest<LotSummary>(`/api/lots/${id}/allocate/proportional/`, { method: "POST", body: {} });
}

export function allocateLotManual(id: UUID, allocations: Array<{ item: UUID; amount: string }>) {
  return apiRequest<LotSummary>(`/api/lots/${id}/allocate/manual/`, {
    method: "POST",
    body: { allocations }
  });
}

export function scrapLotMember(id: UUID, item: UUID, scrapped_at?: string) {
  return apiRequest<LotSummary>(`/api/lots/${id}/scrap/`, {
    method: "POST",
    body: { item, scrapped_at }
  });
}
