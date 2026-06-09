import { apiRequest } from "./client";
import type { PhotoAsset, UUID } from "../types";

export function updatePhoto(id: UUID, payload: Partial<Pick<PhotoAsset, "role" | "is_main" | "order_index">>) {
  return apiRequest<PhotoAsset>(`/api/photos/${id}/`, {
    method: "PATCH",
    body: payload
  });
}

export function deletePhoto(id: UUID) {
  return apiRequest<void>(`/api/photos/${id}/`, { method: "DELETE" });
}
