import { useMutation } from "@tanstack/react-query";
import { MapPin } from "lucide-react";
import { useState } from "react";
import { createMerchantLocation } from "../api/ebay";
import type { MerchantLocationPayload } from "../types";

export function MerchantLocationSetup({ onCreated }: { onCreated: () => void }) {
  const [values, setValues] = useState<MerchantLocationPayload>({ merchant_location_key: "", name: "", country: "", city: "", state: "", postal_code: "" });
  const [confirm, setConfirm] = useState(false);
  const create = useMutation({ mutationFn: () => createMerchantLocation(values), onSuccess: () => { setConfirm(false); onCreated(); } });
  return <details className="min-w-0 space-y-3"><summary className="min-h-11 cursor-pointer font-semibold">Create merchant location</summary>
    <p>This uses the existing eBay location-creation action. It does not stage or publish a listing. Choose the returned location in the picker afterwards.</p>
    <div className="grid gap-3 sm:grid-cols-2">
      {([ ["merchant_location_key", "New location key"], ["name", "Location name"], ["country", "Country code"], ["city", "City"], ["state", "State / province"], ["postal_code", "Postcode"] ] as const).map(([key, label]) => <label className="label" key={key}><span>{label}</span><input className="field" value={values[key] || ""} maxLength={key === "country" ? 2 : undefined} onChange={(e) => { setValues({ ...values, [key]: e.target.value }); setConfirm(false); }} /></label>)}
    </div>
    {confirm ? <div role="alertdialog" aria-label="Confirm merchant location creation" className="space-y-3 border border-slate-500 p-3"><p>Create this merchant location on eBay? {values.name} - {values.city}, {values.state} {values.postal_code}, {values.country}. Key: {values.merchant_location_key}.</p><div className="flex flex-wrap gap-3"><button className="btn-secondary" onClick={() => setConfirm(false)} type="button">Cancel</button><button className="btn-primary gap-2" disabled={create.isPending} onClick={() => create.mutate()} type="button"><MapPin size={18} aria-hidden="true" />Confirm create location</button></div></div>
      : <button className="btn-secondary gap-2" disabled={!values.merchant_location_key.trim() || !values.name.trim() || values.country.trim().length !== 2 || create.isPending} onClick={() => setConfirm(true)} type="button"><MapPin size={18} aria-hidden="true" />Review new location</button>}
    {create.error ? <p role="alert">{create.error instanceof Error ? create.error.message : "Location creation was not confirmed."}</p> : null}
    {create.isSuccess ? <p role="status">Location returned. Select it above; it was not applied to the draft.</p> : null}
  </details>;
}
