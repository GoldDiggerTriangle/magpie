import { apiRequest } from "./client";
import type { PaginatedResponse, SaleRecord, SaleRecordPayload, UUID } from "../types";

export function listSales() {
  return apiRequest<PaginatedResponse<SaleRecord>>("/api/sales/");
}

export function listItemSales(itemId: UUID) {
  return apiRequest<PaginatedResponse<SaleRecord>>(`/api/items/${itemId}/sales/`);
}

export function createItemSale(itemId: UUID, payload: SaleRecordPayload) {
  return apiRequest<SaleRecord>(`/api/items/${itemId}/sales/`, {
    method: "POST",
    body: payload
  });
}

export function createSale(payload: SaleRecordPayload) {
  return apiRequest<SaleRecord>("/api/sales/", {
    method: "POST",
    body: payload
  });
}

export function correctSaleRecord(id: UUID, payload: SaleRecordPayload) {
  return apiRequest<SaleRecord>(`/api/sales/${id}/correct/`, {
    method: "POST",
    body: payload
  });
}
