import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, RotateCcw, SlidersHorizontal, Sparkles, XCircle } from "lucide-react";
import { useState } from "react";

import { fixupItemPhotos } from "../api/items";
import {
  approvePhotoFixup,
  generatePhotoFixup,
  rejectPhotoFixup,
  revertPhotoFixup,
  tweakPhotoFixup
} from "../api/photos";
import type { PhotoAsset, PhotoDerivative, UUID } from "../types";
import { EmptyState } from "./EmptyState";

interface PhotoFixupPanelProps {
  itemId: UUID;
  photos: PhotoAsset[];
  onChanged: () => void;
}

interface TweakState {
  rotate_degrees: string;
  exposure_delta: string;
  contrast_delta: string;
}

const defaultTweak: TweakState = {
  rotate_degrees: "0",
  exposure_delta: "0",
  contrast_delta: "0"
};

export function PhotoFixupPanel({ itemId, photos, onChanged }: PhotoFixupPanelProps) {
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [tweaks, setTweaks] = useState<Record<UUID, TweakState>>({});

  const updateTweak = (photoId: UUID, key: keyof TweakState, value: string) => {
    setTweaks((current) => ({
      ...current,
      [photoId]: {
        ...(current[photoId] ?? defaultTweak),
        [key]: value
      }
    }));
  };

  const afterSuccess = (text: string) => {
    setError("");
    setMessage(text);
    onChanged();
  };

  const afterError = (reason: unknown) => {
    setMessage("");
    setError(reason instanceof Error ? reason.message : "Photo fix-up failed.");
  };

  const batch = useMutation({
    mutationFn: () => fixupItemPhotos(itemId),
    onSuccess: (result) => afterSuccess(`Generated ${result.length} local before/after review${result.length === 1 ? "" : "s"}.`),
    onError: afterError
  });
  const generate = useMutation({
    mutationFn: (photo: PhotoAsset) => generatePhotoFixup(photo.id),
    onSuccess: () => afterSuccess("Generated a local before/after review."),
    onError: afterError
  });
  const approve = useMutation({
    mutationFn: ({ photo, derivative }: { photo: PhotoAsset; derivative?: PhotoDerivative }) => approvePhotoFixup(photo.id, derivative?.id),
    onSuccess: () => afterSuccess("Approved fixed version as the display image. Original remains retained."),
    onError: afterError
  });
  const reject = useMutation({
    mutationFn: ({ photo, derivative }: { photo: PhotoAsset; derivative?: PhotoDerivative }) => rejectPhotoFixup(photo.id, derivative?.id),
    onSuccess: () => afterSuccess("Rejected the fix-up. The original display image was left unchanged."),
    onError: afterError
  });
  const tweak = useMutation({
    mutationFn: ({ photo, derivative }: { photo: PhotoAsset; derivative?: PhotoDerivative }) => {
      const state = tweaks[photo.id] ?? defaultTweak;
      return tweakPhotoFixup(photo.id, derivative?.id, {
        rotate_degrees: state.rotate_degrees,
        exposure_delta: state.exposure_delta,
        contrast_delta: state.contrast_delta
      });
    },
    onSuccess: () => afterSuccess("Generated a tweaked local review. Approve it before it becomes the display image."),
    onError: afterError
  });
  const revert = useMutation({
    mutationFn: (photo: PhotoAsset) => revertPhotoFixup(photo.id),
    onSuccess: () => afterSuccess("Reverted the display image to the retained original."),
    onError: afterError
  });

  const pendingCount = photos.filter((photo) => photo.pending_derivative).length;
  const busy = batch.isPending || generate.isPending || approve.isPending || reject.isPending || tweak.isPending || revert.isPending;

  if (photos.length === 0) {
    return (
      <section className="rounded border border-slate-200 bg-white p-4">
        <EmptyState title="Photo fix-up waits for your photos" detail="Upload your own item photos, then Magpie can stage local before/after clean-ups for review." />
      </section>
    );
  }

  return (
    <section className="rounded border border-slate-200 bg-white p-4 photo-fixup-panel">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="section-title">Local photo fix-up</h2>
          <p className="mt-1 max-w-3xl text-sm text-slate-700">
            One tap stages crop, straighten, white-balance, gentle exposure, and local white-background cleanup. Nothing becomes the display image until you approve it.
          </p>
        </div>
        <button className="btn-primary gap-2" disabled={busy} onClick={() => batch.mutate()} type="button">
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          Fix up all photos
        </button>
      </div>

      <div className="mt-3 rounded border border-amber-700 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-950">
        Condition guard: local geometry, lighting, and background only. No retouching, smoothing, scratch removal, shine boosting, or generative fill.
      </div>

      {message ? <p className="mt-3 rounded border border-emerald-700 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-950">{message}</p> : null}
      {error ? <p className="mt-3 rounded border border-rose-700 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-950">{error}</p> : null}

      <div className="mt-4 grid gap-4">
        {photos.map((photo, index) => {
          const derivative = photo.pending_derivative;
          const approved = photo.active_derivative_detail;
          const state = tweaks[photo.id] ?? defaultTweak;
          const beforeUrl = derivative?.source_url ?? photo.original_url ?? photo.processed_url ?? "";
          const afterUrl = derivative?.fixed_url ?? approved?.fixed_url ?? photo.processed_url ?? photo.original_url ?? "";
          return (
            <article className="rounded border border-slate-200 bg-slate-50 p-3" key={photo.id}>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h3 className="text-base font-semibold text-slate-950">Photo {index + 1} · {roleLabel(photo.role)}</h3>
                  <p className="text-sm text-slate-700">
                    Status: {statusLabel(photo.fixup_status)}
                    {derivative ? ` · ${derivative.background_mode.replace(/_/g, " ")}` : ""}
                  </p>
                </div>
                <button className="btn-secondary gap-2" disabled={busy} onClick={() => generate.mutate(photo)} type="button">
                  <Sparkles className="h-4 w-4" aria-hidden="true" />
                  Generate review
                </button>
              </div>

              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <PhotoPreview label="Before" src={beforeUrl} />
                <PhotoPreview label={derivative ? "After · pending approval" : approved ? "Approved fixed version" : "Current display"} src={afterUrl} />
              </div>

              {derivative ? (
                <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
                  <div className="grid gap-3 sm:grid-cols-3">
                    <label className="label">
                      <span>Rotate</span>
                      <input className="field" inputMode="decimal" value={state.rotate_degrees} onChange={(event) => updateTweak(photo.id, "rotate_degrees", event.target.value)} />
                    </label>
                    <label className="label">
                      <span>Exposure</span>
                      <input className="field" inputMode="decimal" value={state.exposure_delta} onChange={(event) => updateTweak(photo.id, "exposure_delta", event.target.value)} />
                    </label>
                    <label className="label">
                      <span>Contrast</span>
                      <input className="field" inputMode="decimal" value={state.contrast_delta} onChange={(event) => updateTweak(photo.id, "contrast_delta", event.target.value)} />
                    </label>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button className="btn-secondary gap-2" disabled={busy} onClick={() => tweak.mutate({ photo, derivative })} type="button">
                      <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
                      Tweak
                    </button>
                    <button className="btn-primary gap-2" disabled={busy} onClick={() => approve.mutate({ photo, derivative })} type="button">
                      <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                      Approve
                    </button>
                    <button className="btn-danger gap-2" disabled={busy} onClick={() => reject.mutate({ photo, derivative })} type="button">
                      <XCircle className="h-4 w-4" aria-hidden="true" />
                      Reject
                    </button>
                  </div>
                </div>
              ) : (
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  {approved ? (
                    <button className="btn-secondary gap-2" disabled={busy} onClick={() => revert.mutate(photo)} type="button">
                      <RotateCcw className="h-4 w-4" aria-hidden="true" />
                      Revert to original
                    </button>
                  ) : null}
                  {!approved ? <p className="text-sm font-medium text-slate-700">Generate a review to compare before/after before committing anything.</p> : null}
                </div>
              )}

              {(derivative ?? approved)?.condition_note ? (
                <p className="mt-3 text-sm text-slate-700">{(derivative ?? approved)?.condition_note}</p>
              ) : null}
            </article>
          );

        })}
      </div>

      <p className="mt-3 text-sm font-medium text-slate-700">
        {pendingCount > 0 ? `${pendingCount} pending review${pendingCount === 1 ? "" : "s"} still need Approve, Tweak, or Reject.` : "No pending fix-ups. Originals remain retained for every photo."}
      </p>
    </section>
  );
}

function PhotoPreview({ label, src }: { label: string; src: string }) {
  return (
    <figure className="overflow-hidden rounded border border-slate-300 bg-white">
      <figcaption className="border-b border-slate-200 px-3 py-2 text-sm font-bold text-slate-950">{label}</figcaption>
      {src ? (
        <img className="aspect-[4/3] w-full bg-white object-contain" src={src} alt={label} />
      ) : (
        <div className="flex aspect-[4/3] items-center justify-center text-sm font-medium text-slate-700">No image</div>
      )}
    </figure>
  );
}

function roleLabel(role: string) {
  return role.replace(/_/g, " ");
}

function statusLabel(status: PhotoAsset["fixup_status"]) {
  if (status === "pending_review") {
    return "pending review";
  }
  return status;
}
