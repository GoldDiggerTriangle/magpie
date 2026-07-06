import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { beforeEach, expect, test, vi } from "vitest";

import { SoldSearchPanel } from "./SoldSearchPanel";
import { SuggestionReviewPanel } from "./SuggestionReviewPanel";
import type { FieldSuggestion, OcrRunResult } from "../types";

const mocks = vi.hoisted(() => ({
  approveFieldSuggestion: vi.fn(),
  editFieldSuggestion: vi.fn(),
  getSoldSearchLinks: vi.fn(),
  listFieldSuggestions: vi.fn(),
  rejectFieldSuggestion: vi.fn(),
  runItemOcr: vi.fn(),
  scanItemDuplicates: vi.fn()
}));

vi.mock("../api/intelligence", () => ({
  approveFieldSuggestion: (...args: unknown[]) => mocks.approveFieldSuggestion(...args),
  editFieldSuggestion: (...args: unknown[]) => mocks.editFieldSuggestion(...args),
  getSoldSearchLinks: (...args: unknown[]) => mocks.getSoldSearchLinks(...args),
  listFieldSuggestions: (...args: unknown[]) => mocks.listFieldSuggestions(...args),
  rejectFieldSuggestion: (...args: unknown[]) => mocks.rejectFieldSuggestion(...args),
  runItemOcr: (...args: unknown[]) => mocks.runItemOcr(...args),
  scanItemDuplicates: (...args: unknown[]) => mocks.scanItemDuplicates(...args)
}));

const yearSuggestion: FieldSuggestion = {
  id: "suggestion-1",
  item: "item-1",
  item_sku: "STM-00001",
  item_title: "Bridge stamp",
  photo: "photo-1",
  photo_thumb_url: "/media/thumb.jpg",
  field: "attributes.year",
  proposed_value: "1932",
  source: "ocr",
  confidence_band: "medium",
  evidence: "OCR text: Recognised year 1932",
  status: "pending",
  resolved_value: null,
  resolved_at: null,
  created_at: "2026-06-15T00:00:00Z",
  updated_at: "2026-06-15T00:00:00Z"
};

const duplicateSuggestion: FieldSuggestion = {
  ...yearSuggestion,
  id: "suggestion-2",
  photo: "photo-2",
  field: "duplicate_candidate",
  proposed_value: { matched_sku: "STM-00002", distance: 2 },
  source: "duplicate",
  confidence_band: "candidate",
  evidence: "Near-duplicate image candidate: this photo is visually close to STM-00002."
};

const rejectedSuggestion: FieldSuggestion = {
  ...yearSuggestion,
  id: "suggestion-3",
  field: "attributes.country",
  proposed_value: "Australia",
  confidence_band: "high",
  status: "rejected"
};

const unavailableOcr: OcrRunResult = {
  available: false,
  detail: "OCR unavailable. Install local Tesseract to use OCR on this machine.",
  suggestions: []
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getSoldSearchLinks.mockResolvedValue({
    links: [
      {
        id: "broad",
        label: "Broad sold search",
        query: "Australia 1932 2d",
        url: "https://www.ebay.com.au/sch/i.html?_nkw=Australia+1932+2d&LH_Sold=1&LH_Complete=1"
      },
      {
        id: "auction",
        label: "Auction sold search",
        query: "Australia 1932 2d",
        url: "https://www.ebay.com.au/sch/i.html?_nkw=Australia+1932+2d&LH_Sold=1&LH_Complete=1&LH_Auction=1"
      }
    ]
  });
  mocks.listFieldSuggestions.mockResolvedValue({
    count: 2,
    next: null,
    previous: null,
    results: [yearSuggestion, duplicateSuggestion]
  });
  mocks.runItemOcr.mockResolvedValue(unavailableOcr);
  mocks.scanItemDuplicates.mockResolvedValue({ suggestions: [duplicateSuggestion] });
  mocks.approveFieldSuggestion.mockResolvedValue({ ...yearSuggestion, status: "approved" });
  mocks.editFieldSuggestion.mockResolvedValue({ ...yearSuggestion, status: "edited", resolved_value: "1933" });
  mocks.rejectFieldSuggestion.mockResolvedValue({ ...yearSuggestion, status: "rejected" });
});

test("SoldSearchPanel renders public eBay sold-search links without fetching results", async () => {
  renderWithClient(<SoldSearchPanel itemId="item-1" />);

  const broad = await screen.findByRole("link", { name: /Broad sold search/i });
  expect(broad).toHaveAttribute("href", expect.stringContaining("https://www.ebay.com.au/sch/i.html"));
  expect(broad).toHaveAttribute("href", expect.stringContaining("LH_Sold=1"));
  expect(broad).toHaveAttribute("href", expect.stringContaining("LH_Complete=1"));
  expect(broad).toHaveAttribute("target", "_blank");
  expect(screen.getByRole("link", { name: /Auction sold search/i })).toHaveAttribute("href", expect.stringContaining("LH_Auction=1"));
});

test("SuggestionReviewPanel shows OCR unavailable and keeps candidate leads separate", async () => {
  const user = userEvent.setup();
  renderWithClient(<SuggestionReviewPanel itemId="item-1" />);

  expect(await screen.findByText("Reviewable field suggestions")).toBeInTheDocument();
  expect(screen.getByText("Low-confidence leads")).toBeInTheDocument();
  expect(screen.getByText(/Near-duplicate image candidate/)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Run OCR" }));

  expect(await screen.findByText(/OCR unavailable/)).toBeInTheDocument();
  expect(mocks.runItemOcr).toHaveBeenCalledWith("item-1");
});

test("SuggestionReviewPanel requires explicit approve edit or reject actions", async () => {
  const user = userEvent.setup();
  renderWithClient(<SuggestionReviewPanel itemId="item-1" />);

  await screen.findByText("OCR text: Recognised year 1932");
  expect(mocks.approveFieldSuggestion).not.toHaveBeenCalled();
  expect(mocks.editFieldSuggestion).not.toHaveBeenCalled();
  expect(mocks.rejectFieldSuggestion).not.toHaveBeenCalled();

  const row = screen.getByText("OCR text: Recognised year 1932").closest("article");
  expect(row).not.toBeNull();
  await user.clear(within(row as HTMLElement).getByLabelText("Edit value"));
  await user.type(within(row as HTMLElement).getByLabelText("Edit value"), "1933");
  await user.click(within(row as HTMLElement).getByRole("button", { name: "Edit" }));

  await waitFor(() => expect(mocks.editFieldSuggestion).toHaveBeenCalledWith("suggestion-1", "1933"));

  await user.click(within(row as HTMLElement).getByRole("button", { name: "Approve" }));
  await waitFor(() => expect(mocks.approveFieldSuggestion).toHaveBeenCalledWith("suggestion-1"));

  await user.click(within(row as HTMLElement).getByRole("button", { name: "Reject" }));
  await waitFor(() => expect(mocks.rejectFieldSuggestion).toHaveBeenCalledWith("suggestion-1"));
});

test("SuggestionReviewPanel approve all applies exactly visible non-rejected suggestions", async () => {
  const user = userEvent.setup();
  mocks.listFieldSuggestions.mockResolvedValue({
    count: 3,
    next: null,
    previous: null,
    results: [yearSuggestion, duplicateSuggestion, rejectedSuggestion]
  });
  renderWithClient(<SuggestionReviewPanel itemId="item-1" />);

  const approveAll = await screen.findByRole("button", { name: "Approve all shown" });
  expect(mocks.approveFieldSuggestion).not.toHaveBeenCalled();
  await user.click(approveAll);

  await waitFor(() => expect(mocks.approveFieldSuggestion).toHaveBeenCalledTimes(2));
  expect(mocks.approveFieldSuggestion).toHaveBeenNthCalledWith(1, "suggestion-1");
  expect(mocks.approveFieldSuggestion).toHaveBeenNthCalledWith(2, "suggestion-2");
  expect(mocks.approveFieldSuggestion).not.toHaveBeenCalledWith("suggestion-3");
});

test("SuggestionReviewPanel disables approve all until suggestions render", async () => {
  let resolveSuggestions: (value: unknown) => void = () => undefined;
  mocks.listFieldSuggestions.mockReturnValue(new Promise((resolve) => { resolveSuggestions = resolve; }));
  renderWithClient(<SuggestionReviewPanel itemId="item-1" />);

  expect(screen.getByRole("button", { name: "Approve all shown" })).toBeDisabled();

  resolveSuggestions({
    count: 1,
    next: null,
    previous: null,
    results: [yearSuggestion]
  });

  expect(await screen.findByText("OCR text: Recognised year 1932")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Approve all shown" })).toBeEnabled();
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
