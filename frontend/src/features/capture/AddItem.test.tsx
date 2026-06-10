import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, vi } from "vitest";

import { AddItem } from "./AddItem";

const mocks = vi.hoisted(() => ({
  listCategories: vi.fn(),
  listLocations: vi.fn(),
  createItem: vi.fn(),
  uploadItemPhoto: vi.fn()
}));

vi.mock("../../api/categories", () => ({
  listCategories: () => mocks.listCategories()
}));

vi.mock("../../api/locations", () => ({
  listLocations: () => mocks.listLocations()
}));

vi.mock("../../api/items", () => ({
  createItem: (...args: unknown[]) => mocks.createItem(...args),
  uploadItemPhoto: (...args: unknown[]) => mocks.uploadItemPhoto(...args)
}));

beforeEach(() => {
  mocks.listCategories.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  mocks.listLocations.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  mocks.createItem.mockResolvedValue({ id: "item-1" });
  mocks.uploadItemPhoto.mockResolvedValue({});
});

function renderAddItem() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } }
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AddItem />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

test("AddItem blocks submit with no title", async () => {
  renderAddItem();
  await userEvent.click(screen.getByRole("button", { name: /save item/i }));
  expect(await screen.findByText("Title is required.")).toBeInTheDocument();
});

test("AddItem blocks submit with no photo", async () => {
  renderAddItem();
  await userEvent.type(screen.getByLabelText(/title/i), "Stamp lot");
  await userEvent.click(screen.getByRole("button", { name: /save item/i }));
  expect(await screen.findByText("Add at least one photo.")).toBeInTheDocument();
});

test("AddItem keeps gold capture fields optional", async () => {
  mocks.listCategories.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [{
      id: "cat-gold",
      name: "Gold",
      slug: "gold",
      parent: null,
      sku_prefix: "GOLD",
      profile_key: "gold",
      description: ""
    }]
  });
  const user = userEvent.setup();
  renderAddItem();

  await user.type(screen.getByLabelText(/title/i), "Gold parcel");
  await user.selectOptions(await screen.findByLabelText(/category/i), "cat-gold");
  await user.upload(screen.getByLabelText(/add photos/i), new File(["photo"], "gold.jpg", { type: "image/jpeg" }));
  expect(screen.getByLabelText(/Weight g/)).toBeInTheDocument();
  expect(screen.getByLabelText(/Fineness/)).toBeInTheDocument();
  expect(screen.getByLabelText(/Karat/)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /save item/i }));

  expect(mocks.createItem).toHaveBeenCalledWith(expect.objectContaining({
    title: "Gold parcel",
    category: "cat-gold",
    attributes: { metal: "gold" }
  }));
  expect(mocks.uploadItemPhoto).toHaveBeenCalled();
});
