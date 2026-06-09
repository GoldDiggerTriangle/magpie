import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Edit3, Trash2 } from "lucide-react";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";

import { createResearchRecord, deleteResearchRecord, listResearchRecords, updateResearchRecord } from "../api/research";
import type { ResearchRecord, ResearchRecordPayload, UUID } from "../types";
import { ConfirmDialog } from "./ConfirmDialog";

export function ResearchLog({ itemId }: { itemId: UUID }) {
  const queryClient = useQueryClient();
  const records = useQuery({ queryKey: ["research-records", itemId], queryFn: () => listResearchRecords({ item: itemId }) });
  const [editing, setEditing] = useState<ResearchRecord | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ResearchRecord | null>(null);
  const [source, setSource] = useState("");
  const [content, setContent] = useState("");
  const [linkLabel, setLinkLabel] = useState("");
  const [linkUrl, setLinkUrl] = useState("");
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["research-records", itemId] });

  useEffect(() => {
    if (!editing) {
      setSource("");
      setContent("");
      setLinkLabel("");
      setLinkUrl("");
      return;
    }
    setSource(editing.source);
    setContent(editing.content);
    setLinkLabel(editing.links[0]?.label ?? "");
    setLinkUrl(editing.links[0]?.url ?? "");
  }, [editing]);

  const createMutation = useMutation({
    mutationFn: (payload: ResearchRecordPayload) => createResearchRecord(payload),
    onSuccess: refresh
  });
  const updateMutation = useMutation({
    mutationFn: (payload: ResearchRecordPayload) => updateResearchRecord(editing!.id, payload),
    onSuccess: () => {
      setEditing(null);
      refresh();
    }
  });
  const deleteMutation = useMutation({
    mutationFn: (target: ResearchRecord) => deleteResearchRecord(target.id),
    onSuccess: refresh
  });

  function payload(): ResearchRecordPayload {
    return {
      item: itemId,
      source,
      content,
      links: linkLabel && linkUrl ? [{ label: linkLabel, url: linkUrl }] : []
    };
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (editing) {
      updateMutation.mutate(payload());
    } else {
      createMutation.mutate(payload());
      setSource("");
      setContent("");
      setLinkLabel("");
      setLinkUrl("");
    }
  }

  return (
    <section className="rounded border border-slate-800 bg-slate-950/40 p-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="section-title">Research log</h2>
        {editing ? <button className="btn-secondary" type="button" onClick={() => setEditing(null)}>Cancel edit</button> : null}
      </div>
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={handleSubmit}>
        <label className="label">
          <span>Source</span>
          <input className="field" value={source} onChange={(event) => setSource(event.target.value)} />
        </label>
        <label className="label">
          <span>Link label</span>
          <input className="field" value={linkLabel} onChange={(event) => setLinkLabel(event.target.value)} />
        </label>
        <label className="label sm:col-span-2">
          <span>Link URL</span>
          <input className="field" value={linkUrl} onChange={(event) => setLinkUrl(event.target.value)} />
        </label>
        <label className="label sm:col-span-2">
          <span>Note</span>
          <textarea className="field min-h-24" value={content} onChange={(event) => setContent(event.target.value)} />
        </label>
        <button className="btn-primary sm:col-span-2 sm:w-fit" disabled={createMutation.isPending || updateMutation.isPending} type="submit">
          {editing ? "Update note" : "Add note"}
        </button>
      </form>

      <div className="mt-5 space-y-3">
        {(records.data?.results ?? []).map((record) => (
          <div key={record.id} className="rounded border border-slate-800 bg-slate-900 p-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-100">{record.source || "Research note"}</p>
                <p className="mt-2 whitespace-pre-wrap text-sm text-slate-300">{record.content}</p>
                {record.links.map((link) => <a key={link.url} className="mt-2 block text-sm text-cyan-200" href={link.url} target="_blank" rel="noreferrer">{link.label}</a>)}
              </div>
              <div className="flex gap-2">
                <button className="icon-button" type="button" title="Edit research note" onClick={() => setEditing(record)}>
                  <Edit3 className="h-4 w-4" aria-hidden="true" />
                </button>
                <button className="icon-button-danger" type="button" title="Delete research note" onClick={() => setDeleteTarget(record)}>
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      <ConfirmDialog
        open={deleteTarget !== null}
        title="Delete research note?"
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

