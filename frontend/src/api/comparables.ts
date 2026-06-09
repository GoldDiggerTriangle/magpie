import { apiRequest } from "./client";
import type { Comparable, ComparablePayload, PaginatedResponse, UUID } from "../types";

export interface ComparableQuery {
  item?: UUID;
  kind?: string;
  ordering?: string;
}

function queryString(query: ComparableQuery = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value) {
      params.set(key, value);
    }
  }
  const text = params.toString();
  return text ? `?${text}` : "";
}

export function listComparables(query: ComparableQuery = {}) {
  return apiRequest<PaginatedResponse<Comparable>>(`/api/comparables/${queryString(query)}`);
}

export function createComparable(payload: ComparablePayload) {
  return apiRequest<Comparable>("/api/comparables/", {
    method: "POST",
    body: payload
  });
}

export function updateComparable(id: UUID, payload: Partial<ComparablePayload>) {
  return apiRequest<Comparable>(`/api/comparables/${id}/`, {
    method: "PATCH",
    body: payload
  });
}

export function deleteComparable(id: UUID) {
  return apiRequest<void>(`/api/comparables/${id}/`, { method: "DELETE" });
}

