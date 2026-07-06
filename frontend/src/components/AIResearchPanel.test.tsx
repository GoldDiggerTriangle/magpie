import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { beforeEach, expect, test, vi } from "vitest";

import { AIResearchPanel } from "./AIResearchPanel";
import type { AIReferencesResult, AIResearchRunResult, AIStatus, FieldSuggestion } from "../types";

const mocks = vi.hoisted(() => ({
  configureAICredential: vi.fn(),
  disconnectAICredential: vi.fn(),
  getAIReferences: vi.fn(),
  getAIStatus: vi.fn(),
  runAIIdentify: vi.fn(),
  runAIPriceAssist: vi.fn()
}));

vi.mock("../api/intelligence", () => ({
  configureAICredential: (...args: unknown[]) => mocks.configureAICredential(...args),
  disconnectAICredential: (...args: unknown[]) => mocks.disconnectAICredential(...args),
  getAIReferences: (...args: unknown[]) => mocks.getAIReferences(...args),
  getAIStatus: (...args: unknown[]) => mocks.getAIStatus(...args),
  runAIIdentify: (...args: unknown[]) => mocks.runAIIdentify(...args),
  runAIPriceAssist: (...args: unknown[]) => mocks.runAIPriceAssist(...args)
}));

const disabledStatus: AIStatus = {
  configured: false,
  provider: "openai",
  model_id: "gpt-5.4-mini",
  monthly_budget_cap_usd: "5.00",
  monthly_usage_usd: "0.000000",
  budget_remaining_usd: "5.000000",
  enabled: false,
  disabled_reason: "Connect an AI provider to enable the deep-dive."
};

const enabledStatus: AIStatus = {
  ...disabledStatus,
  configured: true,
  enabled: true,
  disabled_reason: ""
};

const emptyReferences: AIReferencesResult = {
  search_terms: [],
  reference_links: []
};

const references: AIReferencesResult = {
  search_terms: [
    {
      id: "term-1",
      item: "item-1",
      phrase: "Australia 1932 Harbour Bridge 2d",
      source_basis: "AI search-term sharpening",
      created_by_call: "call-1",
      is_active: true,
      created_at: "2026-06-15T00:00:00Z",
      updated_at: "2026-06-15T00:00:00Z"
    }
  ],
  reference_links: [
    {
      id: "ref-1",
      item: "item-1",
      label: "Reference image search - Google Images",
      url: "https://www.google.com/search?tbm=isch&q=Australia%201932%20Harbour%20Bridge%202d",
      source_basis: "AI reference lookup",
      created_by_call: "call-1",
      created_at: "2026-06-15T00:00:00Z",
      updated_at: "2026-06-15T00:00:00Z"
    }
  ]
};

const stagedSuggestion: FieldSuggestion = {
  id: "suggestion-1",
  item: "item-1",
  item_sku: "STM-00001",
  item_title: "Bridge stamp",
  photo: null,
  photo_thumb_url: null,
  field: "attributes.country",
  proposed_value: "Australia",
  source: "ai",
  confidence_band: "high",
  evidence: "Fake AI evidence.",
  status: "pending",
  resolved_value: null,
  resolved_at: null,
  created_at: "2026-06-15T00:00:00Z",
  updated_at: "2026-06-15T00:00:00Z"
};

const runResult: AIResearchRunResult = {
  call: {
    id: "call-1",
    item: "item-1",
    phase: "identify",
    status: "success",
    provider: "fake",
    model_id: "fake-ai-research-v1",
    image_count: 1,
    exif_stripped: true,
    suggestions_created: 2,
    search_terms_created: 1,
    reference_links_created: 1,
    input_tokens: 100,
    output_tokens: 80,
    estimated_cost_usd: "0.000100",
    request_metadata: {},
    response_metadata: {},
    error: "",
    created_at: "2026-06-15T00:00:00Z",
    updated_at: "2026-06-15T00:00:00Z"
  },
  suggestions: [stagedSuggestion],
  search_terms: references.search_terms,
  reference_links: references.reference_links
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getAIStatus.mockResolvedValue(disabledStatus);
  mocks.getAIReferences.mockResolvedValue(emptyReferences);
  mocks.runAIIdentify.mockResolvedValue(runResult);
  mocks.runAIPriceAssist.mockResolvedValue({ ...runResult, call: { ...runResult.call, phase: "price_assist" } });
  mocks.configureAICredential.mockResolvedValue(enabledStatus);
  mocks.disconnectAICredential.mockResolvedValue(disabledStatus);
});

test("AIResearchPanel shows graceful disabled state with no key", async () => {
  renderWithClient(<AIResearchPanel itemId="item-1" />);

  await screen.findByText("Connect an AI provider to enable one-item-at-a-time deep-dives.");
  expect(screen.getByText("Connect an AI provider to enable the deep-dive.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Identify & fill/i })).toBeDisabled();
  expect(screen.getByRole("button", { name: /Price-assist search terms/i })).toBeDisabled();
  expect(screen.getByRole("button", { name: /Save encrypted key/i })).toBeDisabled();
  expect(screen.getByLabelText("API key")).toHaveAttribute("type", "password");
});

test("AIResearchPanel runs identify and keeps output staged", async () => {
  const user = userEvent.setup();
  const onReviewSuggestions = vi.fn();
  mocks.getAIStatus.mockResolvedValue(enabledStatus);
  mocks.getAIReferences.mockResolvedValue(references);
  renderWithClient(<AIResearchPanel itemId="item-1" onReviewSuggestions={onReviewSuggestions} />);

  await screen.findByText(/openai \/ gpt-5.4-mini/i);
  await user.click(screen.getByRole("button", { name: /Identify & fill/i }));

  await waitFor(() => expect(mocks.runAIIdentify).toHaveBeenCalledWith("item-1"));
  expect(await screen.findByText(/Identify & fill completed/i)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /Review 1 staged suggestions/i }));
  expect(onReviewSuggestions).toHaveBeenCalled();
  expect(screen.getByText("Australia 1932 Harbour Bridge 2d")).toBeInTheDocument();
  const reference = screen.getByRole("link", { name: /Reference image search/i });
  expect(reference).toHaveAttribute("target", "_blank");
  expect(reference).toHaveAttribute("href", expect.stringContaining("https://www.google.com/search"));
});

test("AIResearchPanel displays nonzero sub-cent usage honestly", async () => {
  mocks.getAIStatus.mockResolvedValue({
    ...enabledStatus,
    monthly_usage_usd: "0.000100",
    monthly_budget_cap_usd: "5.00"
  });

  renderWithClient(<AIResearchPanel itemId="item-1" />);

  expect(await screen.findByText(/<\$0\.01 used of \$5\.00 monthly cap/i)).toBeInTheDocument();
});

test("AIResearchPanel price assist does not surface price-like terms", async () => {
  const user = userEvent.setup();
  mocks.getAIStatus.mockResolvedValue(enabledStatus);
  mocks.getAIReferences.mockResolvedValue(references);
  renderWithClient(<AIResearchPanel itemId="item-1" />);

  await screen.findByText(/openai \/ gpt-5.4-mini/i);
  await user.click(screen.getByRole("button", { name: /Price-assist search terms/i }));

  await waitFor(() => expect(mocks.runAIPriceAssist).toHaveBeenCalledWith("item-1"));
  expect(await screen.findByText(/Price-assist completed/i)).toBeInTheDocument();
  expect(screen.queryByText(/\$100/)).not.toBeInTheDocument();
  expect(screen.queryByText(/estimated value 100/i)).not.toBeInTheDocument();
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
