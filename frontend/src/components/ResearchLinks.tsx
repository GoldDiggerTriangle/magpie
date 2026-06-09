import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";

import { getResearchLinks } from "../api/research";
import type { UUID } from "../types";

export function ResearchLinks({ itemId }: { itemId: UUID }) {
  const links = useQuery({ queryKey: ["research-links", itemId], queryFn: () => getResearchLinks(itemId) });

  return (
    <section className="rounded border border-slate-800 bg-slate-950/40 p-4">
      <h2 className="section-title">Assisted research</h2>
      <div className="mt-3 flex flex-wrap gap-2">
        {(links.data?.links ?? []).map((link) => (
          <a key={link.label} className="btn-secondary gap-2" href={link.url} target="_blank" rel="noreferrer">
            <ExternalLink className="h-4 w-4" aria-hidden="true" />
            {link.label}
          </a>
        ))}
        {links.isLoading ? <span className="text-sm text-slate-400">Loading links</span> : null}
      </div>
    </section>
  );
}

