import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  MapPin,
  RefreshCw,
  Search,
  ShieldCheck,
  UploadCloud,
  XCircle
} from "lucide-react";
import { useState } from "react";

import {
  createMerchantLocation,
  getEbayCategorySuggestions,
  getEbayStatus,
  getMerchantLocation
} from "../api/ebay";
import {
  getListingAspectCheck,
  getStagedOfferReview,
  publishListingDraft,
  stageListingDraft,
  withdrawListingDraft
} from "../api/listing";
import type {
  EbayCategorySuggestion,
  EbayCategorySuggestionsResponse,
  InventoryItemDetail,
  ListingDraft,
  MerchantLocationPayload,
  StagedOfferReview
} from "../types";

interface PublishPanelProps {
  draft: ListingDraft;
  item: InventoryItemDetail;
  onDraftChange: (draft: ListingDraft) => void;
  onDraftUpdated: (draft: ListingDraft) => void;
  persistDraft: () => Promise<ListingDraft>;
}

export function PublishPanel({ draft, item, onDraftChange, onDraftUpdated, persistDraft }: PublishPanelProps) {
  const queryClient = useQueryClient();
  const [categorySearch, setCategorySearch] = useState("");
  const [categoryResult, setCategoryResult] = useState<EbayCategorySuggestionsResponse | null>(null);
  const [overrideMissing, setOverrideMissing] = useState(false);
  const [overrideReason, setOverrideReason] = useState("");
  const [showReview, setShowReview] = useState(false);
  const [publishOpen, setPublishOpen] = useState(false);
  const [confirmSku, setConfirmSku] = useState("");
  const [locationForm, setLocationForm] = useState<MerchantLocationPayload>({
    merchant_location_key: "",
    name: "",
    country: "AU",
    postal_code: "",
    city: "",
    state: ""
  });

  const status = useQuery({ queryKey: ["ebay-status"], queryFn: getEbayStatus });
  const merchantLocation = useQuery({ queryKey: ["ebay-merchant-location"], queryFn: getMerchantLocation });
  const aspectCheck = useQuery({
    queryKey: ["listing-aspects", draft.id, channelValue(draft, "category_id")],
    queryFn: () => getListingAspectCheck(draft.id),
    enabled: Boolean(channelValue(draft, "category_id"))
  });
  const stagedReview = useQuery({
    queryKey: ["staged-review", draft.id, channelValue(draft, "offer_id")],
    queryFn: () => getStagedOfferReview(draft.id),
    enabled: showReview && draft.status === "staged" && Boolean(channelValue(draft, "offer_id"))
  });

  const updateChannel = (patch: Record<string, unknown>) => {
    onDraftChange({
      ...draft,
      channel_data: {
        ...draft.channel_data,
        ...patch
      }
    });
  };

  const categoryMutation = useMutation({
    mutationFn: () => getEbayCategorySuggestions(categorySearch),
    onSuccess: setCategoryResult
  });
  const locationMutation = useMutation({
    mutationFn: () => createMerchantLocation(locationForm),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["ebay-merchant-location"] });
      if (data.location) {
        updateChannel({ merchant_location_key: data.location.merchant_location_key });
      }
    }
  });
  const stageMutation = useMutation({
    mutationFn: async () => {
      await persistDraft();
      return stageListingDraft(draft.id, {
        override_missing_aspects: shouldOverride(aspectCheck.data, overrideMissing, overrideReason),
        override_reason: overrideReason.trim()
      });
    },
    onSuccess: (updated) => {
      setShowReview(false);
      setOverrideMissing(false);
      setOverrideReason("");
      onDraftUpdated(updated);
      queryClient.invalidateQueries({ queryKey: ["listing-aspects", draft.id] });
    }
  });
  const withdrawMutation = useMutation({
    mutationFn: () => withdrawListingDraft(draft.id),
    onSuccess: (updated) => {
      setShowReview(false);
      onDraftUpdated(updated);
    }
  });
  const publishMutation = useMutation({
    mutationFn: () => publishListingDraft(draft.id, confirmSku),
    onSuccess: (updated) => {
      setPublishOpen(false);
      setConfirmSku("");
      onDraftUpdated(updated);
    }
  });

  const missingRequired = aspectCheck.data?.missing_required ?? [];
  const aspectCheckBlocked = Boolean(aspectCheck.error);
  const missingBlocked = missingRequired.length > 0 && !shouldOverride(aspectCheck.data, overrideMissing, overrideReason);
  const connected = status.data?.connected ?? false;
  const offerId = channelValue(draft, "offer_id");
  const listingId = channelValue(draft, "listing_id");

  return (
    <section className="space-y-4 rounded border border-slate-800 bg-slate-950/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="section-title">eBay Publish</h3>
          <p className="mt-1 text-xs text-slate-500">Stage, review, then publish through the SKU gate.</p>
        </div>
        <EnvironmentBadge environment={status.data?.environment ?? ""} />
      </div>

      {draft.status === "published" && listingId ? (
        <div className="rounded border border-emerald-300/30 bg-emerald-400/10 p-3 text-sm text-emerald-50">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span>Published listing {listingId}</span>
            <a className="btn-secondary gap-2" href={`https://www.ebay.com.au/itm/${listingId}`} rel="noreferrer" target="_blank">
              <ExternalLink className="h-4 w-4" aria-hidden="true" />
              Open listing
            </a>
          </div>
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)]">
        <div className="space-y-4">
          <CategoryPicker
            categoryResult={categoryResult}
            draft={draft}
            error={errorText(categoryMutation.error)}
            onCategorySearch={setCategorySearch}
            onSearch={() => categoryMutation.mutate()}
            onSelect={(category) => updateChannel({
              category_id: category.category_id,
              category_tree_id: category.category_tree_id,
              category_name: categoryLabel(category)
            })}
            onUpdateChannel={updateChannel}
            pending={categoryMutation.isPending}
            search={categorySearch}
          />

          <PolicyFields draft={draft} onUpdateChannel={updateChannel} />

          <MerchantLocationForm
            draft={draft}
            error={errorText(locationMutation.error)}
            form={locationForm}
            locationKey={merchantLocation.data?.location?.merchant_location_key ?? ""}
            onCreate={() => locationMutation.mutate()}
            onFormChange={setLocationForm}
            onUpdateChannel={updateChannel}
            pending={locationMutation.isPending}
          />
        </div>

        <div className="space-y-4">
          <AspectsChecklist
            error={errorText(aspectCheck.error)}
            missingRequired={missingRequired}
            onRefresh={() => aspectCheck.refetch()}
            result={aspectCheck.data}
          />

          {missingRequired.length > 0 ? (
            <div className="rounded border border-amber-300/30 bg-amber-300/10 p-3">
              <label className="flex items-start gap-2 text-sm font-medium text-amber-50">
                <input
                  checked={overrideMissing}
                  className="mt-1"
                  onChange={(event) => setOverrideMissing(event.target.checked)}
                  type="checkbox"
                />
                Override and stage anyway
              </label>
              {overrideMissing ? (
                <label className="label mt-3">
                  <span>Override reason</span>
                  <textarea
                    className="field min-h-20"
                    onChange={(event) => setOverrideReason(event.target.value)}
                    value={overrideReason}
                  />
                </label>
              ) : null}
            </div>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <button
              className="btn-primary gap-2"
              disabled={!connected || aspectCheckBlocked || missingBlocked || stageMutation.isPending || draft.status === "published"}
              onClick={() => stageMutation.mutate()}
              type="button"
            >
              <UploadCloud className="h-4 w-4" aria-hidden="true" />
              {offerId ? "Re-stage offer" : "Stage offer"}
            </button>
            <button
              className="btn-secondary gap-2"
              disabled={draft.status !== "staged" || !offerId}
              onClick={() => {
                setShowReview(true);
                stagedReview.refetch();
              }}
              type="button"
            >
              <ShieldCheck className="h-4 w-4" aria-hidden="true" />
              Review & publish
            </button>
          </div>
          {!connected ? <p className="text-sm text-amber-200">Connect eBay before staging.</p> : null}
          {aspectCheckBlocked ? <p className="text-sm text-rose-200">Resolve the category/aspects pre-flight error before staging.</p> : null}
          {errorText(stageMutation.error) ? <p className="text-sm text-rose-200">{errorText(stageMutation.error)}</p> : null}
          {draft.channel_data.last_ebay_error ? <p className="break-words text-sm text-rose-200">{stringValue(draft.channel_data.last_ebay_error)}</p> : null}

          <StagedStateCard
            draft={draft}
            onWithdraw={() => withdrawMutation.mutate()}
            pending={withdrawMutation.isPending}
            withdrawError={errorText(withdrawMutation.error)}
          />
        </div>
      </div>

      {showReview ? (
        <StagedReviewScreen
          error={errorText(stagedReview.error)}
          loading={stagedReview.isLoading}
          onOpenPublish={() => setPublishOpen(true)}
          review={stagedReview.data}
        />
      ) : null}

      <PublishConfirmDialog
        confirmSku={confirmSku}
        error={errorText(publishMutation.error)}
        itemSku={item.sku}
        onCancel={() => setPublishOpen(false)}
        onChange={setConfirmSku}
        onPublish={() => publishMutation.mutate()}
        open={publishOpen}
        pending={publishMutation.isPending}
      />
    </section>
  );
}

function CategoryPicker({
  categoryResult,
  draft,
  error,
  onCategorySearch,
  onSearch,
  onSelect,
  onUpdateChannel,
  pending,
  search
}: {
  categoryResult: EbayCategorySuggestionsResponse | null;
  draft: ListingDraft;
  error: string;
  onCategorySearch: (value: string) => void;
  onSearch: () => void;
  onSelect: (category: EbayCategorySuggestion) => void;
  onUpdateChannel: (patch: Record<string, unknown>) => void;
  pending: boolean;
  search: string;
}) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2">
        <label className="label min-w-56 flex-1">
          <span>Category search</span>
          <input className="field" onChange={(event) => onCategorySearch(event.target.value)} value={search} />
        </label>
        <button className="btn-secondary gap-2" disabled={!search || pending} onClick={onSearch} type="button">
          <Search className="h-4 w-4" aria-hidden="true" />
          Search
        </button>
      </div>
      {categoryResult?.supported === false ? <p className="text-sm text-amber-200">{categoryResult.detail}</p> : null}
      {categoryResult?.suggestions.length ? (
        <div className="space-y-2">
          {categoryResult.suggestions.map((category) => (
            <button
              className="row-link w-full items-start"
              disabled={category.is_leaf !== true}
              key={category.category_id}
              onClick={() => onSelect(category)}
              type="button"
            >
              <span className="min-w-0">
                <span className="block font-medium text-slate-100">{categoryLabel(category)}</span>
                <span className="mt-1 block text-xs text-slate-500">{categoryPath(category)}</span>
              </span>
              <span className="flex shrink-0 flex-col items-end gap-1 text-xs">
                <span className="text-slate-400">ID {category.category_id}</span>
                <span className={category.is_leaf === true ? "text-emerald-200" : category.is_leaf === false ? "text-rose-200" : "text-amber-200"}>
                  {leafLabel(category)}
                </span>
              </span>
            </button>
          ))}
        </div>
      ) : null}
      {error ? <p className="text-sm text-rose-200">{error}</p> : null}
      <div className="grid gap-3 md:grid-cols-4">
        <label className="label">
          <span>Manual category ID</span>
          <input className="field" value={channelValue(draft, "category_id")} onChange={(event) => onUpdateChannel({ category_id: event.target.value })} />
        </label>
        <label className="label">
          <span>Tree ID</span>
          <input className="field" value={channelValue(draft, "category_tree_id")} onChange={(event) => onUpdateChannel({ category_tree_id: event.target.value })} />
        </label>
        <label className="label">
          <span>Category name</span>
          <input className="field" value={channelValue(draft, "category_name")} onChange={(event) => onUpdateChannel({ category_name: event.target.value })} />
        </label>
        <label className="label">
          <span>Condition ID</span>
          <input className="field" value={channelValue(draft, "condition_id")} onChange={(event) => onUpdateChannel({ condition_id: event.target.value })} />
        </label>
      </div>
    </div>
  );
}

function PolicyFields({ draft, onUpdateChannel }: { draft: ListingDraft; onUpdateChannel: (patch: Record<string, unknown>) => void }) {
  return (
    <div className="grid gap-3 md:grid-cols-3">
      <label className="label">
        <span>Payment policy ID</span>
        <input className="field" value={channelValue(draft, "payment_policy_id")} onChange={(event) => onUpdateChannel({ payment_policy_id: event.target.value })} />
      </label>
      <label className="label">
        <span>Fulfillment policy ID</span>
        <input className="field" value={channelValue(draft, "fulfillment_policy_id")} onChange={(event) => onUpdateChannel({ fulfillment_policy_id: event.target.value })} />
      </label>
      <label className="label">
        <span>Return policy ID</span>
        <input className="field" value={channelValue(draft, "return_policy_id")} onChange={(event) => onUpdateChannel({ return_policy_id: event.target.value })} />
      </label>
    </div>
  );
}

function MerchantLocationForm({
  draft,
  error,
  form,
  locationKey,
  onCreate,
  onFormChange,
  onUpdateChannel,
  pending
}: {
  draft: ListingDraft;
  error: string;
  form: MerchantLocationPayload;
  locationKey: string;
  onCreate: () => void;
  onFormChange: (form: MerchantLocationPayload) => void;
  onUpdateChannel: (patch: Record<string, unknown>) => void;
  pending: boolean;
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <MapPin className="h-4 w-4 text-cyan-200" aria-hidden="true" />
        <h4 className="text-sm font-semibold text-slate-200">Merchant location</h4>
      </div>
      {locationKey ? (
        <button className="btn-secondary w-fit gap-2" onClick={() => onUpdateChannel({ merchant_location_key: locationKey })} type="button">
          <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
          Use {locationKey}
        </button>
      ) : null}
      <div className="grid gap-3 md:grid-cols-3">
        <label className="label">
          <span>Draft location key</span>
          <input className="field" value={channelValue(draft, "merchant_location_key")} onChange={(event) => onUpdateChannel({ merchant_location_key: event.target.value })} />
        </label>
        <label className="label">
          <span>Create key</span>
          <input className="field" value={form.merchant_location_key} onChange={(event) => onFormChange({ ...form, merchant_location_key: event.target.value })} />
        </label>
        <label className="label">
          <span>Name</span>
          <input className="field" value={form.name} onChange={(event) => onFormChange({ ...form, name: event.target.value })} />
        </label>
        <label className="label">
          <span>Country</span>
          <input className="field" maxLength={2} value={form.country} onChange={(event) => onFormChange({ ...form, country: event.target.value.toUpperCase() })} />
        </label>
        <label className="label">
          <span>Postal code</span>
          <input className="field" value={form.postal_code ?? ""} onChange={(event) => onFormChange({ ...form, postal_code: event.target.value })} />
        </label>
        <label className="label">
          <span>City</span>
          <input className="field" value={form.city ?? ""} onChange={(event) => onFormChange({ ...form, city: event.target.value })} />
        </label>
      </div>
      <button className="btn-secondary gap-2" disabled={!form.merchant_location_key || !form.name || pending} onClick={onCreate} type="button">
        <MapPin className="h-4 w-4" aria-hidden="true" />
        Create location
      </button>
      {error ? <p className="text-sm text-rose-200">{error}</p> : null}
    </div>
  );
}

function AspectsChecklist({
  error,
  missingRequired,
  onRefresh,
  result
}: {
  error: string;
  missingRequired: string[];
  onRefresh: () => void;
  result?: {
    satisfied_required: string[];
    optional_known: string[];
    unmapped_specifics: string[];
    fetched_at: string | null;
  };
}) {
  return (
    <div className="rounded border border-slate-800 bg-slate-900 p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h4 className="text-sm font-semibold text-slate-200">Aspects pre-flight</h4>
        <button className="btn-secondary gap-2" onClick={onRefresh} type="button">
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Refresh
        </button>
      </div>
      <div className="mt-3 grid gap-2 text-sm">
        <AspectRow icon={missingRequired.length ? "bad" : "good"} label="Missing required" values={missingRequired} />
        <AspectRow icon="good" label="Satisfied required" values={result?.satisfied_required ?? []} />
        <AspectRow icon="neutral" label="Optional known" values={result?.optional_known ?? []} />
        <AspectRow icon="neutral" label="Unmapped specifics" values={result?.unmapped_specifics ?? []} />
      </div>
      <p className="mt-2 text-xs text-slate-500">Fetched {formatDate(result?.fetched_at)}</p>
      {error ? <p className="mt-2 text-sm text-rose-200">{error}</p> : null}
    </div>
  );
}

function AspectRow({ icon, label, values }: { icon: "good" | "bad" | "neutral"; label: string; values: string[] }) {
  const Icon = icon === "good" ? CheckCircle2 : icon === "bad" ? XCircle : AlertTriangle;
  const tone = icon === "good" ? "text-emerald-200" : icon === "bad" ? "text-rose-200" : "text-amber-200";
  return (
    <div className="flex gap-2">
      <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${tone}`} aria-hidden="true" />
      <div>
        <p className="font-medium text-slate-200">{label}</p>
        <p className="text-slate-400">{values.length ? values.join(", ") : "None"}</p>
      </div>
    </div>
  );
}

function StagedStateCard({
  draft,
  onWithdraw,
  pending,
  withdrawError
}: {
  draft: ListingDraft;
  onWithdraw: () => void;
  pending: boolean;
  withdrawError: string;
}) {
  const offerId = channelValue(draft, "offer_id");
  if (!offerId) {
    return null;
  }
  return (
    <div className="rounded border border-cyan-300/30 bg-cyan-300/10 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-cyan-50">Unpublished offer {offerId}</p>
          <p className="mt-1 text-xs text-cyan-100/80">Staged {formatDate(channelValue(draft, "staged_at"))}</p>
        </div>
        <button className="btn-secondary" disabled={pending || draft.status === "published"} onClick={onWithdraw} type="button">
          Withdraw
        </button>
      </div>
      {withdrawError ? <p className="mt-2 text-sm text-rose-200">{withdrawError}</p> : null}
    </div>
  );
}

function StagedReviewScreen({ error, loading, onOpenPublish, review }: { error: string; loading: boolean; onOpenPublish: () => void; review?: StagedOfferReview }) {
  return (
    <div className="rounded border border-amber-300/40 bg-amber-300/10 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-amber-200" aria-hidden="true" />
          <h4 className="section-title">This will create a live eBay listing</h4>
        </div>
        <button className="btn-danger gap-2" disabled={!review} onClick={onOpenPublish} type="button">
          <ShieldCheck className="h-4 w-4" aria-hidden="true" />
          Publish
        </button>
      </div>
      {loading ? <p className="mt-3 text-sm text-amber-100">Loading eBay offer...</p> : null}
      {error ? <p className="mt-3 text-sm text-rose-200">{error}</p> : null}
      {review ? (
        <dl className="mt-4 grid gap-2 text-sm md:grid-cols-2 xl:grid-cols-4">
          <ReviewRow label="Offer" value={review.offer_id} />
          <ReviewRow label="SKU" value={review.sku} />
          <ReviewRow label="Title" value={review.title} />
          <ReviewRow label="Category" value={`${review.category_name || "-"} (${review.category_id || "-"})`} />
          <ReviewRow label="Condition" value={review.condition} />
          <ReviewRow label="Price" value={`${review.currency} ${review.price}`} />
          <ReviewRow label="Quantity" value={String(review.quantity)} />
          <ReviewRow label="Format" value={review.format} />
          <ReviewRow label="Payment" value={review.payment_policy_id} />
          <ReviewRow label="Fulfillment" value={review.fulfillment_policy_id} />
          <ReviewRow label="Return" value={review.return_policy_id} />
          <ReviewRow label="Location" value={review.merchant_location_key} />
          <ReviewRow label="Photos" value={String(review.photo_count)} />
          <ReviewRow label="Aspect warnings" value={review.aspect_warnings.length ? review.aspect_warnings.join(", ") : "None"} />
        </dl>
      ) : null}
    </div>
  );
}

function ReviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-slate-800 bg-slate-950/60 p-2">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-1 break-words text-slate-100">{value || "-"}</dd>
    </div>
  );
}

function PublishConfirmDialog({
  confirmSku,
  error,
  itemSku,
  onCancel,
  onChange,
  onPublish,
  open,
  pending
}: {
  confirmSku: string;
  error: string;
  itemSku: string;
  onCancel: () => void;
  onChange: (value: string) => void;
  onPublish: () => void;
  open: boolean;
  pending: boolean;
}) {
  if (!open) {
    return null;
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4">
      <div className="w-full max-w-md rounded border border-amber-300/40 bg-slate-900 p-5 shadow-xl">
        <div className="flex items-center gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-200" aria-hidden="true" />
          <h2 className="text-base font-semibold text-slate-100">Publish live eBay listing</h2>
        </div>
        <p className="mt-3 text-sm text-slate-300">Type the SKU exactly: <span className="font-semibold text-slate-50">{itemSku}</span></p>
        <input
          aria-label="SKU confirmation"
          className="field mt-3"
          onChange={(event) => onChange(event.target.value)}
          value={confirmSku}
        />
        {error ? <p className="mt-2 text-sm text-rose-200">{error}</p> : null}
        <div className="mt-5 flex justify-end gap-2">
          <button className="btn-secondary" onClick={onCancel} type="button">Cancel</button>
          <button className="btn-danger" disabled={confirmSku !== itemSku || pending} onClick={onPublish} type="button">
            Publish
          </button>
        </div>
      </div>
    </div>
  );
}

function EnvironmentBadge({ environment }: { environment: string }) {
  const value = environment ? environment.toUpperCase() : "NOT CONFIGURED";
  const classes = environment === "production"
    ? "border-rose-300/50 bg-rose-400/10 text-rose-100"
    : environment === "sandbox"
      ? "border-amber-300/50 bg-amber-300/10 text-amber-100"
      : "border-slate-700 bg-slate-900 text-slate-300";
  return <span className={`rounded border px-2 py-1 text-xs font-semibold ${classes}`}>{value}</span>;
}

function shouldOverride(result: { missing_required: string[] } | undefined, checked: boolean, reason: string) {
  return Boolean(result?.missing_required.length && checked && reason.trim());
}

function categoryLabel(category: EbayCategorySuggestion) {
  return category.category_name || category.name || "-";
}

function categoryPath(category: EbayCategorySuggestion) {
  const path = category.category_path?.filter(Boolean) ?? [];
  return path.length ? path.join(" > ") : categoryLabel(category);
}

function leafLabel(category: EbayCategorySuggestion) {
  if (category.validation_error) {
    return "Validation unavailable";
  }
  if (category.is_leaf === true) {
    return "Leaf category";
  }
  if (category.is_leaf === false) {
    return "Not a leaf";
  }
  return "Leaf unknown";
}

function channelValue(draft: ListingDraft, key: string) {
  return stringValue(draft.channel_data?.[key]);
}

function stringValue(value: unknown) {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return "";
}

function formatDate(value?: string | null) {
  if (!value) {
    return "-";
  }
  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

function errorText(error: unknown) {
  if (!error) {
    return "";
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Request failed.";
}
