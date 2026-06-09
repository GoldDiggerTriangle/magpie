import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { AddItem } from "./AddItem";

vi.mock("../../api/categories", () => ({
  listCategories: () => Promise.resolve({ count: 0, next: null, previous: null, results: [] })
}));

vi.mock("../../api/locations", () => ({
  listLocations: () => Promise.resolve({ count: 0, next: null, previous: null, results: [] })
}));

vi.mock("../../api/items", () => ({
  createItem: vi.fn(),
  uploadItemPhoto: vi.fn()
}));

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
