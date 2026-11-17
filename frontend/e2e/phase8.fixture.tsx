import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "../src/components/AppShell";
import { EbayQuantityPanel } from "../src/components/EbayQuantityPanel";
import "../src/styles/index.css";

const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/inventory/owned"]}>
  <Routes><Route element={<AppShell />}><Route path="/inventory/owned" element={<div className="item-page-frame space-y-5"><h1 className="page-title">Synthetic own stock</h1><EbayQuantityPanel itemId="owned" /><EbayQuantityPanel itemId="legacy" /></div>} /></Route></Routes>
</MemoryRouter></QueryClientProvider>);
