import { apiRequest } from "./client";
import type { PhotoAsset, UUID } from "../types";

export interface PhotoFixupParameters {
  rotate_degrees?: number | string;
  exposure_delta?: number | string;
  contrast_delta?: number | string;
}

export function updatePhoto(id: UUID, payload: Partial<Pick<PhotoAsset, "role" | "is_main" | "order_index">>) {
  return apiRequest<PhotoAsset>(`/api/photos/${id}/`, {
    method: "PATCH",
    body: payload
  });
}

export function deletePhoto(id: UUID) {
  return apiRequest<void>(`/api/photos/${id}/`, { method: "DELETE" });
}

export function generatePhotoFixup(id: UUID, parameters: PhotoFixupParameters = {}) {
  return apiRequest<PhotoAsset>(`/api/photos/${id}/fixup/`, {
    method: "POST",
    body: { parameters }
  });
}

export function approvePhotoFixup(id: UUID, derivativeId?: UUID) {
  return apiRequest<PhotoAsset>(`/api/photos/${id}/fixup/approve/`, {
    method: "POST",
    body: derivativeId ? { derivative_id: derivativeId } : {}
  });
}

export function rejectPhotoFixup(id: UUID, derivativeId?: UUID) {
  return apiRequest<PhotoAsset>(`/api/photos/${id}/fixup/reject/`, {
    method: "POST",
    body: derivativeId ? { derivative_id: derivativeId } : {}
  });
}

export function tweakPhotoFixup(id: UUID, derivativeId: UUID | undefined, parameters: PhotoFixupParameters) {
  return apiRequest<PhotoAsset>(`/api/photos/${id}/fixup/tweak/`, {
    method: "POST",
    body: {
      ...(derivativeId ? { derivative_id: derivativeId } : {}),
      parameters
    }
  });
}

export function revertPhotoFixup(id: UUID) {
  return apiRequest<PhotoAsset>(`/api/photos/${id}/fixup/revert/`, {
    method: "POST",
    body: {}
  });
}
