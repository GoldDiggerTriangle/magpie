import { useEffect, useRef, useState } from "react";
import { updateListingDraft } from "../api/listing";
import type { ListingDraft, ListingDraftPayload } from "../types";

export function useDraftAutosave(initial: ListingDraft, onSaved: () => void, readOnly: boolean) {
  const [local, render] = useState(initial);
  const [state, setState] = useState("Saved locally");
  const current = useRef(initial);
  const saved = useRef(initial);
  const revision = useRef(0);
  const savedRevision = useRef(0);
  const pending = useRef<Promise<ListingDraft> | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const priceChoice = useRef<ListingDraftPayload["price_choice"]>();
  const mounted = useRef(true);

  function setLocal(next: ListingDraft, choice?: ListingDraftPayload["price_choice"]) {
    if (readOnly) return;
    current.current = next;
    if (choice) priceChoice.current = choice;
    revision.current += 1;
    render(next);
    setState("Unsaved changes");
    clearTimeout(timer.current);
    timer.current = setTimeout(() => { void flush().catch(() => undefined); }, 650);
  }

  async function flush(): Promise<ListingDraft> {
    clearTimeout(timer.current);
    if (pending.current) {
      await pending.current;
      return flush();
    }
    if (savedRevision.current === revision.current || readOnly) return saved.current;
    const sentRevision = revision.current;
    const next = current.current;
    const payload: ListingDraftPayload = {
      editor_save: true, expected_updated_at: saved.current.updated_at,
      title: next.title, subtitle: next.subtitle, description_html: next.description_html,
      listing_format: next.listing_format, price: next.price, currency: next.currency,
      quantity: next.quantity, channel_data: next.channel_data, item_specifics: next.item_specifics,
      photo_ids: next.photo_ids, include_sku_footer: next.include_sku_footer,
      boilerplate: next.boilerplate, est_shipping_note: next.est_shipping_note,
      ...(priceChoice.current ? { price_choice: priceChoice.current } : {})
    };
    setState("Saving locally…");
    const request = updateListingDraft(next.id, payload);
    pending.current = request;
    try {
      const updated = await request;
      saved.current = updated;
      savedRevision.current = sentRevision;
      if (revision.current === sentRevision) {
        current.current = updated;
        priceChoice.current = undefined;
        if (mounted.current) render(updated);
      }
      // A save response may be older than ongoing typing. Never replace newer text.
      if (mounted.current) {
        setState(revision.current === sentRevision ? "Saved locally" : "Unsaved changes");
      }
      onSaved();
      return updated;
    } catch (error) {
      if (mounted.current) setState(error instanceof Error ? `Not saved: ${error.message}` : "Not saved. Retry or reload after copying your edits.");
      throw error;
    } finally {
      pending.current = null;
      if (mounted.current && savedRevision.current === sentRevision && revision.current !== sentRevision) {
        timer.current = setTimeout(() => { void flush().catch(() => undefined); }, 100);
      }
    }
  }

  function acceptExternal(updated: ListingDraft) {
    saved.current = updated;
    // Refreshing metadata must not overwrite edits made while its GETs were running.
    if (revision.current === savedRevision.current) {
      current.current = updated;
      render(updated);
    } else {
      current.current = { ...current.current, updated_at: updated.updated_at,
        channel_data: { ...updated.channel_data, ...current.current.channel_data } };
      render(current.current);
    }
  }

  useEffect(() => {
    if (!pending.current && revision.current === savedRevision.current && initial.updated_at !== saved.current.updated_at) {
      acceptExternal(initial);
    }
  }, [initial.updated_at]);

  useEffect(() => {
    mounted.current = true;
    const warn = (event: BeforeUnloadEvent) => {
      if (revision.current !== savedRevision.current) { event.preventDefault(); event.returnValue = ""; }
    };
    window.addEventListener("beforeunload", warn);
    return () => {
      mounted.current = false;
      clearTimeout(timer.current);
      // Finish an already-requested human edit when leaving this section.
      if (revision.current !== savedRevision.current) void flush().catch(() => undefined);
      window.removeEventListener("beforeunload", warn);
    };
  }, []);
  return { local, setLocal, flush, acceptExternal, state, pendingPriceChoice: priceChoice.current };
}
