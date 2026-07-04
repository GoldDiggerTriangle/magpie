import { useQuery } from "@tanstack/react-query";
import { Calculator, CircleAlert, Gauge, ReceiptText } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { listItems } from "../../api/items";
import { getBuyCalculatorEvidence } from "../../api/profit";
import { EmptyState } from "../../components/EmptyState";
import type { BuyCalculationPayload, BuyEvidenceOption, PriceBasis, RoiBasis, SellerMode, UUID } from "../../types";
import { calculateLocalBuy } from "./localCalculator";

const sellerModeOptions: Array<[SellerMode, string]> = [
  ["free_selling", "eBay AU free selling"],
  ["pro_starter", "eBay AU Pro Starter"],
  ["pro_other", "eBay AU Pro other"],
  ["legacy_manual", "Manual / other"]
];

const roiBasisOptions: Array<[RoiBasis, string]> = [
  ["all_in_cash", "All-in cash ROI"],
  ["buy_price", "On-buy-price ROI"]
];

export function BuyCalculator() {
  const items = useQuery({ queryKey: ["items", "buy-calculator"], queryFn: () => listItems({ page: 1 }) });
  const [itemId, setItemId] = useState<UUID>("");
  const evidence = useQuery({
    queryKey: ["buy-calculator-evidence", itemId],
    queryFn: () => getBuyCalculatorEvidence(itemId || undefined)
  });

  const [expectedSellPrice, setExpectedSellPrice] = useState("");
  const [priceBasis, setPriceBasis] = useState<PriceBasis>("seller_receives");
  const [sellerMode, setSellerMode] = useState<SellerMode>("free_selling");
  const [targetType, setTargetType] = useState<"roi" | "flat">("roi");
  const [flatProfitTarget, setFlatProfitTarget] = useState("25.00");
  const [roiPct, setRoiPct] = useState("30.00");
  const [roiBasis, setRoiBasis] = useState<RoiBasis>("all_in_cash");
  const [postage, setPostage] = useState("0.00");
  const [packaging, setPackaging] = useState("0.00");
  const [refurb, setRefurb] = useState("0.00");
  const [askingPrice, setAskingPrice] = useState("");
  const [auctionMode, setAuctionMode] = useState(false);
  const [source, setSource] = useState<BuyEvidenceOption["source"]>("what_if");
  const [confidence, setConfidence] = useState("what-if (your estimate)");

  useEffect(() => {
    const settings = evidence.data?.settings;
    if (!settings) return;
    setSellerMode(settings.seller_mode);
    setFlatProfitTarget(settings.default_flat_profit_target);
    setRoiPct(settings.default_roi_pct);
    setRoiBasis(settings.default_roi_basis);
  }, [evidence.data?.settings]);

  useEffect(() => {
    const suggested = evidence.data?.suggested;
    if (!suggested) return;
    setExpectedSellPrice(suggested.price);
    setPriceBasis(suggested.price_basis);
    setSource(suggested.source);
    setConfidence(suggested.confidence_label);
  }, [evidence.data?.suggested]);

  const payload = useMemo<BuyCalculationPayload>(() => ({
    expected_sell_price: expectedSellPrice,
    price_basis: priceBasis,
    seller_mode: sellerMode,
    target_type: targetType,
    flat_profit_target: flatProfitTarget,
    roi_pct: roiPct,
    roi_basis: roiBasis,
    postage,
    packaging,
    refurb,
    asking_price: askingPrice || undefined,
    evidence_source: source,
    confidence_label: confidence,
    auction_mode: auctionMode
  }), [askingPrice, auctionMode, confidence, expectedSellPrice, flatProfitTarget, packaging, postage, priceBasis, refurb, roiBasis, roiPct, sellerMode, source, targetType]);

  const calculation = useMemo(() => {
    if (!expectedSellPrice || priceBasis === "unknown") {
      return { result: null, error: "" };
    }
    try {
      return { result: calculateLocalBuy(payload, evidence.data?.settings), error: "" };
    } catch (error) {
      return { result: null, error: errorText(error) };
    }
  }, [evidence.data?.settings, expectedSellPrice, payload, priceBasis]);

  function useEvidence(option: BuyEvidenceOption) {
    if (!option.seller_receives || option.basis_uncertain) {
      return;
    }
    setExpectedSellPrice(option.seller_receives);
    setPriceBasis("seller_receives");
    setSource(option.source);
    setConfidence(option.confidence_label);
  }

  function markWhatIf(value: string) {
    setExpectedSellPrice(value);
    setSource("what_if");
    setConfidence("what-if (your estimate)");
  }

  const result = calculation.result;
  const cannotCalculate = !expectedSellPrice || priceBasis === "unknown";
  const authLookupFailed = evidence.error || items.error;

  return (
    <div className="buy-calculator-page">
      <header className="buy-calculator-header">
        <div>
          <p className="ledger-kicker">Profit engine</p>
          <h1 className="ledger-title">Max Buy / Max Bid</h1>
          <p className="ledger-subtitle">
            Local calculator only. Uses your own sales and approved comps, or a clearly labelled what-if estimate. What-if values are never saved as evidence.
          </p>
        </div>
        <Calculator className="h-8 w-8 text-[#1d4ed8]" aria-hidden="true" />
      </header>

      <main className="buy-calculator-grid">
        <section className="buy-card buy-card-inputs">
          <div className="buy-card-title">
            <ReceiptText className="h-5 w-5" aria-hidden="true" />
            <h2>Evidence and assumptions</h2>
          </div>
          <div className="buy-form-grid">
            <label className="label buy-span-2">
              <span>Evidence item</span>
              <select className="field" value={itemId} onChange={(event) => setItemId(event.target.value)}>
                <option value="">No item selected</option>
                {(items.data?.results ?? []).map((item) => (
                  <option key={item.id} value={item.id}>{item.sku} - {item.title}</option>
                ))}
              </select>
            </label>
            <label className="label">
              <span>{auctionMode ? "Expected hammer / sell price" : "Expected sell price"}</span>
              <input className="field" inputMode="decimal" value={expectedSellPrice} onChange={(event) => markWhatIf(event.target.value)} />
            </label>
            <label className="label">
              <span>Price basis</span>
              <select className="field" value={priceBasis} onChange={(event) => setPriceBasis(event.target.value as PriceBasis)}>
                <option value="seller_receives">Seller receives</option>
                <option value="buyer_visible">Buyer-visible total</option>
                <option value="unknown">Unknown - review only</option>
              </select>
            </label>
            <label className="label">
              <span>Seller mode</span>
              <select className="field" value={sellerMode} onChange={(event) => setSellerMode(event.target.value as SellerMode)}>
                {sellerModeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label className="label">
              <span>Asking price</span>
              <input className="field" inputMode="decimal" value={askingPrice} onChange={(event) => setAskingPrice(event.target.value)} />
            </label>
            <label className="label">
              <span>Postage / label</span>
              <input className="field" inputMode="decimal" value={postage} onChange={(event) => setPostage(event.target.value)} />
            </label>
            <label className="label">
              <span>Packaging</span>
              <input className="field" inputMode="decimal" value={packaging} onChange={(event) => setPackaging(event.target.value)} />
            </label>
            <label className="label">
              <span>Refurb</span>
              <input className="field" inputMode="decimal" value={refurb} onChange={(event) => setRefurb(event.target.value)} />
            </label>
            <label className="label">
              <span>Mode</span>
              <select className="field" value={auctionMode ? "auction" : "buy"} onChange={(event) => setAuctionMode(event.target.value === "auction")}>
                <option value="buy">Max Buy</option>
                <option value="auction">Max Bid</option>
              </select>
            </label>
          </div>

          <div className="buy-target-toggle" role="group" aria-label="Profit target">
            <button className={targetType === "roi" ? "active" : ""} type="button" onClick={() => setTargetType("roi")}>ROI target</button>
            <button className={targetType === "flat" ? "active" : ""} type="button" onClick={() => setTargetType("flat")}>Flat profit</button>
          </div>
          <div className="buy-form-grid">
            {targetType === "roi" ? (
              <>
                <label className="label">
                  <span>Required ROI %</span>
                  <input className="field" inputMode="decimal" value={roiPct} onChange={(event) => setRoiPct(event.target.value)} />
                </label>
                <label className="label">
                  <span>ROI basis</span>
                  <select className="field" value={roiBasis} onChange={(event) => setRoiBasis(event.target.value as RoiBasis)}>
                    {roiBasisOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                </label>
              </>
            ) : (
              <label className="label buy-span-2">
                <span>Required flat profit</span>
                <input className="field" inputMode="decimal" value={flatProfitTarget} onChange={(event) => setFlatProfitTarget(event.target.value)} />
              </label>
            )}
          </div>
          <p className="buy-note">Current source: {confidence}. What-if inputs are calculation-only and are not persisted as valuation or evidence.</p>
        </section>

        <section className={`buy-card buy-result buy-verdict-${(result?.verdict ?? "empty").toLowerCase().replace(/\s+/g, "-")}`}>
          <div className="buy-card-title">
            <Gauge className="h-5 w-5" aria-hidden="true" />
            <h2>{result?.headline ?? (auctionMode ? "Max Bid" : "Max Buy Price")}</h2>
          </div>
          {cannotCalculate ? (
            <EmptyState title="Choose a known-basis sell price" detail="Unknown-basis comps stay visible as evidence, but they are not used for precise max-buy maths." />
          ) : result ? (
            <>
              <strong className="buy-max">${money(result.max_buy)}</strong>
              <span className="buy-verdict">{result.verdict}</span>
              <dl className="buy-result-list">
                <Row label="Expected profit at asking" value={currencyOrDash(result.expected_profit_at_asking)} />
                <Row label="ROI at asking" value={result.roi_at_asking ? `${result.roi_at_asking}%` : "-"} />
                <Row label="Net before buy" value={currencyOrDash(result.net_proceeds_before_buy)} />
                <Row label="Seller fees" value={currencyOrDash(result.seller_fees)} />
                <Row label="Non-buy costs" value={currencyOrDash(result.non_buy_costs)} />
                <Row label="ROI basis" value={result.roi_basis === "all_in_cash" ? "All-in cash" : "On buy price"} />
              </dl>
              <p className="buy-note">{result.confidence_label}</p>
            </>
          ) : (
            <EmptyState title="Enter a sell price" detail="The result updates from local calculator maths only." />
          )}
          {calculation.error ? <p className="buy-error">{calculation.error}</p> : null}
        </section>

        <section className="buy-card buy-evidence">
          <h2>Evidence lookup</h2>
          {authLookupFailed ? (
            <div className="buy-empty">
              <CircleAlert className="h-5 w-5" aria-hidden="true" />
              <p>{errorText(evidence.error ?? items.error)} Sign in through Django admin to use saved evidence; typed what-if calculations still work.</p>
            </div>
          ) : null}
          {evidence.isLoading ? <EmptyState title="Loading evidence" /> : null}
          {evidence.data?.empty ? (
            <div className="buy-empty">
              <CircleAlert className="h-5 w-5" aria-hidden="true" />
              <p>No approved in-Magpie pricing rows yet. Open sold-search links on the item, then capture comps into the pricing grid.</p>
            </div>
          ) : null}
          <div className="buy-evidence-list">
            {(evidence.data?.evidence ?? []).slice(0, 8).map((option) => (
              <button
                className="buy-evidence-row"
                disabled={!option.seller_receives || option.basis_uncertain}
                key={option.id}
                onClick={() => useEvidence(option)}
                type="button"
              >
                <span>
                  <strong>{option.label}</strong>
                  <small>{option.confidence_label} · {option.match_reason || "captured evidence"}</small>
                </span>
                <span>{option.seller_receives ? `$${money(option.seller_receives)}` : "basis uncertain"}</span>
              </button>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function money(value: string) {
  return Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function currencyOrDash(value: string | null) {
  return value ? `$${money(value)}` : "-";
}

function errorText(error: unknown) {
  if (!error) return "";
  return error instanceof Error ? error.message : "Request failed.";
}
