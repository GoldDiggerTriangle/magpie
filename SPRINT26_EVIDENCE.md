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
