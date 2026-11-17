import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { MerchantLocationSetup } from "./MerchantLocationSetup";

const create = vi.hoisted(() => vi.fn());
vi.mock("../api/ebay", () => ({ createMerchantLocation: (...args: unknown[]) => create(...args) }));
test("legacy location creation has a home, needs explicit confirmation and never auto-applies a location", async () => {
  create.mockResolvedValue({ configured: true, location: { merchant_location_key: "OWN-LOCATION" } });
  const refreshed = vi.fn();
  render(<QueryClientProvider client={new QueryClient()}><MerchantLocationSetup onCreated={refreshed} /></QueryClientProvider>);
  expect(create).not.toHaveBeenCalled();
  await userEvent.click(screen.getByText("Create merchant location"));
  for (const [label, value] of [["New location key", "OWN-LOCATION"], ["Location name", "Own warehouse"], ["Country code", "AU"], ["City", "Maryborough"], ["State / province", "VIC"], ["Postcode", "3465"]]) {
    await userEvent.type(screen.getByRole("textbox", { name: label }), value);
  }
  await userEvent.click(screen.getByRole("button", { name: "Review new location" }));
  expect(screen.getByRole("alertdialog")).toHaveTextContent("Maryborough");
  expect(create).not.toHaveBeenCalled(); expect(refreshed).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Confirm create location" }));
  expect(await screen.findByRole("status")).toHaveTextContent("was not applied to the draft");
  expect(create).toHaveBeenCalledWith({ merchant_location_key: "OWN-LOCATION", name: "Own warehouse", country: "AU", city: "Maryborough", state: "VIC", postal_code: "3465" });
  expect(refreshed).toHaveBeenCalledTimes(1);
});
