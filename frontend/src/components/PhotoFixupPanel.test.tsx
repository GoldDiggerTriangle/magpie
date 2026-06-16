import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { beforeEach, expect, test, vi } from "vitest";

import { PhotoFixupPanel } from "./PhotoFixupPanel";
import type { PhotoAsset, PhotoDerivative } from "../types";

const mocks = vi.hoisted(() => ({
  approvePhotoFixup: vi.fn(),
  fixupItemPhotos: vi.fn(),
  generatePhotoFixup: vi.fn(),
  rejectPhotoFixup: vi.fn(),
  revertPhotoFixup: vi.fn(),
  tweakPhotoFixup: vi.fn()
}));

vi.mock("../api/items", () => ({
  fixupItemPhotos: (...args: unknown[]) => mocks.fixupItemPhotos(...args)
}));

vi.mock("../api/photos", () => ({
  approvePhotoFixup: (...args: unknown[]) => mocks.approvePhotoFixup(...args),
  generatePhotoFixup: (...args: unknown[]) => mocks.generatePhotoFixup(...args),
  rejectPhotoFixup: (...args: unknown[]) => mocks.rejectPhotoFixup(...args),
  revertPhotoFixup: (...args: unknown[]) => mocks.revertPhotoFixup(...args),
  tweakPhotoFixup: (...args: unknown[]) => mocks.tweakPhotoFixup(...args)
}));

const pendingDerivative: PhotoDerivative = {
  id: "derivative-1",
  photo: "photo-1",
  status: "pending_review",
  source: "local_fixup",
  fixed_path: "fixups/item/derivative-1.jpg",
  thumb_path: "fixup-thumbs/item/derivative-1.jpg",
  source_path: "originals/item/photo.jpg",
  fixed_url: "/media/fixups/item/derivative-1.jpg",
  thumb_url: "/media/fixup-thumbs/item/derivative-1.jpg",
  source_url: "/media/originals/item/photo.jpg",
  width: 1200,
  height: 900,
  bytes_fixed: 1234,
  pipeline_version: "sprint17-local-v1",
  operations: [
    { name: "conservative_autocrop" },
    { name: "local_background_cleanup" }
  ],
  parameters: {},
  background_mode: "local_threshold_fallback",
  condition_note: "Local fix-up only: framing, orientation, lighting, and background cleanup. No condition-altering retouch.",
  created_at: "2026-06-16T00:00:00Z",
  updated_at: "2026-06-16T00:00:00Z"
};

const basePhoto: PhotoAsset = {
  id: "photo-1",
  item: "item-1",
  role: "front",
  is_main: true,
  order_index: 0,
  original_path: "originals/item/photo.jpg",
  processed_path: "processed/item/photo.jpg",
  thumb_path: "thumbs/item/photo.jpg",
  original_url: "/media/originals/item/photo.jpg",
  processed_url: "/media/processed/item/photo.jpg",
  thumb_url: "/media/thumbs/item/photo.jpg",
  width: 1200,
  height: 900,
  bytes_original: 1234,
  exif_stripped: true,
  quality_score: null,
  fixup_status: "none",
  active_derivative: null,
  active_derivative_detail: null,
  pending_derivative: null,
  derivatives: []
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.fixupItemPhotos.mockResolvedValue([{ ...basePhoto, pending_derivative: pendingDerivative, fixup_status: "pending_review" }]);
  mocks.generatePhotoFixup.mockResolvedValue({ ...basePhoto, pending_derivative: pendingDerivative, fixup_status: "pending_review" });
  mocks.approvePhotoFixup.mockResolvedValue({ ...basePhoto, active_derivative: pendingDerivative.id, active_derivative_detail: pendingDerivative, fixup_status: "approved" });
  mocks.rejectPhotoFixup.mockResolvedValue({ ...basePhoto, fixup_status: "rejected" });
  mocks.tweakPhotoFixup.mockResolvedValue({ ...basePhoto, pending_derivative: { ...pendingDerivative, source: "local_tweak" }, fixup_status: "pending_review" });
  mocks.revertPhotoFixup.mockResolvedValue(basePhoto);
});

test("PhotoFixupPanel generates local batch reviews without applying them", async () => {
  const user = userEvent.setup();
  const onChanged = vi.fn();
  renderWithClient(<PhotoFixupPanel itemId="item-1" photos={[basePhoto]} onChanged={onChanged} />);

  expect(screen.getByText(/Nothing becomes the display image until you approve it/i)).toBeInTheDocument();
  expect(mocks.approvePhotoFixup).not.toHaveBeenCalled();
  expect(mocks.rejectPhotoFixup).not.toHaveBeenCalled();
  expect(mocks.tweakPhotoFixup).not.toHaveBeenCalled();

  await user.click(screen.getByRole("button", { name: /Fix up all photos/i }));

  await waitFor(() => expect(mocks.fixupItemPhotos).toHaveBeenCalledWith("item-1"));
  expect(await screen.findByText(/Generated 1 local before\/after review/i)).toBeInTheDocument();
  expect(onChanged).toHaveBeenCalled();
});

test("PhotoFixupPanel exposes approve tweak reject and keeps the original explicit", async () => {
  const user = userEvent.setup();
  const onChanged = vi.fn();
  renderWithClient(<PhotoFixupPanel itemId="item-1" photos={[{ ...basePhoto, pending_derivative: pendingDerivative, fixup_status: "pending_review" }]} onChanged={onChanged} />);

  expect(screen.getByText("Before")).toBeInTheDocument();
  expect(screen.getByText("After · pending approval")).toBeInTheDocument();

  await user.clear(screen.getByLabelText("Rotate"));
  await user.type(screen.getByLabelText("Rotate"), "2");
  await user.click(screen.getByRole("button", { name: "Tweak" }));
  await waitFor(() => expect(mocks.tweakPhotoFixup).toHaveBeenCalledWith("photo-1", "derivative-1", expect.objectContaining({ rotate_degrees: "2" })));

  await user.click(screen.getByRole("button", { name: "Approve" }));
  await waitFor(() => expect(mocks.approvePhotoFixup).toHaveBeenCalledWith("photo-1", "derivative-1"));

  await user.click(screen.getByRole("button", { name: "Reject" }));
  await waitFor(() => expect(mocks.rejectPhotoFixup).toHaveBeenCalledWith("photo-1", "derivative-1"));
  expect(screen.getByText(/No retouching, smoothing, scratch removal/i)).toBeInTheDocument();
});

test("PhotoFixupPanel lets approved versions revert to the retained original", async () => {
  const user = userEvent.setup();
  renderWithClient(<PhotoFixupPanel itemId="item-1" photos={[{ ...basePhoto, active_derivative: pendingDerivative.id, active_derivative_detail: pendingDerivative, fixup_status: "approved" }]} onChanged={vi.fn()} />);

  await user.click(screen.getByRole("button", { name: /Revert to original/i }));

  await waitFor(() => expect(mocks.revertPhotoFixup).toHaveBeenCalledWith("photo-1"));
  expect(await screen.findByText(/Reverted the display image to the retained original/i)).toBeInTheDocument();
});

function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } }
  });
  return render(
    <QueryClientProvider client={client}>
      {ui}
    </QueryClientProvider>
  );
}
