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

## 2026-11-21: Final Validation And Restart Handoff

Implementation head: `9078f154b00be7daaf6c7e2d6f90eb766a5cbe07`. [Validation44840855075](https://github.com/GoldDiggerTriangle/magpie/actions/runs/44840855075) **SUCCESS on both lanes**, for this exact head:

| Gate | Result |
|---|---|
| SQLite, job136648555306 |557 passed,1 existing skip; frontend257/48 files; Playwright44 passed. |
| PostgreSQL, job136648555507 |545 passed,13 existing skips. |
| Local final verification |557 passed/1 existing backend skip,445.54s; final11 Sprint28 and21 focused dashboard/profit cases also PASS after all-in-cost refinement. Frontend257, typecheck/check/build/no migration drift PASS. |
| Browser refinements |Full44 PASS, then10 final month-label/remeasurement cases and1 final asynchronous queue-scroll/focus case PASS; no skip or flaky result. CI re-runs all44 on the final code. |
| Documentation and secrets |Eight exact handoff replacements; spec/kickoff worktree and staged blobs equal Downloads byte-for-byte. Changed files and production bundle checked against known local credentials/patterns; PASS, no values revealed. |

Collected only after both CI lanes passed: **7 copied,155 unmodified,425 post-processed**; index and `index-D9aeatgJ.js` / `index-C4v03QMP.css` byte-match the tested build. Read-only database guard and a network-denied collection process: database, protected configuration and64 media files unchanged,0 network attempts, no service restart.

Actual NSSM/Waitress port8000 after collection: health200, root200 referencing the new assets; both new JS/CSS URLs404 in the old running static map. **Administrator restart and hard-refresh REQUIRED**; assets are collected, not yet proven live-served. Do not mistake the earlier root200 or synthetic browser images for post-restart acceptance. No temporary dev server is left for owner acceptance, and no authenticated write/provider request was used for the local route check.

The final queue navigation also waits for hub data, then scrolls/focuses its named section; changing a hash alone is not treated as a working jump. Tap metrics count navigation/focus, not horizontal tab-strip panning or typing; vertical scroll is cumulative absolute window movement. The prior raw tables/images remain unchanged. No new test or measurement is claimed for this documentation-only follow-up.

### Owner Gate

Regan: restart Magpie in Administrator PowerShell and hard-refresh on iPhone. Check Home's saved row/order (four new defaults only if no preference existed), quick actions, honest empty/unknown/cents states where present, alert links where there is genuine work, Record a sale -> item selection -> that item's Sales form, router/phone Back, and Profit Charts & trends including its independent filters and listing-priority jump. Do not submit a sale/preference or sync/reconcile/publish for this acceptance. Check normal/larger text and that Sprint27's keyboard/nav behaviour still holds. No extra real data is requested to manufacture a missing state.

**Sprint28 OPEN:** final implementation/automated gates PASS; Administrator restart, served-build verification, real iPhone acceptance and independent review remain pending. No migration, live save, eBay/provider call or Codex restart; no next sprint.

## 2026-11-21: Closure Note - Pending Independent Review

**Implementation/deployment and owner phone acceptance PASS; pending independent review, NOT CLOSED.** Regan replied **"worked well"** to the restart/hard-refresh and iPhone checklist above. This is owner testimony accepting the delivered experience, not a newly supplied set of photographs or itemised per-field confirmations. No additional sale, preference save, sync, reconciliation or publish action is inferred. The16 earlier screenshots remain explicitly synthetic Chromium evidence.

Final implementation: `9078f154b00be7daaf6c7e2d6f90eb766a5cbe07`; [Validation44840855075](https://github.com/GoldDiggerTriangle/magpie/actions/runs/44840855075), both lanes SUCCESS: SQLite557/1 existing skip, PostgreSQL545/13 existing skips, frontend257, browser44. Pre-acceptance evidence head `52d6d1982f12e95a43e330e3afb2fd0084d2e222`. No new application build or suite is claimed for this documentation filing.

Read-only actual-port8000 verification after Regan's response: Magpie service Running; `/api/health/`200, `/`200 referencing the tested assets, `/assets/index-D9aeatgJ.js`200 and `/assets/index-C4v03QMP.css`200. Both bodies exactly match the tested build. **The former asset404 is resolved.** An exact service restart time is not claimed. Database, protected configuration and64 media files unchanged across these verification GETs. No authenticated write or eBay/provider endpoint was called.

| Contract Criterion | Status | Evidence / Qualification |
|---|---|---|
| Baseline before application changes; repeated measurements | PASS | Baseline6 cases,16 hash-verified before/after images, both widths/text sizes, same-protocol task/height tables and raw after traces above. Page-specific unit fixtures are geometry evidence, not financial parity proof. |
| 2.1 Existing12 IDs,3-5 limit/saved order; two new tiles; defaults only with no saved preference | PASS | Both14-ID registries; server preference GET/create tests and frontend ordering/picker tests; no preference row created on GET. |
| 2.2 Sydney month/sale date, multi-unit sales, remaining stock/all-in known cost/unknown units, local eBay meaning | PASS | `test_sprint28.py` calendar, multi-unit and stock tests; ledger cost helper; active local listing count matches hub and is labelled Marked active in Magpie. No live eBay verification implied. |
| 2.3 Ledger profit parity with scraps, immutable fee/cost basis, exclusions, no-sales/unknown/zero and cents | PASS | Real-model parity, scrap-only, snapshot immutability, external/filter and state tests; KpiRegister formatting tests; existing profit/fee suites. No historical result recalculated. |
| 2.4 Monthly links reach matching figures | PASS | Monthly ledger/chart query parameters and browser destination/filter assertions; neither silently opens an all-time metric. |
| 2.5 Two-column phone tiles, legibility/44px | PASS |320/390 normal/larger automated screenshots, no horizontal overflow, button geometry assertions and visual review; Regan's general acceptance, now supplemented by [real iPhone Home stats](docs/evidence/sprint28/phone-acceptance/01-home-quick-stats.jpg). The real image does not establish exact CSS width or target measurements. |
| 3 All six shortcuts; Record sale selects item then opens its Sales form; works if stats fail | PASS | Real component browser flow, owner acceptance,503/auth unit/browser cases, and [real iPhone quick actions](docs/evidence/sprint28/phone-acceptance/02-home-actions-alert.jpg). Photograph shows all six entries, not the item-selection/Sales transition or a submitted sale. |
| 4 Urgent strip/queues; no false intentional/unrecorded allocation alert; empty hidden | PASS | Owned-record backend alert tests, canonical quantity-state reuse, frontend route/async queue-focus tests; [real iPhone Home](docs/evidence/sprint28/phone-acceptance/02-home-actions-alert.jpg) shows one sold-out take-down alert. No alert click, sync, reconciliation or listing-ending action is inferred. |
| 5.1 All charts/priorities and all filters moved; independent from accountant export | PASS | Original chart render helpers/assertions retained in ChartsAndTrends, seven sections, category/channel/unknown/date filters; browser CSV unchanged by chart-filter edits. |
| 5.2 Phone estimate-vs-actual table and small-sample warnings retained | PASS | Preserved chart/table code and old Dashboard assertions moved with it; CI/browser proofs. |
| 5.3 Listing priorities one tap from Home | PASS | What to list next link and browser viewport assertion on the actual target section. |
| 5.4 Old anchors redirect; /dashboard still works | PASS | Redirect preserves query filter parameters; actual Profit destination/section tests. |
| 5.5 Home fetches no chart data | PASS | Request interception/trace shows summary and preferences only, plus existing saved-health GET; chart endpoint assertions on normal/failure/navigation paths. |
| 6 Backend/frontend tests,320/390/larger, Back/targets/keyboard and dual CI | PASS | Run44840855075; local557 backend/257 frontend/44 browser plus final focused refinements; router-history Back and inherited Sprint27 keyboard gates retained. General owner testimony is supplemented by [five original iPhone images](docs/evidence/sprint28/phone-acceptance/README.md) of Home and Profit ledger. No new video, keyboard/Back demonstration or Charts & trends photo is supplied. |
| 7 Deployment/restart, owner iPhone check, final head/run/closure record | PASS | User response to restart/phone checklist and actual tested assets200/body-matched; [real Home](docs/evidence/sprint28/phone-acceptance/01-home-quick-stats.jpg), [Profit overview](docs/evidence/sprint28/phone-acceptance/03-profit-ledger-overview.jpg), [cash-lock summary](docs/evidence/sprint28/phone-acceptance/04-profit-cash-lock-summary.jpg) and [per-sale cents](docs/evidence/sprint28/phone-acceptance/05-profit-sale-cents.jpg). Charts & trends remains supported by prior tests/general testimony, not these photos. Exact restart time unavailable. |
| 7 Independent review before CLOSED | PENDING | D-143 independent verdict/update still required. Codex does not self-approve or mark CLOSED. |

**Recorded qualifications:** new Home Add shortcut needs more vertical scrolling at320px than the unchanged fixed-nav Add path; Profit is longer because every chart remains there; geometry fixtures are not live profit evidence; phone acceptance is verbal, with no newly supplied phone screenshots; exact restart time unavailable. Existing drawer attribution, genuine multi-unit live proof and evidence cosmetics remain separate backlog items, not changed or closed here.

**Sprint28 pending independent review only.** No further restart, phone task or live mutation requested by this filing. Documentation only: no code, migration, collectstatic, service restart, live save or eBay/provider call; no new sprint. Earlier pending deployment/owner paragraphs remain historical and are not rewritten.

## 2026-11-21: Real iPhone Images Filed

At Regan's request, filed all five attached original JPEGs unchanged/hash-verified in [phone-acceptance](docs/evidence/sprint28/phone-acceptance/README.md). The message said two screenshots (Home; Profit -> Charts & trends), but actual coverage is Home stats/actions/alert (images1-2) and Profit ledger overview/summary/per-sale cents (images3-5). **No Charts & trends view is present.** No other files were sought or substituted and no picture was relabelled as a chart screen.

Owner-acceptance rows2.5/3/4/6/7 above are updated solely to cite the newly supplied real-phone evidence and its limits, as explicitly requested. This supersedes the earlier verbal-only/no-new-phone-images qualification; all earlier narrative and numerical evidence is retained. Regan's general "worked well" acceptance remains PASS, independent review PENDING, NOT CLOSED. These images do not add individual transition/Back/keyboard confirmations, a chart photograph or a new financial recomputation. A Charts & trends image is still absent if photographic proof of that particular view is wanted.

Implementation9078f15 / Validation44840855075 both lanes green unchanged. No new application build/test/deployment, live data save, restart, migration or eBay/provider call in this documentation/image filing; no next sprint.
