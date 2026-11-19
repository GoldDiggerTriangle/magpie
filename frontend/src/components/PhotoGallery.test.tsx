import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { PhotoGallery } from "./PhotoGallery";
import fixture from "../fixtures/listingEditor.json";
import type { PhotoAsset } from "../types";

test("Arrange mode retains set-main, both reorder directions, delete and saved order on resume", async () => {
  const photos = fixture.item.photos as unknown as PhotoAsset[];
  const main = vi.fn(), move = vi.fn(), remove = vi.fn();
  const view = render(<PhotoGallery photos={photos} onSetMain={main} onMove={move} onDelete={remove} />);
  expect(screen.queryByTitle("Set main")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Arrange" }));
  fireEvent.click(screen.getByRole("button", { name: "Set photo 2 as main" }));
  expect(main).toHaveBeenCalledWith(photos[1]);
  fireEvent.click(screen.getByRole("button", { name: "Move photo 1 later" }));
  expect(move).toHaveBeenCalledWith(photos[0], 1);
  fireEvent.click(screen.getByRole("button", { name: "Move photo 2 earlier" }));
  expect(move).toHaveBeenCalledWith(photos[1], -1);
  fireEvent.click(screen.getByRole("button", { name: "Delete photo 2" }));
  expect(remove).toHaveBeenCalledWith(photos[1]);
  view.unmount();
  render(<PhotoGallery photos={[photos[1], photos[0]]} />);
  expect(screen.getByRole("button", { name: "View photo 1 full size" }).querySelector("img")).toHaveAttribute("alt", `Photo 1: ${photos[1].role.replace(/_/g, " ")}`);
});
