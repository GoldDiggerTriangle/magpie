import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "../src/components/AppShell";
import { ItemDetail } from "../src/features/inventory/ItemDetail";
import { EbayHub } from "../src/features/ebay/EbayHub";
import "../src/styles/index.css";

const params = new URLSearchParams(location.search);
const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={client}>
  <MemoryRouter initialEntries={[params.get("entry") || "/inventory/item-fixture"]}>
    <Routes><Route element={<AppShell />}><Route path="/inventory/:id" element={<ItemDetail />} /><Route path="/ebay" element={<EbayHub />} /></Route></Routes>
  </MemoryRouter>
</QueryClientProvider>);
