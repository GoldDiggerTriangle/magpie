import { useQuery } from "@tanstack/react-query";
import { CheckSquare, ExternalLink } from "lucide-react";

import { getResearchLinks } from "../api/research";
import type { UUID } from "../types";

export function ResearchLinks({ itemId }: { itemId: UUID }) {
  const links = useQuery({ queryKey: ["research-links", itemId], queryFn: () => getResearchLinks(itemId) });

  return (
    <section className="rounded border border-slate-800 bg-slate-950/40 p-4">
      <h2 className="section-title">Assisted research</h2>
      <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {(links.data?.links ?? []).map((link, index) => {
          const type = link.type ?? (link.url ? "link" : "checklist");
          if (type === "checklist" || !link.url) {
            return (
              <div key={`${link.label}-${index}`} className="rounded border border-slate-800 bg-slate-900 p-3">
                <div className="flex items-start gap-2">
                  <CheckSquare className="mt-0.5 h-4 w-4 shrink-0 text-cyan-200" aria-hidden="true" />
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-100">{link.label}</p>
                    {link.note ? <p className="mt-1 text-xs text-slate-400">{link.note}</p> : null}
                    {link.source ? <SourceTag source={link.source} /> : null}
                  </div>
                </div>
              </div>
            );
          }
          return (
            <a key={`${link.label}-${index}`} className="btn-secondary min-h-14 justify-start gap-2" href={link.url} target="_blank" rel="noreferrer">
              <ExternalLink className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span className="min-w-0 text-left">
                <span className="block truncate">{link.label}</span>
                {link.source ? <span className="block text-xs font-normal text-slate-500">{link.source}</span> : null}
              </span>
            </a>
          );
        })}
        {links.isLoading ? <span className="text-sm text-slate-400">Loading links</span> : null}
      </div>
    </section>
  );
}

function SourceTag({ source }: { source: string }) {
  return (
    <span className="mt-2 inline-flex rounded border border-slate-700 px-2 py-0.5 text-xs font-medium text-slate-400">
      {source}
    </span>
  );
}
