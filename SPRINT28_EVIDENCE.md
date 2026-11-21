# Sprint 28 Evidence

## 2026-11-21: Contract And Baseline

Baseline main791765d8a1e1141a7249fdb460597f386c3d7f3e, handoff v5.04. Supplied v1.0 spec/kickoff copied byte-for-byte from Downloads; SHA256 e62ff65e6771ff42a458745c796e4be6a8ae99881010c196a983632dbe4bc2c7 /9d5eb496b06b5b300f30da5dbb86bcacdacef98414555a95c0835a4e7253d35c. All8 handoff Find blocks matched once; v5.05 applied verbatim before application changes. Source documents checked for known credentials/patterns without revealing values.

Baseline uses real Home/Profit/AppShell/item/Orders components against fixed synthetic owned records, no live API/media proxy. Fresh context/route for each task,320/390x844, normal16px and larger20px root text. Screenshots are full-document Chromium, not iPhone captures; copied unchanged/hash-verified to docs/evidence/sprint28/before/. Task taps count navigation and field focus (not typing/keystrokes); scroll is cumulative absolute window movement, including automatic positioning. Record sale stops at the actual item's Sales form, without submitting. No owner preference is saved. The same protocol/fixtures are used after implementation.

| Width / Text | Before Home Height | Before Profit Height | Horizontal Overflow |
|---|---:|---:|---|
| 320 / normal |4901 |6681 |none |
| 320 / larger |6333 |8559 |none |
| 390 / normal |4775 |6340 |none |
| 390 / larger |6066 |7889 |none |

| Task | Before320 Taps / Scroll px | Before390 Taps / Scroll px | Destination |
|---|---|---|---|
| Add item |1 /0 |1 /0 |/add |
| Find an item |2 /0 |2 /0 |/inventory, search focused |
| Record a sale |3 /208 |3 /208 |/inventory/item-fixture#item-sales |
| eBay orders |2 /216 |2 /128 |/ebay/orders |
| Profit figures |1 /0 |1 /0 |/profit |

Baseline6 browser cases PASS. Initial rehearsal failed only because its selector used GOLD instead of fixture TEST-EDITOR; corrected before the final baseline, no application change. Home makes six analytics requests (summary plus five charts/opportunities); Profit makes only its ledger request before the move. No chart/control is silently dropped. Sprint28 OPEN; no migration, live save or eBay/provider call.

## 2026-11-21: Implementation And Remeasurement

### Backend And Home

- Both registries retain the12 existing IDs and add `stock_on_hand` / `ebay_listings`; the frontend14-ID set and backend catalogue/defaults are tested. Default row is profit/units/stock/eBay only for no saved preference. GET creates no preference; existing saved ordering is neither reset nor rewritten. No model field/default migration is introduced.
- Home calls only its monthly summary and preference endpoints, plus the existing AppShell's saved local health GET. It makes **no chart endpoint request**; query trace is filed with the raw measurements. Quick actions remain available on503 and auth failures, without pretending a temporary failure requires reconnection/login. AuthRequiredState is retained for401/403.
- Profit comes from shared ledger rows/summary, including scrap rows, immutable sale-time fees/costs and exclusion counts. Sydney month boundaries are explicit. A no-sale scrap loss stays negative, not "No sales" instead of the amount. No rows, wholly unknown profit and genuine zero are distinct; cents are preserved. Stock counts saleable remaining units, not sold-status labels, and uses the ledger's all-in remaining known-cost basis, with unknown-cost units named separately.
- eBay listings counts the same active owned ChannelListing records as the hub; labelled "Marked active in Magpie", not a live eBay assertion. Urgent strip links to order, stuck-publish, genuine-allocation and take-down queues. It does not mutate/reconcile on load; unrecorded or intentionally smaller allocations are not alerts.
- Record a sale opens item selection, then the selected item's existing Sales tab/form using its retained anchor. No SaleRecord is submitted in the browser proof. Add/Find/hub/calculator/orders shortcuts point to existing task flows. The phone nav and Sprint27 keyboard hook/Save bars are unchanged.

### Profit And Reachability

All seven original chart sections, filters, phone estimate-vs-actual table, small-sample warnings and listing-priority list are retained in Charts & trends. Filters persist in `chart_*` search parameters independently of ledger period and accountant FY/CSV inputs. Monthly tiles open the corresponding monthly ledger or monthly chart figures, not an all-time total. `/dashboard` still opens Home; old chart anchors redirect to Profit, preserving filter parameters; What to list next opens its chart section in one tap. Router-history Back returns through selection to Home without a save. Actual iPhone Back remains in the owner acceptance gate.

### Before / After

| Width / Text | Home Before -> After px | Profit Before -> After px |
|---|---|---|
| 320 / normal |4901 ->1163 |6681 ->10742 |
| 320 / larger |6333 ->1545 |8559 ->13778 |
| 390 / normal |4775 ->1126 |6340 ->10319 |
| 390 / larger |6066 ->1389 |7889 ->12891 |

Profit is intentionally longer because every moved chart remains there. Home is about76% shorter at normal text. All four final after views have scrollWidth == clientWidth. Sixteen before/after images are filed unchanged/hash-verified; final visual review of320px larger text prompted icon-above-label action buttons so Calculator is not split mid-word. No viewport-scaled font sizes or new bottom-nav layout.

| Task | 320 Taps Before -> After | 320 Scroll Before -> After px | 390 Taps Before -> After | 390 Scroll Before -> After px |
|---|---|---|---|---|
| Add item |1 ->1 |0 ->313 |1 ->1 |0 ->0 |
| Find an item |2 ->2 |0 ->0 |2 ->2 |0 ->0 |
| Record a sale |3 ->2 |208 ->284 |3 ->2 |208 ->208 |
| eBay orders |2 ->1 |216 ->216 |2 ->1 |128 ->128 |
| Profit figures |1 ->1 |0 ->0 |1 ->1 |0 ->0 |

Before uses the existing navigation/flow; after prefers the new Home shortcuts. The fixed Add/Items shortcuts remain available with their old path and no extra Home scroll. The320px new Add button needs more scrolling than the fixed nav; this trade-off is reported, not hidden or counted as a universal improvement. Task scroll includes automatic positioning; it is not a page-height proxy. Larger-text screenshots/overflow checks use the same20px protocol. Final raw after metrics/request traces and fixture qualifications: [browser evidence](docs/evidence/sprint28/README.md).

### Verification So Far / Stop Gate

Local backend intermediate full run554 PASS/1 existing skip, then expanded11 Sprint28 tests and21 focused dashboard/profit tests PASS; final whole-suite/CI references are appended when complete. Frontend257 PASS, typecheck/build/check PASS; migration drift reports No changes detected. Full44 Playwright cases PASS with no skip/flaky; final10 Sprint28 cases re-run after month-label/large-text refinements PASS. Prior tests are retained; the old Dashboard chart assertions moved with the charts, not deleted. One unrelated local timeout under concurrent load disappeared on the full rerun without changing/skipping that test.

Sprint28 OPEN pending final validation/deployment references, Regan's Administrator restart/phone acceptance and independent review. No live data save, migration, rate seed, eBay/provider call or Codex restart; no next sprint. UI fixtures do not stand in for live financial parity or owner phone evidence.
