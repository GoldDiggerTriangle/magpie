import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import fixture from "../fixtures/listingEditor.json";
import { defaultValues, defaultsForm, type ListingDefaults } from "../api/listingDefaults";
import { ListingDefaultsPanel, SaveListingDefaults } from "./ListingDefaultsPanel";
import type { ListingDraft } from "../types";
import type { ListingEditorContext } from "../api/listing";

const mocks = vi.hoisted(() => ({ list: vi.fn(), get: vi.fn(), preview: vi.fn(), save: vi.fn(), refresh: vi.fn(), browse: vi.fn() }));
vi.mock("../api/listingDefaults", async (original) => ({ ...await original<typeof import("../api/listingDefaults")>(),
  listListingDefaults: (...args: unknown[]) => mocks.list(...args), getListingDefaults: (...args: unknown[]) => mocks.get(...args),
  previewListingDefaults: (...args: unknown[]) => mocks.preview(...args), saveListingDefaults: (...args: unknown[]) => mocks.save(...args),
  refreshListingDefaultsMetadata: (...args: unknown[]) => mocks.refresh(...args), browseListingDefaultsCategory: (...args: unknown[]) => mocks.browse(...args)
}));
let saved: ListingDefaults;
beforeEach(() => {
  vi.clearAllMocks();
  saved = { category: "gold", category_name: "Gold", values: defaultValues(fixture.draft as ListingDraft), revision: "revision", updated_at: null, editor: structuredClone(fixture.editor) as ListingEditorContext, validation: [] };
  mocks.list.mockResolvedValue({ categories: [{ id: "gold", name: "Gold", configured: true }, { id: "stamps", name: "Stamps", configured: false }] });
  mocks.get.mockImplementation(async () => structuredClone(saved));
  mocks.preview.mockImplementation(async (_id, values) => ({ values, expected_revision: "revision", category_name: "Gold", changes: [{ field: "payment_policy_id", label: "Payment policy", before: "p1", after: values.payment_policy_id || "", clears: !values.payment_policy_id }] }));
  mocks.save.mockImplementation(async (_id, preview) => ({ ...saved, values: preview.values }));
  mocks.refresh.mockResolvedValue(saved);
});
function open(ui = <ListingDefaultsPanel />) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>{ui}</QueryClientProvider>);
}

test("Settings category rows reuse native pickers and real policy terms without mount writes", async () => {
  const user = userEvent.setup();
  open();
  await user.click(await screen.findByRole("button", { name: /Gold · Set/ }));
  expect(await screen.findByLabelText("Default format")).toHaveValue("fixed");
  expect(screen.getByRole("button", { name: "Browse categories" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Search eBay" })).toBeInTheDocument();
  expect(screen.getByLabelText("fulfillment policy terms")).toHaveTextContent("$12.50");
  expect(screen.queryByLabelText("Price", { exact: true })).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Quantity", { exact: true })).not.toBeInTheDocument();
  expect(mocks.save).not.toHaveBeenCalled();
  expect(mocks.preview).not.toHaveBeenCalled();
  expect(mocks.refresh).not.toHaveBeenCalled();
});

test("save-as-defaults reviews the exact snapshot and clearing before explicit confirmation", async () => {
  const user = userEvent.setup();
  open(<SaveListingDefaults categoryId="gold" categoryName="Gold" values={{ listing_format: "auction" }} />);
  await user.click(screen.getByRole("button", { name: "Save these as Gold defaults" }));
  const preview = await screen.findByRole("region", { name: "Gold defaults change preview" });
  expect(preview).toHaveTextContent("Clears existing default");
  expect(preview).toHaveTextContent("[empty]");
  expect(mocks.save).not.toHaveBeenCalled();
  await user.click(within(preview).getByRole("button", { name: "Cancel" }));
  expect(mocks.save).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Save these as Gold defaults" }));
  await user.click(await screen.findByRole("button", { name: "Confirm defaults changes" }));
  await waitFor(() => expect(mocks.save).toHaveBeenCalledWith("gold", expect.objectContaining({ values: { listing_format: "auction" }, expected_revision: "revision" })));
  expect(await screen.findByRole("status")).toHaveTextContent("Existing drafts are unchanged");
});

test("Settings edits and clear use the same preview with no implicit defaults save", async () => {
  const user = userEvent.setup();
  open();
  await user.click(await screen.findByRole("button", { name: /Gold · Set/ }));
  await user.selectOptions(await screen.findByLabelText("Default format"), "auction");
  expect(mocks.save).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Review and save defaults" }));
  await waitFor(() => expect(mocks.preview).toHaveBeenCalledWith("gold", expect.objectContaining({ listing_format: "auction", listing_duration: "" })));
  await user.click(await screen.findByRole("button", { name: "Cancel" }));
  await user.click(screen.getByRole("button", { name: "Clear Gold defaults" }));
  await waitFor(() => expect(mocks.preview).toHaveBeenLastCalledWith("gold", {}));
  expect(await screen.findByText("Clears existing default")).toBeInTheDocument();
  expect(mocks.save).not.toHaveBeenCalled();
});

test("defaults extraction cannot include price, quantity, item specifics or offer state", () => {
  const form = defaultsForm("gold", { listing_format: "fixed", category_id: "139965" });
  const values = defaultValues({ ...form, price: "999", quantity: 7, item_specifics: [{ name: "Never", value: "copy" }], channel_data: { ...form.channel_data, offer_id: "never" } });
  expect(values).not.toHaveProperty("price");
  expect(values).not.toHaveProperty("quantity");
  expect(values).not.toHaveProperty("item_specifics");
  expect(values).not.toHaveProperty("offer_id");
});

test("defaults metadata refresh is explicit and search selection never saves defaults", async () => {
  const user = userEvent.setup();
  open();
  await user.click(await screen.findByRole("button", { name: /Gold · Set/ }));
  await screen.findByLabelText("Default format");
  fireEvent.change(screen.getByPlaceholderText("e.g. gold nugget"), { target: { value: "nugget" } });
  await user.click(screen.getByRole("button", { name: "Search eBay" }));
  await waitFor(() => expect(mocks.refresh).toHaveBeenCalledWith("gold", { category_id: "139965", query: "nugget" }));
  expect(mocks.save).not.toHaveBeenCalled();
});
