import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { AppShell } from "../src/components/AppShell";
import { Dashboard } from "../src/features/dashboard/Dashboard";
import { ProfitPage } from "../src/features/profit/ProfitPage";
import { InventoryGrid } from "../src/features/inventory/InventoryGrid";
import { ItemDetail } from "../src/features/inventory/ItemDetail";
import { AddItem } from "../src/features/capture/AddItem";
import { EbayHub } from "../src/features/ebay/EbayHub";
import { EbayOrders } from "../src/features/ebay/EbayOrders";
import "../src/styles/index.css";

function Destination() { const here = useLocation(), navigate = useNavigate(); (window as unknown as { s28Back: () => void }).s28Back = () => navigate(-1); return <output hidden data-testid="destination">{here.pathname}{here.search}{here.hash}</output>; }
const entry = new URLSearchParams(location.search).get("entry") || "/";
const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[entry]}>
  <Destination /><Routes><Route element={<AppShell />}>
    <Route index element={<Dashboard />} /><Route path="dashboard" element={<Dashboard />} />
    <Route path="profit" element={<ProfitPage />} /><Route path="inventory" element={<InventoryGrid />} />
    <Route path="inventory/:id" element={<ItemDetail />} /><Route path="add" element={<AddItem />} />
    <Route path="ebay" element={<EbayHub />} /><Route path="ebay/orders" element={<EbayOrders />} />
    <Route path="*" element={<h1>Existing task destination</h1>} />
  </Route></Routes>
</MemoryRouter></QueryClientProvider>);
