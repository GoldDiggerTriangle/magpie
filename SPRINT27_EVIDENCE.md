# Sprint 27 Evidence

## 2026-11-20: Implementation And Automated Gates

**OPEN: Fixes A/B built and local automated gates PASS; dual-lane CI, static deployment and owner restart references are appended below when complete. Regan's iPhone check and independent review remain required.** No Sprint27 closure or live-behaviour acceptance is claimed.

### Sources And Safety

Baseline main: `dc2aea15a0da7e6946e7de2574c6fa63476d5e92` (handoff v5.00). Latest preceding Validation44639400718 at59dafb99b35ed9705f44bcea858ac45de4d1fd75 succeeded; that commit is an ancestor with the same baseline application code. All eight exact Find blocks in the supplied Sprint27 lock update matched once; applied verbatim to v5.01, including D-146 and the authorised section3/8 additions. Spec/kickoff v1.0 copied byte-for-byte from Downloads:

| File | Bytes | SHA256 |
|---|---:|---|
| SPRINT_27_SPEC.md |6133 |57ff583a38107f9af4a8cc04b4906bf33ec4ac166db69a0fae982031deac93ba |
| SPRINT_27_KICKOFF.md |1919 |46bbd0edd02071cbda0fe5ab28b937ae846c22454fb3694cfeddce852ea803d8 |

No migration, schema/dependency/settings/environment change, live save, production draft/sale creation, eBay/provider call or agent service restart. Backend suites use isolated test databases/fake adapters and temporary-media fixtures; concurrency uses temporary file-backed SQLite on its lane and PostgreSQL on its lane. No real credential is broken or used for a probe. No rate, price or policy value is entered into production. No migrations are installed.

### Fix A: New eBay Draft Stock Guard

| Contract | Implementation And Evidence |
|---|---|
| Resolver order | Existing `plan_group` reconciliation refusal first; eligible active draft reuse unchanged at200, including zero stock; only then refresh the item and check stock before fresh creation or published-history relist seeding. |
| Stable refusal | API409, code `sold_out`, detail "Sold out - nothing to list." (the actual string uses the spec's em dash, tested exactly). Other stock races return409/`stock_changed`, with no raw database error. Existing unresolved-publish response remains unchanged at400, not mislabelled sold out. |
| Definitive atomic guard | `creation_stock.claim_creation_stock` reads fresh stock_revision, conditionally writes that same revision (no-op), refreshes stock and checks Sprint10 quantity_remaining inside one insert transaction. The write takes the shared sale/quantity writer fence on SQLite and PostgreSQL without inventing a stock movement or modifying inventory values. A stale revision/write-upgrade refusal rolls back and asks for reload; no blind retry. |
| Every application creation path | Model save boundary covers generated drafts, item/header/hub/quick/relist paths, admin Add and seed. Admin model validation shows Sold out in the form; a save-time stock race rolls back before a reload message. Seed refuses with CommandError and its transaction rolls back. Bulk creation and supported constant channel changes/bulk channel saves also use the guard; API channel transition into eBay returns409. |
| Not a blanket update rule | Normal existing-draft edits/archive stay available at zero. Existing read-only history/in-flight/staging protections stay in place. No stock check is inserted into ordinary edits, withdraw, reconcile or existing-draft reuse. Phase25 stage/publish/allocation/pending-order gates are unchanged and remain covered by the full suite. |
| Stock semantics | Uses active sale counts, excludes superseded sales, ignores the item's sold status label. Partial stock creates with remaining quantity; restocking re-enables creation. Defaults never invent quantity/price. |
| Tests | `test_sprint27_stock.py`: zero reuse across active/unknown statuses, unresolved outcomes, relist/history/audit preservation, partial/restock/superseded sales, unchanged inventory values, edits/archive, channel transition, direct/bulk/admin/seed, and both ordered sale/create race outcomes. `test_sprint26_audit.py` now asserts409/no row instead of201/quantity0. The additional obsolete zero-quantity assumption in `test_sprint25_defaults.py` now tests refusal at zero and retains every empty-default/readiness assertion on positive stock. |
| Frontend message | Shared ApiError formatting recognises the stable sold_out code for every entry point; common-client unit test and browser top-entry refusal test. No new eBay call/path. |

The concurrency tests force both orders. If the last-unit sale commits after the creator's read but before its fence, no draft is inserted (SQLite stale snapshot/write refusal or PostgreSQL revision mismatch). If creation wins the fence while stock is positive, the later sale serialises after it: one local draft may then remain at zero, as explicitly required for reuse; a draft is not a stock reservation, and stage/publish still reject unavailable stock. File-backed SQLite uses WAL in this test only to allow the forced stale-reader interleaving; this does not change the live journal mode. No production rows are inserted for a race test.

### Fix B: Keyboard-Aware Navigation And Save

- AppShell's hook hides mobile nav only for a writable text-like input/textarea plus a visualViewport drop greater than both150px and20% of the known closed baseline. Focus alone, hardware-keyboard-like focus, selects/date/file controls, read-only/disabled fields, small chrome changes, zoom, rotation without a known baseline, desktop and missing/invalid viewport information leave it visible. Field contents are never read or logged.
- Closing the keyboard restores nav even with focus retained. Viewport resize/scroll and focus/blur are observed; a field switch is rechecked on the next frame. The nav uses visibility rather than removal, retaining page padding and document geometry so hiding itself does not add a layout jump. Safe-area spacing is retained.
- ListingSaveBar measures actual nav visibility and visualViewport's offset/height against the layout viewport, not a stale nav height or innerHeight alone. It follows viewport panning/resize and ignores hidden-nav height. Safe-area padding and measured end-of-editor reservation stay. The title and Save can both be reached without overlap in the geometry tests.
- Tests: three hook tests plus common API error test (four additional frontend tests); five new browser cases across320/390, including viewport drop/focus/restore, conservative cases, three required controls, field clearance, unchanged document geometry and desktop. Existing Sprint26 keyboard geometry now checks nav clearance when visible, visible-bottom clearance when expressly hidden; no reachability/business assertion is skipped. Full34 browser tests PASS, then the five new cases re-run after the final field-clearance assertion PASS.
- [Twelve simulated geometry screenshots](docs/evidence/sprint27/keyboard/README.md), copied unchanged/hash-verified. These are not real keyboard/phone captures and do not close Regan's Safari acceptance gate.

### Drawer Attribution: OPEN

Read-only source check: AppShell renders a fixed **left** desktop sidebar (`hidden ... md:block`) and the full-width bottom mobile nav. The right-aligned More-actions popover is contextual, not a persistent edge drawer. No drawer/off-canvas/slide-over implementation was found in frontend source. The Settings EnvironmentBadge renders the uppercased configured environment; that alone identifies no overlay owner.

**No positive external attribution exists.** There is no same-Settings-screen phone demonstration of an external feature toggled on/off that makes the handle appear/disappear. Source absence alone is not attribution. The item therefore stays **OPEN / unattributed**, with no guessed owner and no code change. It does not block Fixes A/B. No phone feature was toggled by Codex and no live Settings credential was changed.

### Local Verification

- Backend: **546 passed,1 existing skip**,359.78s; includes the final conditional no-op fence and inventory-preservation assertion. Earlier545-pass run preceded that last test and is not substituted for the final result.
- Frontend: **252 passed**,0 failed suites/unhandled errors. Typecheck PASS.
- Playwright: **34 passed**,0 skipped/flaky; five focused cases also pass after the final clearance assertion. All provider/API interactions are mocked/intercepted.
- Production build PASS: `index-LtFabXMF.js`, `index-pA-mnJas.css`; existing large-chunk warning, no dependency change.
- Django check PASS; `makemigrations --check --dry-run --noinput`: **No changes detected**. No migration file or live migration command.
- Source inspection and test assertions retain canonical reuse, immutable history, the original76-row inventory, copy/download/take-down and publish/reconcile safety. No Sprint26 historical evidence is rewritten.

### Stop And Owner Gate

After both Validation lanes pass and static collection is ready, ask Regan to restart in Administrator PowerShell and hard-refresh. On iPhone, focus/switch writable fields; check nav hides only with the on-screen keyboard, Details Save/Add comparable/listing Save remain reachable by scrolling, and dismissing the keyboard restores nav without an extra jump. Do not stage/publish/reconcile or create a live sale/draft for these checks. Regan's own phone checks are the only authorised owner edits; none has been performed by Codex.

Acceptance remains OPEN for dual-lane/deployment references below, owner restart/phone acceptance and independent review. Drawer remains unattributed; genuine multi-unit live proof and evidence tidying remain out of scope. No next sprint starts from this work.

### CI Follow-Up: Isolated Admin Static Storage

Initial implementation58133bc / Validation44694729755 failed the backend admin-Add test in clean CI: rendering the invalid form required a collected `admin/css/base.css` manifest entry. The live checkout already had that manifest, masking the test's local-artifact dependency. This was not a stock-guard failure, dependency-rate change or eBay error. The admin form test now uses scoped plain static storage and an explicitly uncollected temporary STATIC_ROOT; every refusal/form/no-row assertion remains. Production storage/configuration is unchanged, and production collectstatic/WhiteNoise smoke stay in CI.

The bulk-create guard also preserves Django's positional arguments; a positional batch-size case was added to the existing refusal test. Focused stock20 tests passed before the static-isolation fix; final clean-storage/local and dual-lane results are filed below. No test is skipped or weakened and no migration is introduced.

### Final Validation And Static Deployment: 2026-11-20

Implementation head: `466b98d51e865bba1fe3acc69a4f1e9810a402b1` (initial implementation `58133bcdb019641f681efb3a2e5ccbeaaf88d754`, followed by the isolated-admin-test/positional-API correction). [Validation 44695261077](https://github.com/GoldDiggerTriangle/magpie/actions/runs/44695261077) completed **SUCCESS on both lanes**, for this exact implementation head:

| Gate | Final Result |
|---|---|
| CI SQLite, job136150392085 | 546 passed,1 existing skip; frontend252 passed; Playwright34 passed. |
| CI PostgreSQL, job136150391717 | 534 passed,13 existing skips; both forced sale/create orders covered on this database lane. |
| Final local backend after CI correction | 546 passed,1 existing skip,240.13s, exit0. |
| Local frontend / browser / static checks | 252 frontend,34 browser plus5 final focused browser cases; typecheck/build/Django check PASS; no migration drift. |
| Supplied documentation | Spec/kickoff byte equality retained; eight exact handoff replacements remain unchanged, with only this task's required section9 log added. |

Collected static files only: **7 copied,155 unmodified,425 post-processed**. Collected index/JS/CSS match the tested build byte-for-byte (`index-LtFabXMF.js`, `index-pA-mnJas.css`). Database, protected configuration and all64 media files were compared before/after and are unchanged. The collection process was network-blocked:0 network attempts. No service restart or startup recovery was run by Codex.

Actual NSSM/Waitress service on port8000 remains Running. Local read-only GETs after collection: `/api/health/`200; `/`200 and references the new assets; both new `/assets/` URLs404 in the still-running service's old static map. **Administrator restart and hard-refresh REQUIRED before acceptance**; the build is collected, not yet verified as served. No authenticated write, eBay/API metadata call or live save was used to obtain this proof.

### Acceptance At Handoff

| Spec Section5 Criterion | Status And Evidence |
|---|---|
| Fix A both database lanes, resolver order/admin/seed/race/old audit contract | PASS: final implementation and both Validation jobs above; full backend suites retain existing stage/publish/allocation/reconcile guards. |
| Fix B automated320/390 checks | PASS:34 browser tests and12 simulated screenshots. **Real iPhone acceptance OPEN**, owned by Regan after restart: focus/switch fields, Details Save, Add comparable, listing Save, keyboard dismiss/nav restore without a jump. |
| Drawer attribution | OPEN/unattributed, explicitly allowed by the spec; no positive external-toggle evidence supplied. Source absence is not attribution. |
| Suites/typecheck/build/collectstatic/both CI lanes | PASS above. Administrator restart, served-new-assets verification and independent review remain OPEN. |

**Sprint27 remains OPEN, not CLOSED.** Stop for Regan's Administrator restart/hard-refresh and iPhone check, followed by independent review. No migration, live save, eBay/provider call, service restart or new sprint was performed. No secret values are included. This documentation-only follow-up records the validated implementation head rather than claiming a second application build.

## 2026-11-20: Real iPhone Evidence And Served Assets

Regan supplied four real iPhone screenshots following the restart/hard-refresh request. [Original phone evidence](docs/evidence/sprint27/phone-acceptance/README.md) filed unchanged with source/destination SHA256 equality (four JPEGs,100386/98199/99068/92986 bytes). The condition picker leaves navigation visible; the two title/keyboard images show it hidden while typing; the dismissed-keyboard image shows it restored. No saved change or full phone acceptance is inferred from the images.

At19:12-19:15 Sydney, actual port8000 GETs returned200 for `/api/health/`, `/`, `/assets/index-LtFabXMF.js` and `/assets/index-pA-mnJas.css`. The index references both new assets; both asset bodies exactly match the tested implementation466b98d build. The former running-static-map404 is resolved. NSSM Magpie is Running; process creation time was unavailable to this read-only session, so no exact restart timestamp is claimed. Live database, protected configuration and64 media files are unchanged across these verification GETs; no request was made to any eBay/provider endpoint or authenticated write route.

| Remaining Acceptance | Current Evidence / Owner |
|---|---|
| Select visible / text keyboard hidden / dismissed restored | Real iPhone photographs above support all three states. |
| Switching writable fields; no dismissal jump | OPEN: Regan to confirm. Two cursor positions in the same title are not a field-switch test; still images cannot establish transition motion. |
| Details Save / Pricing Add comparable / listing-editor Save reachable with keyboard | OPEN: Regan to confirm reachability by scrolling, without submitting anything. Not pictured in this set. |
| New assets served | PASS: actual8000 GETs and exact body matches above. No further restart requested solely for the old404. |
| Automated checks | Existing implementation466b98d / Validation44695261077 both lanes green; no application change or new suite claimed in this evidence filing. |
| Drawer / independent review | Drawer OPEN/unattributed; independent review PENDING. No external-toggle demonstration or independent verdict supplied. |

**Sprint27 remains OPEN.** Documentation/original-image filing and read-only local deployment verification only; no code, migration, live save, eBay/provider call, collectstatic or Codex restart. Await the remaining owner phone checks before presenting a complete closure note for independent review. Earlier pending deployment paragraphs are historical, not rewritten.

## 2026-11-20: Closure Note - Pending Independent Review

**Implementation, deployment and Regan's iPhone acceptance PASS; pending independent review, NOT CLOSED.** Regan answered **"All checks passed"** to the explicit question covering writable-field switching, Details Save, Pricing Add comparable and listing-editor Save reachable with the keyboard open, and navigation returning without a jump after dismissal. This owner testimony supplies the checks not demonstrable in the four still images; it is not inferred from those images. No extra screenshot, submitted action or independent verdict is claimed.

Final implementation head: `466b98d51e865bba1fe3acc69a4f1e9810a402b1`; [Validation44695261077](https://github.com/GoldDiggerTriangle/magpie/actions/runs/44695261077), both lanes SUCCESS. Original phone/deployment evidence baseline: `7dffd8d952c4c09a062ab5325bd935c47531a18c`. The preceding exact-hash/source-copy and served-asset proofs remain part of this closure record. This filing changes documentation only, not the tested or served application.

| Spec5 Criterion | Status | Evidence / Qualification |
|---|---|---|
| Fix A zero-stock refusal; unchanged reuse/reconciliation order | PASS | `test_sprint27_stock.py` zero refusal/reuse/unresolved cases; replaced `test_sprint26_audit.py`201 contract; implementation466b98d / Validation44695261077. Eligible active reuse remains200 at zero, unresolved states still require reconciliation, new creation409/sold_out. |
| Fix A fresh stock, both race orders, restock/partial/superseded sales | PASS | File-backed SQLite and PostgreSQL race tests; inventory-preservation, stock-count and restock tests; both Validation lanes green. A pre-sale local draft is not a reservation; existing stage/publish stock guards remain. |
| Fix A all creation paths, including admin/seed/channel/bulk; no blanket update guard | PASS | Direct/bulk/channel-transition, admin invalid Add form, seed rollback, existing edit/archive tests; full suites retain publish/withdraw/reconcile/allocation behaviour. No production test row was inserted. |
| Fix B320/390 automated checks; desktop/conservative states | PASS | `frontend/e2e/sprint27.spec.ts`, inherited full34 browser tests, three hook tests,12 explicitly simulated screenshots; focus plus large viewport drop required, select/uncertain cases visible, real-visible-bottom Save geometry. |
| Fix B real iPhone check: switching fields, three controls reachable, dismissal/no jump | PASS | Regan's explicit "All checks passed" response on2026-11-20 plus [four original hash-verified JPEGs](docs/evidence/sprint27/phone-acceptance/README.md). Testimony and photographic coverage are distinguished above. |
| Drawer attribution | PASS for the allowed disposition; item remains OPEN | Source/read-only check recorded; right-edge handle is visible in phone images, but no same-Settings-screen external-toggle attribution exists. Unattributed backlog retained, not declared fixed/external. Spec3/5 explicitly allow this and it does not block FixesA/B. |
| Suites, typecheck, build, collectstatic and both lanes | PASS | SQLite546/1 existing skip, PostgreSQL534/13 existing skips; frontend252, browser34, typecheck/build/check/no migration drift PASS; collectstatic7/155/425, build-matched assets, protected data unchanged. Validation44695261077 both jobs SUCCESS. |
| Administrator restart / actual live build / phone | PASS for deployment and owner checks | Prior requested restart is operationally evidenced by Running service and new static map: actual8000 health/index/new JS/CSS200, body matches. Exact restart time unavailable; none invented. Regan's subsequent phone checks all pass. No Codex restart. |
| Closure head/run and evidence record | PASS | This dated section, final implementation and run above, source/deployment baseline7dffd8d, complete spec5 mapping, phone testimony and original-image links. |
| Independent review before CLOSED | PENDING | Regan supplies the D-143 independent verdict/update after review. Codex does not self-approve or mark CLOSED. |

**Recorded limitations/backlog:** the drawer/PRODUCTION-badge overlay remains unattributed; simulated browser geometry is not substituted for phone testimony; exact service restart time is unavailable. Genuine multi-unit live proof and older evidence-file cosmetic tidying remain out of scope. No additional owner phone action, live save, eBay call, restart or new sprint is requested by this closure filing. Earlier partial-acceptance paragraphs remain historical. STOP for independent review.

Final evidence-baseline revalidation: [Validation44701044297](https://github.com/GoldDiggerTriangle/magpie/actions/runs/44701044297), head `7dffd8d952c4c09a062ab5325bd935c47531a18c`, **both lanes SUCCESS** (PostgreSQL job136169227580, SQLite job136169227872). The SQLite lane includes frontend/browser and Waitress/WhiteNoise smoke gates. This revalidates the original-image evidence commit and unchanged application; the following closure filing changes only this file and the handoff, outside the workflow's application/evidence-image path filters. Implementation466b98d / Validation44695261077 remains the application-build reference. No second implementation or self-issued independent verdict is implied.

## 2026-11-20: Independent Review - CLOSED + LIVE

**CLOSE WITH RECORDED LIMITATIONS.** Received independent verdict and limitations, quoted verbatim from Edit 6 of `MASTER_HANDOFF_UPDATE_2026-11-20_SPRINT27_CLOSED.md`:

**2026-11-20 — Claude — Sprint 27 ☑ CLOSED + LIVE, after independent review.** Implementation `466b98d`; latest Validation `44701044297`, both lanes green; Regan’s iPhone acceptance PASS with four original screenshots. ChatGPT’s independent review (D-143) returned **CLOSE WITH RECORDED LIMITATIONS**, finding no unmet spec §5 criterion: (1) the resolver order holds (unresolved publishes go to reconciliation first; an eligible draft returns unchanged at 200 even at zero stock; only then the stock check before fresh creation or relisting, returning 409 `sold_out`); admin Add shows the refusal and the seed command rolls back; (2) the race tests use separate database connections and a real last-unit sale on file-backed SQLite and PostgreSQL (sale first: no draft survives; draft first: the later sale succeeds, since a draft reserves no stock); edits and archive are tested at zero, and withdrawal and reconciliation gained no stock guard; (3) the nav hides only with writable-field focus and a substantial viewport drop, stays visible when uncertain, and the listing Save bar uses the visible bottom edge at 320 and 390px; (4) the iPhone originals show the nav visible with a picker, hidden while typing and restored after dismissal, with Regan’s confirmation covering field switching, all three Saves and no jump. **Recorded limitations:** the drawer overlap remains open and unattributed; the exact restart time was not recorded, though the served assets matched the tested build.

This append supersedes the earlier pending-independent-review status; no earlier evidence is rewritten. Handoff v5.04 records Sprint27 CLOSED + LIVE after the supplied independent review, not Codex self-approval. Documentation only: no application change, new test/deployment claim, service restart, live save or eBay/provider call. No new sprint is committed or started; a separate instruction is required.
