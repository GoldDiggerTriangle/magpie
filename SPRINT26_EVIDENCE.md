# Sprint 26 Evidence

## 2026-11-19: Phase 0 Audit And Review Stop

**Status: PHASE 0 DELIVERED; awaiting Regan's screenshot review and Claude's final mapping. Phases1-5 NOT STARTED.**

Controlling sources: [Sprint26 spec v1.0 LOCKED](docs/specs/SPRINT_26_SPEC.md) section1 and [kickoff v1.0](docs/specs/SPRINT_26_KICKOFF.md). Handoff v4.96/D-145 activates D-134 only in the locked phase order. Audited source checkout baseline: **8d0b10666bc8cbdb92f86232c586a62c4856cfb4** on main. This is documentation/evidence work, not a new application build or a Sprint26 closure.

### Source Import And Exact Update

- `C:\Users\Regan\Downloads\SPRINT_26_SPEC.md` -> `docs/specs/SPRINT_26_SPEC.md`:8941 bytes, v1.0 LOCKED, source/copy SHA256 equal.
- `C:\Users\Regan\Downloads\SPRINT_26_KICKOFF.md` -> `docs/specs/SPRINT_26_KICKOFF.md`:2884 bytes, v1.0, source/copy SHA256 equal.
- `MASTER_HANDOFF_UPDATE_2026-11-19_SPRINT26_LOCKED.md`: eight Find blocks each matched **exactly once** before application. All eight replacements applied verbatim, v4.95 -> v4.96, plus this task's required Codex section9 line. No other handoff changes.
- The supplied update does not replace the header's Last updated value (still18Nov); it does identify the19Nov author/update and section9 entry. That source wording was preserved, not silently repaired.
- Updated [spec source table](docs/specs/README.md). Source and changed text files were checked against known local credential values and credential patterns; none is copied into evidence.

### Safety And Measurement Method

1. Owned data came from existing local GET views with SQLite opened `mode=ro`, in-memory DRF authentication and all socket connections refused. No live session/login was created. Django WSGI/startup recovery was not invoked.
2. Snapshot collection returned85 saved view responses, all successful;0 network attempts; digests of all58 SQLite tables (including internal tables) identical before/after. These are read-only snapshot checks, not migrations or restore tests.
3. Playwright used the **actual served production page and assets on port8000**, with every `/api/` request intercepted. Local own-photo media was served from owned files; external URLs were aborted. Three states used owned-record snapshots; four used existing `frontend/e2e/phase6.fixture.ts` fixtures. No new application fixture/source/helper file was added.
4. Temporary Vite was used solely to import the existing TypeScript fixture, not as the photographed application server. Browser and fixture helper were closed; no listener remains on4179.
5. Screenshots used390x844 CSS pixels, device scale1, Chromium mobile/touch emulation, en-AU and Australia/Sydney, fresh contexts with no remembered accordion settings. Default Photos/Core are open. Gold's photograph is owned media, not remote/stock imagery.
6. Capture runs replayed GETs only. Task runs additionally simulated item PATCH, valuation POST and preview POST **in browser memory only**. No request for these actions was transported to the live API. No live saves, draft creation, eBay/provider calls, inventory/offer updates, publish, withdraw, reconcile or service restart.
7. A valuation run reuses an already recorded item/report/sale figure, or a clearly synthetic existing fixture input. No amount was invented as real evidence. GSP has no such owned figure, so its real-record run stops at the form; its separate geometry-only rehearsal uses a test-fixture input and is not a GSP valuation.
8. Preview rehearsal is the existing preview renderer fed an offline cached-shape response. It is **not** evidence of current live taxonomy, policy terms, fees, publish readiness or eBay health. In-flight/unknown/published guards were respected, not bypassed.
9. All63 PNGs decode, are nonblank and390px wide. Final capture and task runs have0 blocked requests and0 browser errors. An early isolation pilot intercepted/rejected the sold item's top create action before transport; the final sold-item baseline deliberately does not invoke it. No production mutation resulted.
10. No backend/frontend app-code change, dependency change, migration, collectstatic, service restart or test/CI-gate alteration. Existing Sprint25 tests were not rerun for this docs-only audit, and their earlier green runs are not represented as a fresh Sprint26 Validation.

### Screenshots And Page Heights

[Open the63-image index](docs/evidence/sprint26/phase0/README.md). It links default viewport, full all-open page and all seven section opening viewports for every requested state. Full-page images include every outer section's content; viewport crops are not whole-panel captures. Nested optional disclosures are identified in the source inventory, not automatically opened or approved.

| State | Default document height px | All collapsed px | All outer sections open px | All-open scrollWidth/clientWidth px |
|---|---:|---:|---:|---:|
| GOLD-00002 (live) | 9744 | 1085 | 32542 | 390/390 |
| GSP-00001 (draft) | 5900 | 1064 | 32080 | 390/390 |
| STM-00002 (sold out) | 3795 | 1009 | 21212 | 390/390 |
| Fixture: staged | 3832 | 1079 | 21318 | 390/390 |
| Fixture: publishing | 3832 | 1079 | 21544 | 390/390 |
| Fixture: publish_unknown | 3832 | 1079 | 21564 | 390/390 |
| Fixture: partial stock | 3832 | 1079 | 21402 | 390/390 |

Section heights with all seven sections open (px):

| State | Photos | Core | Specifics | Research | Pricing evidence | Listings | Sales/valuation |
|---|---:|---:|---:|---:|---:|---:|---:|
| GOLD-00002 (live) | 8091 | 683 | 1705 | 3751 | 6312 | 8333 | 2988 |
| GSP-00001 (draft) | 4269 | 683 | 1886 | 7283 | 6585 | 7709 | 3008 |
| STM-00002 (sold out) | 2218 | 683 | 2330 | 1666 | 8334 | 1731 | 3646 |
| Fixture: staged | 2186 | 683 | 1244 | 1716 | 4971 | 6468 | 3376 |
| Fixture: publishing | 2186 | 683 | 1244 | 1716 | 4971 | 6694 | 3376 |
| Fixture: publish_unknown | 2186 | 683 | 1244 | 1716 | 4971 | 6714 | 3376 |
| Fixture: partial stock | 2186 | 683 | 1244 | 1716 | 4971 | 6552 | 3376 |

These heights are content- and font-dependent baselines, not target compactness metrics. At390px the desktop seven-button index is **not visible**: spec0's three-navigation-systems description does not literally apply to the current phone viewport. The page still has page-wide Expand/Collapse plus individual accordions; the desktop index exists at wider widths.

### Task Protocol And Baselines

Each task starts in a new context at scrollY0 with default sections. Locate each control, scroll it into a usable viewport position above the fixed nav, then focus/tap. Count button taps, input-focus taps and native select opening/choice (modelled as2 taps); typing, scrolling gestures and loading time are not taps. Scroll distance is the **sum of absolute scrollY changes**, including anchor/autoscroll, not just the ending position. It is CSS-pixel geometry, not human timing or measured iOS-picker gestures. After implementation repeat the same protocol, item values, default preferences, fonts and viewport.

- **edit:** focus/edit Title, restore its original value before simulated core Save; open Category specifics, focus/edit its first specific (or its picker), restore original before simulated specifics Save. Five taps including the section opener; each Save stays field-scoped.
- **value:** open Sales & valuations, choose Comparable-based if needed, focus Suggested with an existing figure, then simulated Create valuation report. This measures reaching/recording through the UI, not valuation validity or permission to treat a gut price as evidence.
- **list:** top List on eBay opens the existing editor, then Review listing if enabled. No create/stage/publish/reconcile occurs. An unavailable action is N/A, not a zero-tap success.

| State | Task | Taps | Cumulative scroll px | Result / limitation |
|---|---|---:|---:|---|
| GOLD-00002 (live) | edit | 5 | 10492 | Two simulated scoped saves; title and first specific edited then restored before simulated Save. |
| GOLD-00002 (live) | value | 3 | 10036 | Existing item figure; one simulated report. |
| GOLD-00002 (live) | list | 1 | 9518 | Read-only published editor reached; no preview action available. |
| GSP-00001 (draft) | edit | 5 | 6829 | Two simulated scoped saves. |
| GSP-00001 (draft) | value | 1 | 5056 | Form reached; no existing figure found, so no number supplied/report recorded. |
| GSP-00001 (draft) | list | 2 | 11180 | Editor and simulated cached-shape preview reached. |
| STM-00002 (sold out) | edit | 5 | 5169 | Two simulated scoped saves. |
| STM-00002 (sold out) | value | 3 | 4088 | Existing sale figure; one simulated report. |
| STM-00002 (sold out) | list | 0 | 0 | No retained draft; top action would create one and was not invoked. Not a completed task. |
| Fixture: staged | edit | 5 | 4120 | Two simulated scoped saves. |
| Fixture: staged | value | 5 | 4125 | Existing test-fixture figure; strategy changed explicitly; one simulated report. |
| Fixture: staged | list | 2 | 7952 | Editor and simulated cached-shape preview reached. |
| Fixture: publishing | edit | 5 | 4120 | Two simulated scoped saves. |
| Fixture: publishing | value | 5 | 4125 | Existing test-fixture figure; strategy changed explicitly; one simulated report. |
| Fixture: publishing | list | 1 | 3606 | Editor reached; preview disabled by in-flight/unknown-outcome guard. |
| Fixture: publish_unknown | edit | 5 | 4120 | Two simulated scoped saves. |
| Fixture: publish_unknown | value | 5 | 4125 | Existing test-fixture figure; strategy changed explicitly; one simulated report. |
| Fixture: publish_unknown | list | 1 | 3606 | Editor reached; preview disabled by in-flight/unknown-outcome guard. |
| Fixture: partial stock | edit | 5 | 4120 | Two simulated scoped saves. |
| Fixture: partial stock | value | 5 | 4125 | Existing test-fixture figure; strategy changed explicitly; one simulated report. |
| Fixture: partial stock | list | 2 | 7952 | Editor and simulated cached-shape preview reached. |

GSP supplemental **geometry-only** complete value path: **3 taps /6193px** using an existing test-fixture input, one simulated report. Source explicitly says "not an item valuation" in [supplementary metrics](docs/evidence/sprint26/phase0/task-metrics-value-rehearsal.json). Its actual owned-record case remains incomplete at1 tap/5056px until Regan supplies/selects an admissible figure. Do not compare a fabricated successful real-record valuation against the later layout.

Gold's published editor correctly has no fresh preview/publish action. STM-00002 has no retained draft and its inner Create draft is disabled at zero stock, but the top List on eBay is **enabled** and would POST the existing create endpoint. The audit does not call it and does not claim the backend would accept or reject it. That entry-point inconsistency needs explicit disposition outside any accidental layout change; no live draft was made to force task completion.

[Raw21 task records](docs/evidence/sprint26/phase0/task-metrics.json) retain each action, source, mock count and outcome. There is no before/after improvement claim yet.

### Control Inventory And Proposed Mapping

[SPRINT26_CONTROL_INVENTORY.md](SPRINT26_CONTROL_INVENTORY.md) preserves **all76 original Sprint25 IDs and current-path cells unchanged** and adds proposed destination/tab and tap path to every row. Eight supplemental rows identify newer or easily orphaned controls without replacing original rows. Every underlying component has exactly one proposed tab home; header warnings/links are shortcuts, not duplicate editing forms. Old [x] marks are historical Sprint25 parity, not Sprint26 completion.

- Details: Core + Category specifics, separate Saves.
- Photos: Gallery/Uploader/Fixup; selected upload Files and own-photo review retained.
- Research: AIResearch/Suggestions/ResearchLinks/**ResearchLog**.
- Pricing: Descriptor/PricingEvidence/SoldSearch/Comparables/**Valuation + valuation ProfitBreakdown**.
- eBay: canonical draft/editor/workflow/history, Quantity/TakeDown and **Copy packs for other channels**, still usable with no eBay connection.
- Sales: actual sales/corrections/history.
- Global item header/authentication and existing board/hub/Settings remain in their current ownership; out-of-scope screens are not remade.

Existing hashes, `?draft=`, upload shortcuts and Back are mapped. **Review decision:** old `#sales-valuations` spans two proposed tabs; proposal is Pricing/Valuation (old first content) plus a Sales shortcut. Regan/Claude must confirm it rather than silently losing/reinterpreting the link. The proposed optional inner disclosures are justified by measured long panels in the inventory; none is implemented.

### Developer Labels And Unsaved State

[SPRINT26_LABELS_AND_STATE.md](SPRINT26_LABELS_AND_STATE.md) inventories46 label/representation families and22 local-state ownership groups, including conditional controls shared by item/hub/deep-link editor entry points.

Key findings:
- Repeated unknown-source labels, raw enum statuses/valuation strategies, category/location IDs and snapshot/provenance jargon can be made readable **without dropping truth**.
- Primary copy-pack text currently uses preformatted blocks. Raw suggestion JSON is already behind Raw payload; it is not a blanket primary debug dump.
- Captured metadata dates are local numeric dates and reviewed time already uses local words; source inspection also identifies raw YYYY-MM-DD dates in sales/comparable history and monospace sales date/money. No raw ISO timestamp with a time component or "AUD 0.0" presentation bug was found in the seven states. Missing archived prices use "AUD -"; later wording should say not set, never zero.
- Publishing/unknown fixtures display an "Unpublished staged offer" notice and wording implying editing stays local while fields are locked. Wording must respect uncertain outcomes; do not alter publish safety to fit the label.
- Outer accordion bodies remain mounted via `hidden`. Tab unmount would lose pending files, suggestion/research/capture input, valuation/sale forms, review and selection state.
- **useDraftAutosave cleanup flushes pending edits on unmount.** Keep tabs mounted so tab navigation itself does not trigger a save; ordinary human-edit autosave remains.
- Mounted alone is insufficient: `ItemDetail` form resets on `item.data`; `ProfitBreakdown` costs reset on `item`; other forms/review flags have refresh resets. Later state work needs dirty-buffer protection and safe revalidation.
- No dirty-state fix, unmount experiment on the live app, policy refresh or stored draft edit has been made.

### Review Stop And Remaining Decisions

1. Regan: mark the annoying controls/scroll regions on the screenshot index, especially8091px of default Gold photo content before lower work, long Research/Pricing/editor areas and header density.
2. Claude/Regan: confirm/amend the proposed six-tab mapping, legacy `#sales-valuations` destination and justified nested disclosures. Keep all76 rows, added controls, field-scoped Saves and warnings outside inactive tabs.
3. Record a disposition for the sold/no-retained-draft top-entry inconsistency and unknown-state wording. Do not accidentally introduce backend/eBay behaviour changes under a layout sprint.
4. If an actual GSP valuation task is needed, Regan must choose an admissible figure/source. The fixture rehearsal is geometry only.
5. **STOP here.** No Phase1-5 code, new API path, backend fix, migration, deployment or additional live listing work is authorised by this audit. Phone/Safari keyboard/safe-area/larger-text acceptance and later CI/remeasurement remain future gates, not passed by these Chromium captures.
## 2026-11-19: Phases 1-5 Implementation (Spec v1.1)

**OPEN: implementation/local gates PASS; Validation and deployment confirmation are filed below when available. Regan's restart/phone acceptance and independent closure review remain outstanding.**

### Sources And Scope

Regan supplied v1.1 spec/kickoff and the Phase0 review update. Source/destination bytes match: spec12711 bytes (SHA256 bc87635f18b4f166ba8538d309abd630ff3d02d89833ad0b11a45ba15d9c15c7), kickoff3050 bytes (SHA256 5dc25cbc6f1b35a46483e38a17663270eb1e99f552c712c18f3aabb3090723be). All seven Find blocks matched exactly once; replacements applied verbatim, handoff4.96 ->4.97. Spec section11 authorises the build after Phase0 review. Unchanged historical wording left by the supplied update was not silently repaired.

Runtime backend/API/model/pipeline code is unchanged; the only backend addition is the isolated audit test `apps/listing/tests/test_sprint26_audit.py`. No migration, settings, dependency or environment change, no live save, no eBay/provider call and no Codex restart. Phase0 evidence above remains historical; its stop point was superseded only by Regan's explicit v1.1 instruction.

### Phase And Section 11 Checks

| Requirement | Implementation / verification |
|---|---|
| Phase1 six tabs | Details/Photos/Research/Pricing/eBay/Sales; inactive panels remain mounted via hidden. Sticky scrollable strip, visible partial next tab plus labelled chevron, desktop row, keyboard arrows/Home/End and44px minimum targets. |
| Selection/deep links | Explicit hash or draft query wins over valid per-item remembered tab, then Details. Existing hashes, listing-/quick-ebay- fields, upload-photo event and exact history query retained. Select before deferred focus; wait for asynchronously rendered editor. Back/Forward and stale remembered-tab fallback tested. |
| Confirmed mapping | Valuation/valuation ProfitBreakdown first in Pricing; actual sales in Sales; ResearchLinks/ResearchLog in Research; copy packs in eBay and usable without a connection. No other-screen layout migration. |
| Legacy sales-valuations | Opens Pricing at Valuation; visible Sales shortcut selects Sales. Integrated navigation/focus tests. |
| Phase2 header | Compact title/SKU/status/List on eBay; named More actions -> Delete item -> existing confirmation/cancel with title+SKU. Separate live link retained, including owned ChannelListing URL fallback if no draft is retained. |
| Sold out | Remaining0 replaces top create/list action with plain Sold out. Read-only history/copy packs remain accessible through eBay; live link retained if known. Backend guard is not changed. |
| Urgent stock warnings | Compact warning remains outside inactive tabs; jump opens eBay then the quantity/take-down control. Pending/unlinked/uncertain stock logic stays server-owned, explicit and unchanged. |
| Photos | Three-across at390px; tap opens full-size own photo in native modal. Arrange exposes set-main, earlier/later and confirmed delete. At320px Arrange uses two columns so all44px controls fit. Camera/library/upload remain prominent; adjustments disclosure stays mounted. Callback tests and mocked existing-endpoint reorder/main/resume browser check PASS. |
| Phase3 dirty protection | Recursive clean-field refresh merge preserves edited fields/schema siblings; save acknowledgement does not replace later typing. Core/specifics, costs, comparable edits, sales, AI settings, valuation-method selection and quantity target protected. Stock/review validity still revalidates; stale confirmations are not preserved as valid. |
| Navigation is not save | Mounted listing editor is not cleaned up by a tab switch; pending edit continues its existing650ms autosave. No extra flush from navigation. Pending upload Files, selected listing photos, research/capture buffers and note inputs survive switching. Query-only navigation across all11 states tested. |
| Phase4 plain language | Readable draft states and valuation methods, Source unknown/You entered/chose this, date-only history formatting, standard-text labels, normal-type copy packs and descriptions, missing price says Price not set. Category IDs/manual fallback in details; names/paths and real policy terms remain visible. Readiness/D-129/calculated-vs-actual/legacy source truths kept. |
| State-specific notices | Publishing says in progress; publish_unknown says result not yet known; both explain locked editing/do not send again. Neither claims unpublished/local edits. Reconcile, timeout and retry safety unchanged. |
| Phase5 reachability | Original76 IDs/current-path cells retained exactly. CI raw-table check plus real-panel/route assertions across11 states and existing individual panel/workflow/copy/download/take-down tests. Original behavioural assertions retained; obsolete accordion/index assertions translated to the authorised tab navigation, not skipped. |
| Width gates |29 Playwright tests PASS, including320/390px at normal/larger text,80-character titles, item/hub/editor/preview/staged review, photo modal/Arrange, keyboard-height Save/nav clearance and no document horizontal overflow. Deliberate horizontal tab-strip scrolling is tested separately. |
| Phone/closure | NOT yet passed for this new layout. Regan must restart/hard-refresh and accept GOLD/GSP/STM on phone. Independent review still required before CLOSED. |

### Read-Only Backend Zero-Stock Finding

Source inspection: `ItemListingDraftViewSet.create` calls the existing canonical builder without checking remaining stock; defaults supply `item.quantity_remaining`, and ListingDraft.quantity permits0. **Isolated test result: HTTP201, draft status draft, quantity0, no offer/listing ID; live metadata function not called.** Seeded sold-out item/test database only; no POST to production, no live draft created. Test runs in both Validation lanes. **Backlog, separate instruction:** a backend draft-create stock guard if Regan wants one. This sprint changes frontend findability only; existing stage/publish stock gates are unchanged.

### Same-Protocol Task Remeasurement

Same390x844/scale1/locale/timezone, fresh context, initial scroll0, input focus/button counting, native select modelled as2 taps and cumulative absolute scrollY changes as Phase0. Destination selection is now the owning tab rather than an accordion opener; default Details already exposes both scoped forms. Inputs restored before simulated Saves, existing recorded/fixture figures only. Updated names do not change the operation. All API writes remained intercepted in memory; preview is cached-shape rendering, not a live readiness or fee check.

Each cell is **taps / cumulative scroll px**:

| State | Task | Phase0 | Final layout | Outcome / qualification |
|---|---|---:|---:|---|
| GOLD-00002 | edit | 5 / 10492 | 4 / 1954 | Same task; browser-memory saves/preview only. |
| GOLD-00002 | value | 3 / 10036 | 3 / 802 | Same task; browser-memory saves/preview only. |
| GOLD-00002 | list | 1 / 9518 | 1 / 267 | Editor only; existing read-only/in-flight gate retained. |
| GSP-00001 | edit | 5 / 6829 | 4 / 2184 | Same task; browser-memory saves/preview only. |
| GSP-00001 | value | 1 / 5056 | 1 / 263 | Form only; still no admissible figure. |
| GSP-00001 | list | 2 / 11180 | 2 / 5615 | Same task; browser-memory saves/preview only. |
| STM-00002 | edit | 5 / 5169 | 4 / 2552 | Same task; browser-memory saves/preview only. |
| STM-00002 | value | 3 / 4088 | 3 / 774 | Same task; browser-memory saves/preview only. |
| STM-00002 | list | N/A | N/A | No retained draft; Sold out, no top create action. |
| Fixture staged | edit | 5 / 4120 | 4 / 1487 | Same task; browser-memory saves/preview only. |
| Fixture staged | value | 5 / 4125 | 5 / 1094 | Same task; browser-memory saves/preview only. |
| Fixture staged | list | 2 / 7952 | 2 / 4525 | Same task; browser-memory saves/preview only. |
| Fixture publishing | edit | 5 / 4120 | 4 / 1487 | Same task; browser-memory saves/preview only. |
| Fixture publishing | value | 5 / 4125 | 5 / 1094 | Same task; browser-memory saves/preview only. |
| Fixture publishing | list | 1 / 3606 | 1 / 261 | Editor only; existing read-only/in-flight gate retained. |
| Fixture publish_unknown | edit | 5 / 4120 | 4 / 1487 | Same task; browser-memory saves/preview only. |
| Fixture publish_unknown | value | 5 / 4125 | 5 / 1094 | Same task; browser-memory saves/preview only. |
| Fixture publish_unknown | list | 1 / 3606 | 1 / 261 | Editor only; existing read-only/in-flight gate retained. |
| Fixture partial stock | edit | 5 / 4120 | 4 / 1487 | Same task; browser-memory saves/preview only. |
| Fixture partial stock | value | 5 / 4125 | 5 / 1094 | Same task; browser-memory saves/preview only. |
| Fixture partial stock | list | 2 / 7952 | 2 / 4567 | Same task; browser-memory saves/preview only. |

GSP's actual valuation remains incomplete: no admissible owned figure was supplied. Its **same fixture-input geometry rehearsal** is3/6193 -> **3/851**, not a new item valuation. Gold's published history has no new preview; in-flight drafts keep preview disabled; STM has no retained draft and no top create action. These N/A cases are not zero-tap successes.

All comparable completed tasks use no more taps and less scrolling. Every synthetic state's edit run measured1487px in the final same-protocol run. Cumulative counting includes asynchronous/native scroll changes; raw per-action records are retained. No worse task is hidden or waived.

### Heights And Images

[Final56-image index](docs/evidence/sprint26/implementation/README.md). Same owned records plus four synthetic states; no image is claimed as a new real-iPhone capture.

Document heights at390px (not sum-of-hidden-panels height):

| State | Old default | New default Details | Details | Photos | Research | Pricing | eBay | Sales |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| GOLD-00002 | 9744 | 2798 | 2798 | 1016 | 5024 | 7443 | 8539 | 1623 |
| GSP-00001 | 5900 | 3028 | 3028 | 1065 | 8520 | 7522 | 7869 | 1693 |
| STM-00002 | 3795 | 3396 | 3396 | 866 | 3100 | 9047 | 2099 | 2460 |
| Fixture staged | 3832 | 2331 | 2331 | 888 | 2621 | 6894 | 6698 | 1637 |
| Fixture publishing | 3832 | 2331 | 2331 | 888 | 2621 | 6894 | 6924 | 1637 |
| Fixture publish_unknown | 3832 | 2331 | 2331 | 888 | 2621 | 6894 | 6924 | 1637 |
| Fixture partial stock | 3832 | 2331 | 2331 | 888 | 2621 | 6894 | 6801 | 1637 |

Gold's old Photos section alone was8091px; the **entire new Photos-tab page** is1016px, including header/nav spacing. These are deliberately named different measures, not a claim that a tab document equals a former section. Long research/eBay content remains reachable inside its one tab; text sizes were not shrunk to obtain the improvement.

Capture/task snapshots: all58 SQLite-table digests unchanged;0 attempted network connections; all saved view responses successful;0 browser errors/blocked requests. Final56 images decoded/nonblank/390px. The owned screenshots show real own-photo thumbnails, while fixture placeholders stay labelled as fixtures. The external drawer/PRODUCTION-badge backlog is unchanged and not attributed to this work.

### Local Verification And Stop Gate

- Backend: **527 passed,1 existing skip**,288.53s; no live database or real credentials used. Production app/backend logic unchanged.
- Frontend: **248 passed**, no skipped/failed suites or unhandled errors. Existing canonical reuse/no-create-on-mount/published-plus-active/error guards retained; original workflow91 and inherited browser assertions retained. Added real-component refresh checks for AI model/cap, valuation method and quantity target/confirmation alongside recursive-buffer tests.
- Typecheck PASS. Production build PASS; existing large-chunk warning retained. Final assets `index-CuPKGVAS.js` and `index-BOiqsqO7.css`.
- Playwright: **29 passed**,0 skipped/flaky; existing22 plus7 new tests. Automated reduced-height keyboard geometry is not real Safari keyboard/status-bar proof.
- Copy packs and take-down checklist remain regression-green in the current full suites. No additional rate/fee/profit engine or published-data change.
- Validation/deployment references are appended below after they finish. **No self-closure:** ask Regan for Administrator restart and phone acceptance only after both lanes pass and static collection completes.

### Validated Implementation And Restart Handoff

Final implementation head: **d34ddabcc946a4666d5660350247a92d4f100e94**. [Validation44477593759](https://github.com/GoldDiggerTriangle/magpie/actions/runs/44477593759) completed successfully on both lanes: SQLite527 passed/1 existing skip (80.36s), PostgreSQL515 passed/13 existing skips (66.94s), frontend248 passed, browser29 passed/0 skipped/flaky. Typecheck, build, migration-drift check, marketplace confinement, encrypted CI backup/restore, collectstatic, deploy check and Waitress/WhiteNoise smoke all green. No workflow, dependency, runtime-backend or migration change. These references validate the implementation commit; the following evidence/handoff-only commit does not change tested code.

At **2026-11-19 18:20 Sydney**, local collectstatic PASS: **7 copied,155 unmodified,425 post-processed**. Collected index and assets match the tested build byte-for-byte: `index-CuPKGVAS.js`, `index-BOiqsqO7.css`. Database file, .env and all64 media digests are unchanged across collection; network attempts0. Source/staged-doc and built-output secret scans PASS. Original76 inventory cells/IDs intact; no behavioural assertion skipped, and the four original top-entry tests remain alongside the new sold-out/live-link test.

Actual port8000 after collection: `/api/health/`200; `/`200 and references the new asset names; both new asset URLs404 in the still-running WhiteNoise map. NSSM Magpie remains Running. **Administrator restart is REQUIRED now**, followed by hard refresh. This is not a claim that the new tabs are already live or owner-accepted. Temporary browser/Vite sessions ended; port4179 has no listener.

**STOP: Phases1-5 built and automated gates PASS; Sprint26 remains OPEN pending Regan's restart and phone acceptance, then independent review.** Regan: run `Restart-Service -Name Magpie` in Administrator PowerShell, hard-refresh, and check GOLD-00002, GSP-00001 and STM-00002. Confirm all six tabs/header, off-screen-tab cue, More actions -> named Delete confirmation -> Cancel, Photos grid/full-size/Arrange controls, readable Save/nav clearance, retained history/copy packs and GOLD's separate View on eBay. STM must show Sold out, with no top create action. Do not stage, publish, reconcile or change live values for this layout acceptance. Capture each tab/header per spec9; real Safari keyboard/safe-area/larger-text checks remain owner proof, not inferred from Chromium.

Remaining recorded limitations: actual GSP valuation has no selected admissible figure (fixture geometry rehearsal only); GOLD is published/read-only and in-flight previews stay disabled; STM listing task is N/A without a retained draft. Backend zero-stock draft-create currently accepts quantity0 (isolated201 test), separately deferred guard. Drawer/PRODUCTION-badge backlog unchanged. No live save, eBay/provider call, service restart by Codex, or new sprint authorised.
