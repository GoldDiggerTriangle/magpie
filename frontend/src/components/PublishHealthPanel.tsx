import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { getPublishHealth, reconcileListing } from "../api/listingWorkflow";

export function PublishHealthPanel() {
  const client = useQueryClient();
  const health = useQuery({ queryKey: ["publish-health"], queryFn: getPublishHealth });
  const reconcile = useMutation({ mutationFn: (id: string) => reconcileListing(id), onSuccess: () => client.invalidateQueries({ queryKey: ["publish-health"] }) });
  return <section className="min-w-0 space-y-3 border-t border-slate-400 pt-4" aria-label="Publish recovery">
    <h3 className="text-lg font-semibold">Publish recovery</h3>
    {health.error ? <p role="alert">Publish status unavailable. Check your session and reload.</p> : health.isLoading ? <p>Checking local publish status...</p> : health.data?.drafts.length ? health.data.drafts.map((row) => <div key={row.id} className="rounded border-2 border-amber-700 p-4"><strong>{row.sku}: {row.status.replace(/_/g, " ")}</strong><p>{row.message}</p>{row.started_at ? <p>Started: {new Date(row.started_at).toLocaleString()}</p> : null}<button className="btn-secondary mt-3 gap-2" disabled={reconcile.isPending} onClick={() => reconcile.mutate(row.id)} type="button"><RefreshCw size={18} aria-hidden="true" />Reconcile offer</button></div>) : <p>No interrupted publish attempts.</p>}
    {reconcile.error ? <p role="alert">Reconciliation is unconfirmed. Do not publish again.</p> : null}
  </section>;
}
