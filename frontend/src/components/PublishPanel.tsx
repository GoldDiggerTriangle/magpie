import type { InventoryItemDetail, ListingDraft } from "../types";
import { ListingWorkflow } from "./ListingWorkflow";

interface PublishPanelProps {
  localEditor?: boolean; draft: ListingDraft; item: InventoryItemDetail;
  onDraftChange: (draft: ListingDraft) => void;
  onDraftUpdated: (draft: ListingDraft) => void;
  persistDraft: () => Promise<ListingDraft>;
}

export function PublishPanel({ draft, item, onDraftUpdated, persistDraft }: PublishPanelProps) {
  return <ListingWorkflow draft={draft} item={item} mode="full" onUpdated={onDraftUpdated} beforeReview={persistDraft} />;
}
