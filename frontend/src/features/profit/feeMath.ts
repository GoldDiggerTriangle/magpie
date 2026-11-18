import type { FeeCalendar, FeeOrder, FeeResult, PlanPeriod, TierRate } from "../../api/feeEngine";

const HUNDRED = 100n;
function cents(value: string | undefined) {
  const s = value ?? "0";
  if (!/^\d+(\.\d{1,2})?$/.test(s)) throw new Error("Enter amounts to the cent.");
  const [whole, fraction = ""] = s.split(".");
  return BigInt(whole) * HUNDRED + BigInt(fraction.padEnd(2, "0"));
}
function pct(value: string) {
  if (!/^\d+(\.\d{1,6})?$/.test(value)) throw new Error("Enter a valid percentage.");
  const [whole, fraction = ""] = value.split(".");
  const result = BigInt(whole) * 1000000n + BigInt(fraction.padEnd(6, "0"));
  if (result > 100000000n) throw new Error("Percentage must be between zero and 100.");
  return result;
}
function fee(base: bigint, percentage: string) { return (base * pct(percentage) + 50000000n) / 100000000n; }
function money(value: bigint) { return `${value / HUNDRED}.${String(value % HUNDRED).padStart(2, "0")}`; }
function sum(values: bigint[]) { return values.reduce((a, b) => a + b, 0n); }
function allocate(total: bigint, weights: bigint[]) {
  if (!weights.length) throw new Error("An order needs items.");
  if (sum(weights) === 0n) weights = weights.map(() => 1n);
  const denominator = sum(weights);
  const numerators = weights.map((w) => total * w);
  const result = numerators.map((n) => n / denominator);
  const indices = weights.map((_, i) => i).sort((a, b) => {
    const left = numerators[a] % denominator, right = numerators[b] % denominator;
    return left === right ? a - b : left > right ? -1 : 1;
  });
  const residue = Number(total - sum(result));
  for (let i = 0; i < residue; i++) result[indices[i]] += 1n;
  return result;
}

export function calculateOrderLocal(order: FeeOrder & { lines: Array<FeeOrder["lines"][number] & { tier?: string }> }, period: Pick<PlanPeriod, "per_order_fee" | "international_pct">, rates: Record<string, TierRate>): FeeResult {
  const lines = [...order.lines].sort((a, b) => a.key < b.key ? -1 : a.key > b.key ? 1 : 0);
  const units = lines.flatMap((line) => {
    if (!Number.isInteger(line.quantity) || line.quantity < 1 || line.quantity > 10000) throw new Error("Quantity must be a positive integer.");
    return allocate(cents(line.item_total), Array<bigint>(line.quantity).fill(1n)).map((price) => ({ key: line.key, tier: line.tier, price }));
  });
  if (!units.length || units.length > 10000 || new Set(lines.map((l) => l.key)).size !== lines.length) throw new Error("Enter complete, unique order lines.");
  const prices = units.map((u) => u.price), discount = cents(order.seller_discount);
  if (discount > sum(prices)) throw new Error("Seller discount exceeds item total.");
  const discounts = allocate(discount, prices), net = prices.map((p, i) => p - discounts[i]);
  const postage = allocate(cents(order.postage) + cents(order.handling), net);
  const tax = allocate(cents(order.marketplace_tax), net), extras = allocate(cents(order.other_fee_base), net);
  const bases = net.map((p, i) => p + postage[i] + tax[i] + extras[i]);
  const fixed = allocate(cents(period.per_order_fee), bases), promoted = allocate(cents(order.promoted_fee), bases);
  const extra = allocate(sum((order.extra_charges ?? []).map((e) => cents(e.amount))), bases);
  const rows: Record<string, { state: string; revenue: bigint; base: bigint; total: bigint; components: Record<string, bigint> }> = {};
  units.forEach((u, i) => {
    const r = rows[u.key] ??= { state: "calculated", revenue: 0n, base: 0n, total: 0n, components: { final_value_fee: 0n, per_order_fee: 0n, international_fee: 0n, promoted_fee: 0n, extra_charges: 0n } };
    r.revenue += net[i] + postage[i] + extras[i]; r.base += bases[i];
    const rate = u.tier ? rates[u.tier] : undefined;
    if (!rate) { r.state = "fee rate not configured"; return; }
    const threshold = cents(rate.threshold), lower = bases[i] < threshold ? bases[i] : threshold;
    // Round the combined tier calculation once per physical unit, not twice at the breakpoint.
    const fvf = (lower * pct(rate.fvf_pct) + (bases[i] - lower) * pct(rate.above_pct) + 50000000n) / 100000000n;
    const components = { final_value_fee: fvf, per_order_fee: fixed[i], international_fee: order.destination_country !== "AU" ? fee(bases[i], period.international_pct) : 0n, promoted_fee: promoted[i], extra_charges: extra[i] };
    Object.entries(components).forEach(([k, v]) => { r.components[k] += v; r.total += v; });
  });
  const known = Object.values(rows).every((r) => r.state === "calculated");
  return { state: known ? "calculated" : "fee rate not configured", label: "Calculated fees - not evidence of what eBay charged", fee_total: known ? money(sum(Object.values(rows).map((r) => r.total))) : null,
    gst_added: "0.00", lines: Object.fromEntries(Object.entries(rows).map(([k, r]) => [k, { state: r.state, revenue: money(r.revenue), fee_base: money(r.base), fee_total: r.state === "calculated" ? money(r.total) : null, components: Object.fromEntries(Object.entries(r.components).map(([n, v]) => [n, money(v)])) }])) };
}

export function proBasicLocal(order: FeeOrder, calendar: FeeCalendar | undefined): FeeResult {
  if (!calendar?.current) throw new Error("schedule unknown - enter a confirmed Pro Basic period and rates in Settings.");
  const version = calendar?.current;
  const period = version?.periods.find((p) => p.effective_from <= order.sale_date && (!p.effective_to || order.sale_date < p.effective_to));
  if (!period) throw new Error("schedule unknown - enter a confirmed Pro Basic period and rates in Settings.");
  if (period.plan !== "pro_basic") throw new Error("Plan restriction: this period is not Pro Basic. Reconnecting cannot change the plan.");
  const mappings = period.mapping?.categories ?? calendar.categories.categories;
  const conflicts: string[] = [];
  const lines = order.lines.map((line) => {
    const mapping = mappings[line.category_slug];
    const roots = Object.values(mappings).filter((v) => v.tier === mapping?.tier).flatMap((v) => v.roots);
    const ids = [...line.ebay_path ?? [], line.ebay_category_id ?? ""];
    const conflict = mapping && line.ebay_category_id && line.ebay_path?.length && !roots.some((id) => ids.includes(id));
    const unverified = mapping && line.ebay_category_id && !line.ebay_path?.length && !roots.some((id) => ids.includes(id));
    if (conflict) conflicts.push(line.key);
    return { ...line, tier: mapping && !conflict && !unverified ? mapping.tier : undefined };
  });
  const result = calculateOrderLocal({ ...order, lines }, period, Object.fromEntries(period.rates.map((r) => [r.tier, r])));
  return { ...result, category_conflicts: conflicts, version_id: version.id, label: conflicts.length ? "Selected eBay category conflicts with the configured Magpie tier." : result.label };
}
