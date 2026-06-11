import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";

import { EbaySettings } from "./EbaySettings";
import type { EbayStatus } from "../../types";

const sandboxStatus: EbayStatus = {
  configured: true,
  environment: "sandbox",
  connected: true,
  ebay_username: "fake_sandbox_seller",
  scopes: [
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.account.readonly"
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

const mocks = vi.hoisted(() => ({
  completeEbayConnect: vi.fn(),
  disconnectEbay: vi.fn(),
  getEbayStatus: vi.fn(),
  listAuditLogs: vi.fn(),
  refreshEbayPolicies: vi.fn(),
  startEbayConnect: vi.fn()
}));

vi.mock("../../api/ebay", () => ({
  completeEbayConnect: (...args: unknown[]) => mocks.completeEbayConnect(...args),
  disconnectEbay: (...args: unknown[]) => mocks.disconnectEbay(...args),
  getEbayStatus: (...args: unknown[]) => mocks.getEbayStatus(...args),
  refreshEbayPolicies: (...args: unknown[]) => mocks.refreshEbayPolicies(...args),
  startEbayConnect: (...args: unknown[]) => mocks.startEbayConnect(...args)
}));

vi.mock("../../api/audit", () => ({
  listAuditLogs: (...args: unknown[]) => mocks.listAuditLogs(...args)
}));

beforeEach(() => {
  mocks.completeEbayConnect.mockReset();
  mocks.completeEbayConnect.mockResolvedValue({ ebay_username: "fake_sandbox_seller" });
  mocks.disconnectEbay.mockReset();
  mocks.disconnectEbay.mockResolvedValue(undefined);
  mocks.getEbayStatus.mockReset();
  mocks.getEbayStatus.mockResolvedValue(sandboxStatus);
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
  expect(screen.getByText("ebay.connect.completed")).toBeInTheDocument();
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
