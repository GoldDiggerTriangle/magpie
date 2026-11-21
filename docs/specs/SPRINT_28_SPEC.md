# Magpie — Sprint 28 spec (v1.0 LOCKED): Home — quick stats and quick buttons (phone-first)

**Audience:** Codex. **Author:** Claude, with a ChatGPT cross-check (D-143; six corrections adopted). **Status:** LOCKED v1.0 (2026-11-21). Regan asked to “improve home page” and chose **quick statistics and quick buttons** first, with the **charts moved to the Profit page**.
**Decision:** **D-147** (this sprint). It changes Sprint 12’s fixed Home layout and default tile row (history: `docs/history/specs/SPRINT 12 SPEC.pdf`).
**Locks carried forward:** D-126 (legibility), the Sprint 18–22 profit rules (sale-time fee snapshots, all-in direct costs, exclusion counts, small-sample honesty), D-129, the fee engine’s immutable snapshots, Sprint 26/27 phone behaviour (tabs, keyboard-aware nav), §0 rules 10–12.
**Baseline:** `main` @ `791765d` (handoff v5.04). **Out of scope:** the two-row phone bottom nav stays as it is.

---

## 0. Why this sprint

Home is the “Dealer’s ledger”: filter bar, sold-out alert, a customisable KPI row, then a P&L chart, estimate-vs-actual scatter, revenue, margin by category, sell-through/time-to-sale, aging and “What’s worth listing next”. On a phone that is a long chart page, and several charts show empty states while sales are few. Regan wants Home to open on quick statistics and quick buttons.

## 1. Baseline first (no stop)

Before changing anything: 320/390px screenshots of Home and Profit; page heights; taps to reach Add item, find an item, record a sale, eBay orders and the profit figures. Recorded in `SPRINT28_EVIDENCE.md` for the before/after comparison.

## 2. Quick stats (top of Home)

1. **Picker preserved:** keep all 12 existing tile IDs, the 3–5 tile limit and any saved order. **Add two tiles** to both the backend registry and the frontend registry: **Stock on hand** and **eBay listings**. **New defaults apply only when no preference is saved:** Profit this month · Units sold this month · Stock on hand · eBay listings.
2. **Meanings (shown on the tile or its help text):**
   - **This month** uses the existing definition (`backend/apps/dashboard/analytics.py`): the first of the month to today in `Australia/Sydney`, by sale date.
   - **Units sold this month:** a three-unit sale counts as three.
   - **Stock on hand:** saleable units remaining now (Sprint 10 `quantity_remaining`), with known cost basis, plus a count of units with unknown cost.
   - **eBay listings:** labelled “Marked active in Magpie”: local records (`backend/apps/ebay/hub.py`), not live eBay confirmation.
3. **Profit this month matches the Profit ledger** (`backend/apps/profit/ledger.py`), including scrap losses; a month with no sales can still show a loss. Preserve sale-time fees, all-in costs and exclusion counts. Distinguish **“No sales this month”**, **“Profit unknown”** (e.g. cost-unknown sales) and a genuine **$0.00**. **Show cents:** today a $0.34 profit renders as `$0`; fix it.
4. **Tiles link to matching figures:** a monthly tile opens the Profit page filtered to this month, never silently to an all-time total.
5. Large two-column tiles on phone; D-126 sizes; 44px targets.

## 3. Quick buttons

**Add item · Find an item · eBay hub · Buy calculator · Record a sale · eBay orders.** Each lands on the task, not just a page: **Record a sale opens item selection, then that item’s Sales form** (`/sales` is history, not the task). Quick buttons render and work **even if the stats fail to load**.

## 4. Urgent-alert strip (kept on Home)

A compact strip, each entry opening its queue: pending eBay order lines to resolve; `publishing`/`publish_unknown` drafts that are overdue or unknown; **genuine** allocation problems (an intentionally smaller or unrecorded allocation is **not** an alert, per Sprint 25 Phase 8); sold-out items that still have an active listing to take down. Hidden when nothing needs attention.

## 5. Charts move to Profit

1. All chart sections, “What’s worth listing next”, and the **chart filters (dates, category, channel, unknown-cost)** move to the Profit page under **“Charts & trends”**, **separate from the accountant export’s filters**.
2. Preserve the phone estimate-vs-actual table and the small-sample warnings.
3. **“What to list next” stays one tap from Home** (a quick link or button).
4. Nothing is deleted. Old links and anchors to Home sections redirect to their new places; `/dashboard` keeps working.
5. **Opening Home does not fetch chart data;** charts load on the Profit page.

## 6. Tests and measurement

- Backend: the two new tiles (definitions, unknown-cost counts, timezone month boundaries, multi-unit sales); profit-this-month equals the ledger for the same window, including a scrap loss with no sales; cents preserved; defaults apply only with no saved preference; an existing saved preference is untouched.
- Frontend: tiles, the three empty/unknown/zero states, quick buttons working while stats fail, the Record a sale flow, alert routing (including “intentional smaller allocation is not an alert”), moved sections reachable, old anchors redirected, no chart requests from Home.
- Phone: 320/390px with normal and larger text; Back behaviour; 44px targets; Sprint 27 keyboard behaviour intact. **Repeat the baseline:** page height and taps to the tasks in §1.
- Both Validation lanes green. **No migrations expected** (the KPI preference is a JSON field; stop under §0 rule 12 if one appears). No eBay writes.

## 7. Acceptance (closure gate)

All of §2–§6 met; before/after measurements recorded; Administrator restart; Regan’s iPhone check of Home (stats, buttons, alerts, Record a sale) and the Profit page’s Charts & trends; closure note with the final head and Validation run; independent review (D-143) before CLOSED.

## 8. For Codex

Reasoning: High. Baseline → backend tiles and profit parity → Home layout → Profit page move → tests and remeasurement → stop and report for Regan’s iPhone check. Never echo `.env` values or tokens.
