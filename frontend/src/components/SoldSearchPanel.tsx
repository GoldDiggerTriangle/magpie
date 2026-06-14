import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Search } from "lucide-react";

import { getSoldSearchLinks } from "../api/intelligence";
import type { UUID } from "../types";
import { EmptyState } from "./EmptyState";

export function SoldSearchPanel({ itemId }: { itemId: UUID }) {
  const links = useQuery({
    queryKey: ["sold-search-links", itemId],
    queryFn: () => getSoldSearchLinks(itemId)
  });

  return (
    <section className="intelligence-panel">
      <div className="intelligence-panel-header">
        <div>
          <p className="intelligence-kicker">Market angles</p>
          <h2>Search eBay sold</h2>
          <p>Open sold/completed searches in your browser. Magpie builds links only; it does not fetch or store result pages.</p>
        </div>
        <Search className="h-5 w-5 text-[#9A7B2E]" aria-hidden="true" />
      </div>

      {links.isLoading ? <div className="intelligence-skeleton" /> : null}
      {links.error ? <EmptyState title="Unable to build sold-search links" detail="Check your Django admin session." /> : null}
      {!links.isLoading && !links.error && (links.data?.links.length ?? 0) === 0 ? (
        <EmptyState title="No useful sold-search angles yet" detail="Add a title, category, or valuation and Magpie will build search links here." />
      ) : null}

      <div className="sold-search-grid">
        {links.data?.links.map((link) => (
          <a
            className="sold-search-link"
            href={link.url}
            key={link.id}
            rel="noreferrer"
            target="_blank"
          >
            <span>
              <strong>{link.label}</strong>
              <small>{link.query}</small>
            </span>
            <ExternalLink className="h-4 w-4" aria-hidden="true" />
          </a>
        ))}
      </div>
    </section>
  );
}
