import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";

import { EbaySettings } from "./EbaySettings";
import type { AIStatus, EbayStatus } from "../../types";

const sandboxStatus: EbayStatus = {
  configured: true,
  environment: "sandbox",
  connected: true,
  requires_reconsent: false,
  missing_scopes: [],
  ebay_username: "fake_sandbox_seller",
  scopes: [
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.account.readonly",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment.readonly",
    "https://api.ebay.com/oauth/api_scope/sell.finances"
  ],
  access_token_expires_at: "2026-06-11T04:00:00Z",
  refresh_token_expires_at: "2026-12-11T04:00:00Z",
  last_refresh_error: "",
  snapshot: {
    opted_in: true,
    policy_counts: { payment: 1, fulfillment: 2, return: 3 },
    fetched_at: "2026-06-11T03:00:00Z"
  }
};

const aiDisconnectedStatus: AIStatus = {
  configured: false,
  provider: "openai",
  model_id: "gpt-5.4-mini",
  monthly_budget_cap_usd: "5.00",
  monthly_usage_usd: "0.000000",
  budget_remaining_usd: "5.000000",
  enabled: false,
  disabled_reason: "Connect an AI provider to enable the deep-dive."
};

const aiConnectedStatus: AIStatus = {
  ...aiDisconnectedStatus,
  configured: true,
  enabled: true,
  disabled_reason: "",
  monthly_usage_usd: "0.250000",
  budget_remaining_usd: "4.750000"
};

const mocks = vi.hoisted(() => ({
  configureAICredential: vi.fn(),
  completeEbayConnect: vi.fn(),
  disconnectAICredential: vi.fn(),
  disconnectEbay: vi.fn(),
  getEbayStatus: vi.fn(),
  getAIStatus: vi.fn(),
  listEbayOrderDuplicates: vi.fn(),
  listEbayOrderStaging: vi.fn(),
  listAuditLogs: vi.fn(),
  refreshEbayPolicies: vi.fn(),
  resolveEbayOrderDuplicate: vi.fn(),
  resolveEbayOrderStaging: vi.fn(),
  syncEbayOrders: vi.fn(),
  startEbayConnect: vi.fn()
}));

vi.mock("../../api/intelligence", () => ({
  configureAICredential: (...args: unknown[]) => mocks.configureAICredential(...args),
  disconnectAICredential: (...args: unknown[]) => mocks.disconnectAICredential(...args),
  getAIStatus: (...args: unknown[]) => mocks.getAIStatus(...args)
}));

vi.mock("../../api/ebay", () => ({
  completeEbayConnect: (...args: unknown[]) => mocks.completeEbayConnect(...args),
  disconnectEbay: (...args: unknown[]) => mocks.disconnectEbay(...args),
  getEbayStatus: (...args: unknown[]) => mocks.getEbayStatus(...args),
  listEbayOrderDuplicates: (...args: unknown[]) => mocks.listEbayOrderDuplicates(...args),
  listEbayOrderStaging: (...args: unknown[]) => mocks.listEbayOrderStaging(...args),
  refreshEbayPolicies: (...args: unknown[]) => mocks.refreshEbayPolicies(...args),
  resolveEbayOrderDuplicate: (...args: unknown[]) => mocks.resolveEbayOrderDuplicate(...args),
  resolveEbayOrderStaging: (...args: unknown[]) => mocks.resolveEbayOrderStaging(...args),
  syncEbayOrders: (...args: unknown[]) => mocks.syncEbayOrders(...args),
  startEbayConnect: (...args: unknown[]) => mocks.startEbayConnect(...args)
}));

vi.mock("../../api/audit", () => ({
  listAuditLogs: (...args: unknown[]) => mocks.listAuditLogs(...args)
}));

beforeEach(() => {
  mocks.configureAICredential.mockReset();
  mocks.configureAICredential.mockResolvedValue(aiConnectedStatus);
  mocks.completeEbayConnect.mockReset();
  mocks.completeEbayConnect.mockResolvedValue({ ebay_username: "fake_sandbox_seller" });
  mocks.disconnectAICredential.mockReset();
  mocks.disconnectAICredential.mockResolvedValue(aiDisconnectedStatus);
  mocks.disconnectEbay.mockReset();
  mocks.disconnectEbay.mockResolvedValue(undefined);
  mocks.getAIStatus.mockReset();
  mocks.getAIStatus.mockResolvedValue(aiDisconnectedStatus);
  mocks.getEbayStatus.mockReset();
  mocks.getEbayStatus.mockResolvedValue(sandboxStatus);
  mocks.listEbayOrderDuplicates.mockReset();
  mocks.listEbayOrderDuplicates.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  mocks.listEbayOrderStaging.mockReset();
  mocks.listEbayOrderStaging.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  mocks.listAuditLogs.mockReset();
  mocks.listAuditLogs.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [
      {
        id: "audit-1",
        actor: "sprint6",
        action: "ebay.connect.completed",
        target_type: "ebay_credential",
        target_id: "cred-1",
        payload: { environment: "sandbox" },
        created_at: "2026-06-11T03:00:00Z"
      }
    ]
  });
  mocks.refreshEbayPolicies.mockReset();
  mocks.refreshEbayPolicies.mockResolvedValue(sandboxStatus);
  mocks.resolveEbayOrderDuplicate.mockReset();
  mocks.resolveEbayOrderDuplicate.mockResolvedValue({});
  mocks.resolveEbayOrderStaging.mockReset();
  mocks.resolveEbayOrderStaging.mockResolvedValue({});
  mocks.syncEbayOrders.mockReset();
  mocks.syncEbayOrders.mockResolvedValue({
    environment: "sandbox",
    start: "2026-06-10T00:00:00Z",
    end: "2026-06-11T00:00:00Z",
    counts: {
      created: 0,
      staged: 1,
      duplicate_flagged: 0,
      skipped: 0,
      fee_authoritative: 0,
      fee_estimated_or_unmapped: 1
    }
  });
  mocks.startEbayConnect.mockReset();
  mocks.startEbayConnect.mockResolvedValue({ consent_url: "https://signin.sandbox.ebay.test/consent?state=abc" });
});

function renderSettings() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <EbaySettings />
    </QueryClientProvider>
  );
}

test("EbaySettings renders sandbox status, readiness counts, and audit rows", async () => {
  renderSettings();

  expect(await screen.findAllByText("SANDBOX")).toHaveLength(2);
  expect(screen.getByText("fake_sandbox_seller")).toBeInTheDocument();
  expect(screen.getByText("Payment")).toBeInTheDocument();
  expect(screen.getByText("1")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Sync eBay Orders" })).toBeInTheDocument();
  expect(screen.getAllByText("ebay.connect.completed").length).toBeGreaterThan(0);
  expect(screen.getByText("AI Provider")).toBeInTheDocument();
  expect(screen.getByDisplayValue("gpt-5.4-mini")).toBeInTheDocument();
});

test("EbaySettings renders nonzero sub-cent AI usage as less than one cent", async () => {
  mocks.getAIStatus.mockResolvedValue({
    ...aiConnectedStatus,
    monthly_usage_usd: "0.000100"
  });

  renderSettings();

  expect(await screen.findByText("<$0.01")).toBeInTheDocument();
});

test("EbaySettings saves an encrypted AI key without displaying it", async () => {
  const user = userEvent.setup();
  renderSettings();

  await screen.findByText("AI Provider");
  await user.type(screen.getByLabelText("API key"), "unit-test-openai-key");
  await user.click(screen.getByRole("button", { name: "Save AI" }));

  await waitFor(() => expect(mocks.configureAICredential).toHaveBeenCalledWith({
    provider: "openai",
    model_id: "gpt-5.4-mini",
    monthly_budget_cap_usd: "5.00",
    api_key: "unit-test-openai-key"
  }));
  expect(screen.queryByText("unit-test-openai-key")).not.toBeInTheDocument();
});

test("EbaySettings updates the AI model without resubmitting the stored key", async () => {
  const user = userEvent.setup();
  mocks.getAIStatus.mockResolvedValue(aiConnectedStatus);
  renderSettings();

  await screen.findByText("Configured");
  const model = screen.getByLabelText("Model");
  await user.clear(model);
  await user.type(model, "gpt-5.5");
  await user.click(screen.getByRole("button", { name: "Save AI" }));

  await waitFor(() => expect(mocks.configureAICredential).toHaveBeenCalledWith({
    provider: "openai",
    model_id: "gpt-5.5",
    monthly_budget_cap_usd: "5.00",
    api_key: ""
  }));
  expect(screen.getByPlaceholderText("Configured; paste a new key to replace")).toHaveAttribute("type", "password");
});

test("EbaySettings confirms before disconnecting AI", async () => {
  const user = userEvent.setup();
  mocks.getAIStatus.mockResolvedValue(aiConnectedStatus);
  renderSettings();

  await user.click(await screen.findByRole("button", { name: "Disconnect AI" }));
  expect(screen.getByText("Disconnect AI provider?")).toBeInTheDocument();
  const disconnectButtons = screen.getAllByRole("button", { name: "Disconnect" });
  await user.click(disconnectButtons[disconnectButtons.length - 1]);

  await waitFor(() => expect(mocks.disconnectAICredential).toHaveBeenCalled());
});

test("EbaySettings manually starts order sync and shows counts", async () => {
  const user = userEvent.setup();
  renderSettings();

  await user.click(await screen.findByRole("button", { name: "Sync eBay Orders" }));

  await waitFor(() => expect(mocks.syncEbayOrders).toHaveBeenCalled());
  expect(await screen.findByText("Staged")).toBeInTheDocument();
});

test("EbaySettings starts connect and completes the paste-back flow", async () => {
  const user = userEvent.setup();
  renderSettings();

  await user.click(await screen.findByRole("button", { name: "Connect" }));
  expect(await screen.findByText("https://signin.sandbox.ebay.test/consent?state=abc")).toBeInTheDocument();

  await user.type(screen.getByLabelText("Redirected URL"), "https://example.test?code=abc&state=abc");
  await user.click(screen.getByRole("button", { name: "Complete" }));

  await waitFor(() => expect(mocks.completeEbayConnect).toHaveBeenCalledWith({
    pasted_url: "https://example.test?code=abc&state=abc"
  }));
});

test("EbaySettings confirms before disconnecting", async () => {
  const user = userEvent.setup();
  renderSettings();

  await user.click(await screen.findByRole("button", { name: "Disconnect" }));
  expect(screen.getByText("Disconnect eBay?")).toBeInTheDocument();
  await user.click(screen.getAllByRole("button", { name: "Disconnect" })[1]);

  await waitFor(() => expect(mocks.disconnectEbay).toHaveBeenCalled());
});
