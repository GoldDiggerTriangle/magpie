import { ArrowDown, ArrowUp, Star, Trash2, X, ArrowUpDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { PhotoAsset } from "../types";
import { EmptyState } from "./EmptyState";

interface PhotoGalleryProps {
  photos: PhotoAsset[];
  onSetMain?: (photo: PhotoAsset) => void;
  onMove?: (photo: PhotoAsset, direction: -1 | 1) => void;
  onDelete?: (photo: PhotoAsset) => void;
}

export function PhotoGallery({ photos, onSetMain, onMove, onDelete }: PhotoGalleryProps) {
  const [arranging, setArranging] = useState(false);
  const [viewed, setViewed] = useState<PhotoAsset | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (viewed && dialog.current && !dialog.current.open) dialog.current.showModal();
    else if (!viewed && dialog.current?.open) dialog.current.close();
  }, [viewed]);
  if (!photos.length) return <EmptyState title="No photos yet" />;
  return <div className="space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-3"><p>{photos.length} photos</p>
      <button className="btn-secondary gap-2" type="button" aria-pressed={arranging} onClick={() => setArranging(!arranging)}><ArrowUpDown size={18} aria-hidden="true" />{arranging ? "Done arranging" : "Arrange"}</button>
    </div>
    <div className={`photo-grid${arranging ? " arranging" : ""}`}>
      {photos.map((photo, index) => <div key={photo.id} className="photo-tile">
        <button className="photo-open" type="button" aria-label={`View photo ${index + 1} full size`} onClick={() => setViewed(photo)}>
          <img src={photo.thumb_url ?? photo.processed_url ?? photo.original_url ?? ""} alt={`Photo ${index + 1}: ${photo.role.replace(/_/g, " ")}`} />
          {photo.is_main ? <span className="photo-main">Main</span> : null}
        </button>
        {arranging ? <div className="photo-actions">
          <button className={photo.is_main ? "icon-button-active" : "icon-button"} title="Set main" aria-label={`Set photo ${index + 1} as main`} type="button" onClick={() => onSetMain?.(photo)}><Star size={18} aria-hidden="true" /></button>
          <button className="icon-button" title="Move earlier" aria-label={`Move photo ${index + 1} earlier`} disabled={index === 0} type="button" onClick={() => onMove?.(photo, -1)}><ArrowUp size={18} aria-hidden="true" /></button>
          <button className="icon-button" title="Move later" aria-label={`Move photo ${index + 1} later`} disabled={index === photos.length - 1} type="button" onClick={() => onMove?.(photo, 1)}><ArrowDown size={18} aria-hidden="true" /></button>
          <button className="icon-button-danger" title="Delete photo" aria-label={`Delete photo ${index + 1}`} type="button" onClick={() => onDelete?.(photo)}><Trash2 size={18} aria-hidden="true" /></button>
        </div> : null}
      </div>)}
    </div>
    <dialog ref={dialog} className="photo-viewer" aria-label="Full size photo" onClose={() => setViewed(null)} onCancel={() => setViewed(null)}>
      <button className="icon-button" aria-label="Close full size photo" title="Close photo" onClick={() => setViewed(null)} type="button"><X size={22} aria-hidden="true" /></button>
      {viewed ? <img src={viewed.processed_url ?? viewed.original_url ?? viewed.thumb_url ?? ""} alt="Full size own photo" /> : null}
    </dialog>
  </div>;
}
