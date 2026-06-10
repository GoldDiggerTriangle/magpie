import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { ResearchLinks } from "./ResearchLinks";

const mocks = vi.hoisted(() => ({
  getResearchLinks: vi.fn()
}));

vi.mock("../api/research", () => ({
  getResearchLinks: (...args: unknown[]) => mocks.getResearchLinks(...args)
}));

beforeEach(() => {
  mocks.getResearchLinks.mockResolvedValue({
    item: "item-1",
    links: [
      {
        type: "link",
        label: "Numista",
        url: "https://en.numista.com/catalogue/index.php?r=Australia&ct=coin",
        note: "",
        source: "public search"
      },
      {
        type: "checklist",
        label: "Check Renniks AU Coin & Banknote Values (latest ed.)",
        url: null,
        note: "Print catalogue - no public searchable DB. Enter values as kind=catalogue comps.",
        source: "manual checklist"
      }
    ]
  });
});

function renderResearchLinks() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  render(
    <QueryClientProvider client={queryClient}>
      <ResearchLinks itemId="item-1" />
    </QueryClientProvider>
  );
}

test("ResearchLinks renders URL links with source tags", async () => {
  renderResearchLinks();

  const link = await screen.findByRole("link", { name: /Numista public search/i });
  expect(link).toHaveAttribute("href", "https://en.numista.com/catalogue/index.php?r=Australia&ct=coin");
  expect(screen.getByText("public search")).toBeInTheDocument();
});

test("ResearchLinks renders checklist entries as non-clickable rows", async () => {
  renderResearchLinks();

  const renniks = await screen.findByText("Check Renniks AU Coin & Banknote Values (latest ed.)");
  expect(renniks.closest("a")).toBeNull();
  expect(screen.getByText(/Print catalogue/)).toBeInTheDocument();
  expect(screen.getByText("manual checklist")).toBeInTheDocument();
});
