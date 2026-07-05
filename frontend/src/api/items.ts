import { ApiError, apiRequest } from "./client";
import type { InventoryItemDetail, InventoryItemList, ItemFormPayload, PaginatedResponse, PhotoAsset, UUID } from "../types";

export interface ItemQuery {
  page?: number;
  search?: string;
  status?: string;
  category?: string;
  condition?: string;
  has_photos?: string;
}

function itemQueryString(query: ItemQuery = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  }
  const text = params.toString();
  return text ? `?${text}` : "";
}

export function listItems(query: ItemQuery = {}) {
  return apiRequest<PaginatedResponse<InventoryItemList>>(`/api/items/${itemQueryString(query)}`);
}

export function getItem(id: UUID) {
  return apiRequest<InventoryItemDetail>(`/api/items/${id}/`);
}

export function createItem(payload: ItemFormPayload) {
  return apiRequest<InventoryItemDetail>("/api/items/", {
    method: "POST",
    body: payload
  });
}

export function updateItem(id: UUID, payload: Partial<ItemFormPayload>) {
  return apiRequest<InventoryItemDetail>(`/api/items/${id}/`, {
    method: "PATCH",
    body: payload
  });
}

export function deleteItem(id: UUID) {
  return apiRequest<void>(`/api/items/${id}/`, { method: "DELETE" });
}

export function uploadItemPhoto(id: UUID, file: File, role = "other") {
  const form = new FormData();
  form.set("image", file);
  form.set("role", role);
  return apiRequest<PhotoAsset>(`/api/items/${id}/photos/`, {
    method: "POST",
    multipart: form
  });
}

export function reorderPhotos(id: UUID, order: UUID[]) {
  return apiRequest<PhotoAsset[]>(`/api/items/${id}/photos/reorder/`, {
    method: "POST",
    body: { order }
  });
}

export function fixupItemPhotos(id: UUID) {
  return apiRequest<PhotoAsset[]>(`/api/items/${id}/photos/fixup/`, {
    method: "POST",
    body: {}
  });
}

export async function downloadItemPhotoZip(id: UUID) {
  const response = await fetch(`/api/items/${id}/photos/export.zip/`, {
    credentials: "include"
  });
  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }
  return response.blob();
}
