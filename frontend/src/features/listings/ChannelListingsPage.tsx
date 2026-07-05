import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, PlusCircle, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { listItems } from "../../api/items";
import { createChannelListing, getChannelListingBoard, markChannelListingEnded, seedEbayChannelListings } from "../../api/listing";
import { AuthRequiredState } from "../../components/AuthRequiredState";
import { EmptyState } from "../../components/EmptyState";
import type { ChannelListingChannel, ChannelListingItemState } from "../../types";

const channels: Array<{ value: ChannelListingChannel; label: string }> = [
  { value: "ebay", label: "eBay" },
  { value: "facebook_marketplace", label: "Facebook Marketplace" },
  { value: "gumtree", label: "Gumtree" },
  { value: "in_person", label: "In person" },
  { value: "other", label: "Other" }
];

export function ChannelListingsPage() {
  const queryClient = useQueryClient();
  const board = useQuery({ queryKey: ["channel-listing-board"], queryFn: getChannelListingBoard });
  const items = useQuery({ queryKey: ["items", "channel-listing-form"], queryFn: () => listItems({}) });
  const [form, setForm] = useState({
    item: "",
    channel: "facebook_marketplace" as ChannelListingChannel,
    listed_at: new Date().toISOString().slice(0, 16),
    url: "",
    note: ""
  });
  const createMutation = useMutation({
    mutationFn: () =>
      createChannelListing({
        ...form,
        listed_at: new Date(form.listed_at).toISOString()
      }),
    onSuccess: () => {
      setForm((current) => ({ ...current, url: "", note: "" }));
      queryClient.invalidateQueries({ queryKey: ["channel-listing-board"] });
    }
  });
  const endMutation = useMutation({
    mutationFn: (id: string) => markChannelListingEnded(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["channel-listing-board"] })
  });
  const seedMutation = useMutation({
    mutationFn: seedEbayChannelListings,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["channel-listing-board"] })
  });

  if (board.error) {
    return (
      <ListingsFrame>
        <AuthRequiredState detail="The listings board needs your Magpie session. Sign in, then return to Listings." />
      </ListingsFrame>
    );
  }

  const activeItems = items.data?.results ?? [];

  return (
    <ListingsFrame>
      <header className="profit-hero">
        <div>
          <p className="ledger-kicker">Listing truth</p>
          <h1 className="ledger-title">Channel listings board</h1>
          <p className="ledger-subtitle">Manual tracking for eBay, Facebook, Gumtree, and other listings. Magpie never ends a marketplace listing for you.</p>
        </div>
        <button className="ledger-button gap-2" disabled={seedMutation.isPending} onClick={() => seedMutation.mutate()} type="button">
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Seed local eBay rows
        </button>
      </header>

      {seedMutation.data ? (
        <p className="small-sample">
          Seed result: {seedMutation.data.seeded} seeded, {seedMutation.data.existing} already present, {seedMutation.data.skipped_ambiguous} ambiguous skipped.
        </p>
      ) : null}

      {board.data?.take_down_checklist.length ? (
        <section className="profit-section take-down-section">
          <div className="profit-section-header">
            <div>
              <p className="ledger-kicker">Manual take-down required</p>
              <h2>Sold-out items still listed</h2>
            </div>
          </div>
          <div className="grid gap-3">
            {board.data.take_down_checklist.map((item) => (
              <TakeDownRow item={item} onEnd={(id) => endMutation.mutate(id)} pending={endMutation.isPending} key={item.item} />
            ))}
          </div>
        </section>
      ) : null}

      {board.data?.partial_quantity.length ? (
        <section className="profit-section">
          <div className="profit-section-header">
            <div>
              <p className="ledger-kicker">Partial quantity</p>
              <h2>Listings still valid</h2>
            </div>
          </div>
          <div className="grid gap-3">
            {board.data.partial_quantity.map((item) => (
              <article className="rounded border border-blue-700 bg-blue-50 p-4 text-blue-950" key={item.item}>
                <Link className="font-semibold" to={`/inventory/${item.item}`}>{item.sku}</Link>
                <p>{item.message}</p>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      <section className="profit-section">
        <div className="profit-section-header">
          <div>
            <p className="ledger-kicker">Manual add</p>
            <h2>Add a channel listing</h2>
          </div>
        </div>
        <form className="listing-form-grid" onSubmit={(event) => { event.preventDefault(); createMutation.mutate(); }}>
          <label className="label">
            <span>Item</span>
            <select className="field" value={form.item} onChange={(event) => setForm({ ...form, item: event.target.value })}>
              <option value="">Choose item</option>
              {activeItems.map((item) => (
                <option key={item.id} value={item.id}>{item.sku} - {item.title || "Untitled"}</option>
              ))}
            </select>
          </label>
          <label className="label">
            <span>Channel</span>
            <select className="field" value={form.channel} onChange={(event) => setForm({ ...form, channel: event.target.value as ChannelListingChannel })}>
              {channels.map((channel) => (
                <option key={channel.value} value={channel.value}>{channel.label}</option>
              ))}
            </select>
          </label>
          <label className="label">
            <span>Listed at</span>
            <input className="field" type="datetime-local" value={form.listed_at} onChange={(event) => setForm({ ...form, listed_at: event.target.value })} />
          </label>
          <label className="label">
            <span>URL</span>
            <input className="field" value={form.url} onChange={(event) => setForm({ ...form, url: event.target.value })} />
          </label>
          <label className="label listing-span-2">
            <span>Note</span>
            <textarea className="field min-h-20" value={form.note} onChange={(event) => setForm({ ...form, note: event.target.value })} />
          </label>
          <button className="btn-primary gap-2" disabled={!form.item || createMutation.isPending} type="submit">
            <PlusCircle className="h-4 w-4" aria-hidden="true" />
            Add listing
          </button>
        </form>
        {createMutation.error ? <p className="intelligence-error">{createMutation.error instanceof Error ? createMutation.error.message : "Could not add listing."}</p> : null}
      </section>

      <section className="profit-section">
        <div className="profit-section-header">
          <div>
            <p className="ledger-kicker">Active board</p>
            <h2>Items with active listings</h2>
          </div>
        </div>
        {board.isLoading ? <div className="ledger-skeleton ledger-table-skeleton" /> : null}
        {board.data?.empty ? <EmptyState title="No active listings" detail="Add a channel listing or seed local eBay publish records." /> : null}
        <div className="listing-board-groups">
          {(board.data?.groups ?? []).map((group) => (
            <article className="listing-board-group" key={group.channel}>
              <header>
                <h3>{group.channel_label}</h3>
                <span>{group.count} active</span>
              </header>
              <div className="grid gap-2">
                {group.listings.map((listing) => (
                  <div className="listing-board-row" key={listing.id}>
                    <div>
                      <Link to={`/inventory/${listing.item}`}>{listing.item_sku}</Link>
                      <strong>{listing.item_title || "Untitled"}</strong>
                      <small>{listing.days_listed} days listed{listing.url ? ` · ${listing.url}` : ""}</small>
                    </div>
                    <button className="btn-secondary gap-2" disabled={endMutation.isPending} onClick={() => endMutation.mutate(listing.id)} type="button">
                      <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                      Mark ended
                    </button>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>
    </ListingsFrame>
  );
}

function ListingsFrame({ children }: { children: ReactNode }) {
  return <div className="profit-page listings-page">{children}</div>;
}

function TakeDownRow({ item, onEnd, pending }: { item: ChannelListingItemState; onEnd: (id: string) => void; pending: boolean }) {
  return (
    <article className="take-down-alert">
      <div>
        <AlertTriangle className="h-5 w-5" aria-hidden="true" />
        <div>
          <h3>{item.message}</h3>
          <p>
            <Link to={`/inventory/${item.item}`}>{item.sku}</Link> is sold out. The checklist clears only when every active external row is ticked ended.
          </p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {item.active_listings.map((listing) => (
          <button className="btn-danger gap-2" disabled={pending} key={listing.id} onClick={() => onEnd(listing.id)} type="button">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            Mark {listing.channel_label} ended
          </button>
        ))}
      </div>
    </article>
  );
}
