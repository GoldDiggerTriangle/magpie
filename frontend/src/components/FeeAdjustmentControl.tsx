import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { adjustSaleFee } from "../api/feeEngine";

export function FeeAdjustmentControl({ saleId }: { saleId: string }) {
  const cache = useQueryClient(); const [amount, setAmount] = useState(""); const [reason, setReason] = useState("");
  const save = useMutation({ mutationFn: () => adjustSaleFee(saleId, { amount, reason, provenance: "human_correction" }),
    onSuccess: () => { setAmount(""); setReason(""); cache.invalidateQueries({ queryKey: ["profit-ledger"] }); cache.invalidateQueries({ queryKey: ["sales"] }); cache.invalidateQueries({ queryKey: ["item-sales"] }); cache.invalidateQueries({ predicate: (q) => String(q.queryKey[0]).startsWith("analytics-") }); } });
  return <details className="mt-3"><summary>Record fee adjustment</summary><form className="mt-3 grid gap-3" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
    <label className="label">Signed fee change<input required className="field" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} /></label>
    <label className="label">Reason / evidence source<textarea required className="field" value={reason} onChange={(e) => setReason(e.target.value)} /></label>
    <p>Original snapshot is retained. Positive adds a fee; negative records a credit.</p>
    <button className="btn-secondary" type="submit" disabled={save.isPending}>Confirm audited adjustment</button>
    {save.error ? <p role="alert">{save.error.message}</p> : null}{save.isSuccess ? <p role="status">Adjustment recorded</p> : null}
  </form></details>;
}
