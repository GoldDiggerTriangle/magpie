import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Edit3, Trash2 } from "lucide-react";
import { useState } from "react";

import { createComparable, deleteComparable, listComparables, updateComparable } from "../api/comparables";
import type { Comparable, ComparablePayload, UUID } from "../types";
import { ComparableForm } from "./ComparableForm";
import { ConfirmDialog } from "./ConfirmDialog";
import { EmptyState } from "./EmptyState";

export function ComparableList({ itemId }: { itemId: UUID }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Comparable | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Comparable | null>(null);
  const comparables = useQuery({ queryKey: ["comparables", itemId], queryFn: () => listComparables({ item: itemId }) });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["comparables", itemId] });

  const createMutation = useMutation({
    mutationFn: (payload: ComparablePayload) => createComparable(payload),
    onSuccess: refresh
  });
  const updateMutation = useMutation({
    mutationFn: (payload: ComparablePayload) => updateComparable(editing!.id, payload),
    onSuccess: () => {
      setEditing(null);
      refresh();
    }
  });
  const deleteMutation = useMutation({
    mutationFn: (target: Comparable) => deleteComparable(target.id),
    onSuccess: refresh
  });

  return (
    <section className="rounded border border-slate-800 bg-slate-950/40 p-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="section-title">Comparables</h2>
        {editing ? <button className="btn-secondary" type="button" onClick={() => setEditing(null)}>Cancel edit</button> : null}
      </div>
      <ComparableForm
        itemId={itemId}
        initial={editing}
        submitLabel={editing ? "Update comparable" : "Add comparable"}
        disabled={createMutation.isPending || updateMutation.isPending}
        onSubmit={(payload) => editing ? updateMutation.mutate(payload) : createMutation.mutate(payload)}
      />

      <div className="mt-5 space-y-3">
        {comparables.isLoading ? <EmptyState title="Loading comparables" /> : null}
        {(comparables.data?.results ?? []).map((comp) => (
          <div key={comp.id} className="rounded border border-slate-800 bg-slate-900 p-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-100">{comp.title || comp.source || comp.kind}</p>
                <p className="mt-1 text-xs text-slate-400">{comp.kind} · {comp.price ?? "-"} {comp.currency} · {comp.observed_on ?? "no date"}</p>
                {comp.notes ? <p className="mt-2 text-sm text-slate-300">{comp.notes}</p> : null}
              </div>
              <div className="flex gap-2">
                <button className="icon-button" type="button" title="Edit comparable" onClick={() => setEditing(comp)}>
                  <Edit3 className="h-4 w-4" aria-hidden="true" />
                </button>
                <button className="icon-button-danger" type="button" title="Delete comparable" onClick={() => setDeleteTarget(comp)}>
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      <ConfirmDialog
        open={deleteTarget !== null}
        title="Delete comparable?"
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) {
            deleteMutation.mutate(deleteTarget);
          }
          setDeleteTarget(null);
        }}
      />
    </section>
  );
}

