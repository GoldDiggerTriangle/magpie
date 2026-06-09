import { ArrowDown, ArrowUp, Star, Trash2 } from "lucide-react";

import type { PhotoAsset } from "../types";
import { EmptyState } from "./EmptyState";

interface PhotoGalleryProps {
  photos: PhotoAsset[];
  onSetMain?: (photo: PhotoAsset) => void;
  onMove?: (photo: PhotoAsset, direction: -1 | 1) => void;
  onDelete?: (photo: PhotoAsset) => void;
}

export function PhotoGallery({ photos, onSetMain, onMove, onDelete }: PhotoGalleryProps) {
  if (photos.length === 0) {
    return <EmptyState title="No photos yet" />;
  }

  const main = photos.find((photo) => photo.is_main) ?? photos[0];

  return (
    <div className="space-y-3">
      <div className="overflow-hidden rounded border border-slate-800 bg-slate-900">
        <img
          className="max-h-[60vh] w-full object-contain"
          src={main.processed_url ?? main.original_url ?? ""}
          alt="Main item"
        />
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
        {photos.map((photo, index) => (
          <div key={photo.id} className="overflow-hidden rounded border border-slate-800 bg-slate-900">
            <img
              className="aspect-[4/3] w-full object-cover"
              src={photo.thumb_url ?? photo.processed_url ?? ""}
              alt={`${photo.role} photo`}
            />
            <div className="flex items-center justify-between gap-1 p-2">
              <button
                className={photo.is_main ? "icon-button-active" : "icon-button"}
                title="Set main"
                type="button"
                onClick={() => onSetMain?.(photo)}
              >
                <Star className="h-4 w-4" aria-hidden="true" />
              </button>
              <button
                className="icon-button"
                disabled={index === 0}
                title="Move earlier"
                type="button"
                onClick={() => onMove?.(photo, -1)}
              >
                <ArrowUp className="h-4 w-4" aria-hidden="true" />
              </button>
              <button
                className="icon-button"
                disabled={index === photos.length - 1}
                title="Move later"
                type="button"
                onClick={() => onMove?.(photo, 1)}
              >
                <ArrowDown className="h-4 w-4" aria-hidden="true" />
              </button>
              <button
                className="icon-button-danger"
                title="Delete photo"
                type="button"
                onClick={() => onDelete?.(photo)}
              >
                <Trash2 className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
