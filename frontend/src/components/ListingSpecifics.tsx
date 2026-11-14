import type { ListingSpecific, FieldSpec } from "../types";
import { SuggestedTextField } from "./SchemaFieldsForm";

type Aspect = { name: string; required: boolean; values: string[] };
export function ListingSpecifics({ aspects, rows, onChange, customRows }: {
  aspects: Aspect[]; rows: ListingSpecific[]; onChange: (rows: ListingSpecific[]) => void; customRows: React.ReactNode;
}) {
  function control(aspect: Aspect) {
    const label = `${aspect.name} (${aspect.required ? "required by eBay" : "recommended, not a blocker"})`;
    const value = rows.find((row) => row.name.toLowerCase() === aspect.name.toLowerCase())?.value ?? "";
    const change = (next: unknown) => onChange([...rows.filter((row) => row.name.toLowerCase() !== aspect.name.toLowerCase()), { name: aspect.name, value: String(next ?? "") }]);
    return <div className="mb-3" key={aspect.name}>{aspect.values?.length ? <SuggestedTextField field={{ name: aspect.name, label, type: "str", required: false, choices: [], suggestions: aspect.values, min: null, max: null, help_text: "" } satisfies FieldSpec} value={value} onChange={change} /> : <label className="label"><span>{label}</span><input className="field" aria-label={label} value={value} onChange={(event) => change(event.target.value)} /></label>}</div>;
  }
  const recommended = aspects.filter((aspect) => !aspect.required);
  return <div><h3 className="section-title mb-3">Item specifics</h3>
    {aspects.filter((aspect) => aspect.required).map(control)}
    <details><summary className="listing-section-toggle">Recommended ({recommended.length})</summary>{recommended.map(control)}</details>
    <details className="mt-3"><summary className="listing-section-toggle">Additional / custom specifics</summary>{customRows}</details>
  </div>;
}
