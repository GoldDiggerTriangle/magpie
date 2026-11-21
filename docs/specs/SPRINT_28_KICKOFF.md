# Sprint 28 kickoff (v1.0): Home — quick stats and quick buttons

**To Codex. Reasoning: High.** The controlling document is `SPRINT_28_SPEC.md` **v1.0 (LOCKED 2026-11-21, D-147)**. Read it in full first.

## What it is
Home stops being a long chart page. It opens on **quick stats** (default: Profit this month · Units sold this month · Stock on hand · eBay listings) and **quick buttons** (Add item · Find an item · eBay hub · Buy calculator · Record a sale · eBay orders), with a compact urgent-alert strip. **All charts move to the Profit page** under “Charts & trends”.

## What it builds on
Sprint 12’s KPI tiles and picker (kept: 12 IDs, 3–5 limit, saved order; two new tiles); `backend/apps/dashboard/analytics.py` (this month, `Australia/Sydney`); `backend/apps/profit/ledger.py` (the profit truth); `backend/apps/ebay/hub.py` (local listing records); Sprint 25 Phase 8 allocation rules; Sprint 26/27 phone behaviour.

## Must not break
- Saved KPI preferences (new defaults only when none is saved).
- Profit honesty: Home profit equals the ledger (scrap losses included); “No sales this month” ≠ “Profit unknown” ≠ $0.00; cents shown (today $0.34 shows as $0).
- “eBay listings” is labelled as Magpie’s own records, not live eBay state.
- Chart filters stay separate from the accountant export; the estimate-vs-actual phone table and small-sample warnings stay.
- Old Home anchors and `/dashboard` keep working. Quick buttons work when stats fail. Home fetches no chart data.

## Guardrails
No migrations expected (§0 rule 12 if one appears). No eBay writes. The two-row bottom nav is out of scope. **Never print token or `.env` values.**

## Closure gate
Spec §7: before/after measurements; both Validation lanes green; restart; Regan’s iPhone check; closure note; independent review.
