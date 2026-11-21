import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test } from "vitest";
import { DEFAULT_ROW, KPI_TILE_IDS, KpiTile, formatTile, sanitizeSelectedTiles } from "./KpiRegister";
import type { DashboardKpiTile } from "../../types";

const base: DashboardKpiTile = { id:"realised_profit", label:"Profit this month", value:"0.34", format:"currency", description:"Ledger profit", secondary:"", excluded_count:0 };
test("cents, no sales, unknown and genuine zero remain distinct", () => {
  expect(formatTile(base)).toBe("$0.34");
  expect(formatTile({...base,value:"0.00",state:"known"})).toBe("$0.00");
  expect(formatTile({...base,value:null,state:"unknown"})).toBe("Profit unknown");
  expect(formatTile({...base,state:"no_sales"})).toBe("No sales this month");
  expect(formatTile({...base,value:"-12.45",state:"known"})).toBe("-$12.45");
});
test("monthly figures link to the matching period; eBay is labelled local", () => {
  render(<MemoryRouter><KpiTile tile={base} /><KpiTile tile={{...base,id:"ebay_listings",label:"eBay listings",format:"integer",value:"2",secondary:"Marked active in Magpie"}} /></MemoryRouter>);
  expect(screen.getByRole("link", {name:/Profit this month/})).toHaveAttribute("href","/profit?range=this_month#profit-summary");
  expect(screen.getByRole("link", {name:/Marked active in Magpie/})).toHaveAttribute("href","/ebay#live-listings");
});
test("new default row and saved ordering survive sanitising", () => {
  expect(new Set(KPI_TILE_IDS).size).toBe(14);
  expect(DEFAULT_ROW).toEqual(["realised_profit","items_sold","stock_on_hand","ebay_listings"]);
  const old = ["gross_revenue","net_proceeds","items_sold"] as const;
  expect(sanitizeSelectedTiles([...old],[])).toEqual([...old]);
});
