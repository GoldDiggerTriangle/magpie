import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { PublishHealthPanel } from "./PublishHealthPanel";

const mocks = vi.hoisted(() => ({ health: vi.fn(), reconcile: vi.fn() }));
vi.mock("../api/listingWorkflow", () => ({ getPublishHealth: (...a: unknown[]) => mocks.health(...a), reconcileListing: (...a: unknown[]) => mocks.reconcile(...a) }));
beforeEach(() => vi.clearAllMocks());
function open() { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><PublishHealthPanel /></QueryClientProvider>); }
test("health reads local stuck attempts, never retries a publish on mount", async () => {
  mocks.health.mockResolvedValue({ drafts: [{ id: "draft-1", sku: "TEST-1", status: "publish_unknown", message: "Outcome unknown; reconcile", started_at: null }] });
  open(); expect(await screen.findByText("TEST-1: publish unknown")).toBeInTheDocument();
  expect(mocks.reconcile).not.toHaveBeenCalled();
  mocks.reconcile.mockResolvedValue({ status: "publish_unknown" });
  await userEvent.click(screen.getByRole("button", { name: "Reconcile offer" }));
  expect(mocks.reconcile).toHaveBeenCalledWith("draft-1");
  expect(await screen.findByText("Outcome unknown; reconcile")).toBeInTheDocument();
});
test("health honestly shows no interrupted attempts", async () => {
  mocks.health.mockResolvedValue({ drafts: [] }); open();
  expect(await screen.findByText("No interrupted publish attempts.")).toBeInTheDocument();
});
test("health lookup failure is not shown as a healthy empty result", async () => {
  mocks.health.mockRejectedValue(new Error("offline")); open();
  expect(await screen.findByRole("alert")).toHaveTextContent("Publish status unavailable");
  expect(screen.queryByText("No interrupted publish attempts.")).not.toBeInTheDocument();
});
