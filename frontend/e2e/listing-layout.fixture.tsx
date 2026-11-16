import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "../src/components/AppShell";
import { ListingPanel } from "../src/components/ListingPanel";
import fixture from "../src/fixtures/listingEditor.json";
import type { InventoryItemDetail } from "../src/types";
import "../src/styles/index.css";

const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
const item = fixture.item as unknown as InventoryItemDetail;
createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={client}>
    <MemoryRouter>
      <Routes><Route element={<AppShell />}><Route path="/" element={
        <div className="item-page-frame">
          <h1 className="page-title">Isolated gold listing</h1>
          <div className="item-detail-layout"><div className="item-section-stack">
            <section className="item-detail-section">
              <h2 className="item-detail-section-header">Listings / channels</h2>
              <div className="item-detail-section-body"><div className="grid gap-6"><ListingPanel item={item} /></div></div>
            </section>
          </div></div>
        </div>
      } /></Route></Routes>
    </MemoryRouter>
  </QueryClientProvider>,
);
