import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import { FeeEnginePanel } from "./FeeEnginePanel";
import { calculateOrderLocal, proBasicLocal } from "../features/profit/feeMath";
import fixture from "../fixtures/sprint25FeeParity.json";
import type { FeeOrder } from "../api/feeEngine";
import type { BuyCalculationPayload } from "../types";
import { calculateLocalBuy } from "../features/profit/localCalculator";

const mocks = vi.hoisted(() => ({ get: vi.fn(), save: vi.fn(), calculate: vi.fn() }));
vi.mock("../api/feeEngine", () => ({ getFeeCalendar: (...a: unknown[]) => mocks.get(...a), saveFeeCalendar: (...a: unknown[]) => mocks.save(...a), calculateOrderFees: (...a: unknown[]) => mocks.calculate(...a) }));
const empty = { current: null, today: "2026-11-18", state: "schedule unknown", gst_note: "Regan is not registered for GST. Enter GST-inclusive fees exactly as eBay shows them.", legacy: [{ id: "old", name: "Old schedule", label: "Legacy / unverified - history only" }], versions: [], categories: { source: "Fixture", categories: { coins: { tier: "tier4", roots: ["11116"] } } } };
beforeEach(() => { vi.clearAllMocks(); mocks.get.mockResolvedValue(empty); mocks.save.mockResolvedValue({ id: "version", number: 1, periods: [] }); mocks.calculate.mockResolvedValue({ state: "schedule unknown", label: "schedule unknown", fee_total: null, lines: {} }); });
function open() { render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><FeeEnginePanel /></MemoryRouter></QueryClientProvider>); }

test.each(fixture.cases)("shared fee parity: $id", (c) => {
  const r = calculateOrderLocal(c.order as FeeOrder, fixture.period, fixture.rates);
  expect(r.fee_total).toBe(c.total); expect(r.gst_added).toBe("0.00");
  if ("revenue" in c) expect(r.lines.a.revenue).toBe(c.revenue);
  expect(Object.values(r.lines).reduce((sum, l) => sum + Number(l.components.per_order_fee), 0)).toBeCloseTo(0.33);
});
test("missing calendar/rate is unknown, never the old Pro percentage", () => {
  expect(() => proBasicLocal(fixture.cases[0].order, undefined)).toThrow("schedule unknown");
  const data = { ...empty, current: { id: "v", number: 1, label: "Fixture", source_note: "Fixture", source_url: "", periods: [{ plan: "pro_basic", effective_from: "2026-01-01", effective_to: null, per_order_fee: "0.33", international_pct: "1.1", gst_treatment: "inclusive", source_note: "Fixture", rates: [] }] } };
  expect(proBasicLocal(fixture.cases[0].order, data).fee_total).toBeNull();
});
test("Pro Basic reverse-margin fixture agrees with backend and persists nothing", () => {
  const data = { ...empty, current: { id: "v", number: 1, label: "Fixture", source_note: "Fixture", source_url: "", periods: [{ plan: "pro_basic", effective_from: "2026-01-01", effective_to: null, ...fixture.period, gst_treatment: "inclusive", source_note: "Fixture", rates: Object.values(fixture.rates) }] } };
  const result = calculateLocalBuy(fixture.buy_case as BuyCalculationPayload, undefined, data);
  expect(result.max_buy).toBe(fixture.buy_case.expected_max_buy); expect(result.expected_profit_at_asking).toBe(fixture.buy_case.expected_profit); expect(result.roi_at_asking).toBe(fixture.buy_case.expected_roi); expect(result.verdict).toBe("BUY");
  expect(mocks.save).not.toHaveBeenCalled();
});
test("no rates or dates seeded; explicit rendered review precedes immutable save", async () => {
  const enter = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
  open(); await userEvent.click(await screen.findByRole("button", { name: "Enter plan periods and rates" }));
  expect(mocks.save).not.toHaveBeenCalled(); await userEvent.click(screen.getByRole("button", { name: "Add period" }));
  expect(screen.getByLabelText("Fixed fee per order")).toHaveValue(""); expect(screen.getByLabelText("Effective from")).toHaveValue("");
  enter("Version label", "Human fixture"); enter("Source / provenance", "Observed fee page");
  enter("Effective from", "2026-01-01");
  enter("Fixed fee per order", "0.33"); enter("International fee %", "1.1");
  enter("Period source / date confirmation", "Confirmed by human");
  await userEvent.click(screen.getByRole("button", { name: "Add tier" }));
  expect(screen.getByLabelText("Per-item threshold")).toHaveValue("");
  enter("FVF % up to threshold", "13.09"); enter("Per-item threshold", "4000"); enter("FVF % above threshold", "2.75");
  await userEvent.click(screen.getByRole("button", { name: "Review new version" }));
  expect(screen.getByRole("region", { name: "Review fee calendar" })).toBeVisible(); expect(mocks.save).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Save confirmed version" }));
  await waitFor(() => expect(mocks.save).toHaveBeenCalledTimes(1));
  expect(mocks.save.mock.calls[0][0].periods[0]).toMatchObject({ per_order_fee: "0.33", gst_treatment: "inclusive", rates: [{ tier: "tier4", fvf_pct: "13.09", threshold: "4000", above_pct: "2.75" }] });
});
test("legacy label and GST status are visible; loading never calculates or saves", async () => {
  open(); expect(await screen.findByText(/Regan is not registered for GST/)).toBeVisible();
  await userEvent.click(screen.getByText("Legacy schedules — unverified history"));
  expect(screen.getByText(/Old schedule.*unverified/)).toBeVisible(); expect(mocks.save).not.toHaveBeenCalled(); expect(mocks.calculate).not.toHaveBeenCalled();
});
