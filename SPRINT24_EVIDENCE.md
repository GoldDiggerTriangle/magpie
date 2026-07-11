# Sprint 24 Evidence - AI Review Flow and Collapsible Item Page

Status: reopened for Round 2. Round 1 was live-closed; Round 2 fixes are implemented and locally validated in this checkout. Formal Round 2 live closure remains pending owner proof that a full AI-approved/edited title saves and re-renders correctly from the restarted NSSM `Magpie` service.

## Scope Implemented

- Identify-and-fill completion now exposes a clear action: `Review N staged suggestions ->`.
- The review action expands the `AI research` item-detail section and jumps to `#ai-review`.
- The staged suggestion review panel now sits adjacent to the AI actions inside the `AI research` section.
- Item detail is reorganised into named collapsible sections:
  - Photos
  - Core details
  - Category specifics
  - AI research
  - Pricing evidence & comps
  - Listings / channels
  - Sales & valuations
- Photos and Core details open by default; the remaining sections start collapsed.
- Expand all / Collapse all controls are available.
- Section state persists per item via local storage.
- Desktop gets a left-hand section index; each index action expands and jumps to the section.
- Existing hash anchors expand the relevant section, including `#ai-review`.
- Suggestion review keeps per-field Approve / Edit / Reject and adds `Approve all shown`.
- `Approve all shown` is disabled until suggestions render and applies only pending suggestions in the rendered list.
- Batch approval is implemented as a visible-list convenience; it does not auto-approve anything before a user click.
- AI usage display now renders nonzero sub-cent usage as `<$0.01`.
- Banknotes identify scope is widened through a data/config registry:
  - country
  - denomination
  - series/year
  - prefix/serial
  - signature/variety
  - catalogue-ref candidates
  - condition observations
  - title draft
  - short-description draft

## Safety and Scope Controls

- No schema changes.
- No migrations.
- No new AI paths.
- No new network paths.
- No scraping.
- No new eBay API usage.
- Catalogue references remain candidate-only.
- Condition remains observation-only.
- Short descriptions are mapped to candidate draft fields.
- Nothing in staged suggestions persists to item data without explicit Approve/Edit or batch approval click.
- Temporary screenshot-only staged suggestions were created for UI proof and removed afterward:
  - cleanup count after removal: `0`.
- Temporary local browser session file was removed after screenshot capture.

## No-Content-Lost Checklist

- Photos:
  - Photo gallery retained.
  - Take photo / Choose from library uploader retained.
  - Upload selected retained.
  - Sprint 17 photo fix-up panel retained.
- Core details:
  - Title retained.
  - Status retained.
  - Condition retained.
  - Total quantity and sold/remaining line retained.
  - Category retained.
  - Location retained.
  - Save retained.
- Category specifics:
  - Descriptor-driven schema fields retained.
  - Lot retained.
  - Source retained.
  - Disposition retained.
  - Scrapped date retained.
  - Acquisition/refurb/shipping/packaging/value cost fields retained.
  - Notes retained.
  - Save retained.
- AI research:
  - Identify & fill / Price-assist panel retained.
  - Provider disabled/status/config display retained.
  - Reference links retained.
  - Suggestion review retained and moved adjacent to AI actions.
- Pricing evidence & comps:
  - Descriptor evidence retained.
  - Pricing evidence panel retained.
  - Sold-search panel retained.
  - Research links retained.
  - Comparable list retained.
  - Research log retained.
- Listings / channels:
  - Take-down checklist retained.
  - Copy pack retained.
  - Listing panel retained.
- Sales & valuations:
  - Valuation panel retained.
  - Profit breakdown retained.
  - Sales panel retained.

## Validation

- Migration check:
  - `python manage.py makemigrations --check --dry-run`
  - Result: `No changes detected`.
- Focused backend Sprint 24 tests:
  - `python -m pytest apps/intelligence/tests/test_sprint24.py apps/intelligence/tests/test_sprint15.py::test_ai_review_requires_explicit_approve_edit_or_reject -q`
  - Result: `6 passed`.
- Full backend suite:
  - `python -m pytest -q`
  - Result: `199 passed, 1 skipped`.
- Focused frontend Sprint 24 tests:
  - `npm run test -- --run src/components/AIResearchPanel.test.tsx src/components/Sprint13Panels.test.tsx src/features/inventory/ItemDetail.test.tsx src/features/settings/EbaySettings.test.tsx`
  - Result: `22 passed`.
- Full frontend suite:
  - `npm run test -- --run`
  - Result: `109 passed`.
- Typecheck:
  - `npm run typecheck`
  - Result: passed.
- Build:
  - `npm run build`
  - Result: passed.
- collectstatic:
  - `python manage.py collectstatic --noinput`
  - Result: `7 static files copied`, `155 unmodified`, `425 post-processed`.
- Django system check:
  - `python manage.py check`
  - Result: `System check identified no issues`.
- Diff whitespace check:
  - `git diff --check`
  - Result: passed.
- Built asset hardcoded-localhost check:
  - `rg "localhost:8000|127\\.0\\.0\\.1:8000|http://localhost|https://localhost" frontend/dist backend/staticfiles`
  - Result: no matches.
- New identify-scope network guard:
  - `apps/intelligence/tests/test_sprint24.py::test_no_new_network_paths_for_identify_scope_registry`
  - Result: covered by focused/full backend tests.

## Screenshot Evidence

Captured against a temporary port `8001` Waitress process from this checkout because this non-Administrator session could not restart the production NSSM service. The temporary process was stopped after capture.

- Phone collapsed item overview:
  - `docs/evidence/sprint24-phone-collapsed-item-overview.png`
- Phone expanded AI review section:
  - `docs/evidence/sprint24-phone-ai-review-expanded.png`
- Phone `Approve all shown` over visible suggestion list:
  - `docs/evidence/sprint24-phone-approve-all-shown.png`
- Desktop left-hand section index:
  - `docs/evidence/sprint24-desktop-section-index.png`

Final live-service screenshots captured after Administrator restart against `http://127.0.0.1:8000`:

- Live phone collapsed item overview:
  - `docs/evidence/sprint24-live-phone-collapsed-item-overview.png`
- Live phone expanded AI review section:
  - `docs/evidence/sprint24-live-phone-ai-review-expanded.png`
- Live phone `Approve all shown` over visible suggestion list:
  - `docs/evidence/sprint24-live-phone-approve-all-shown.png`
- Live desktop left-hand section index:
  - `docs/evidence/sprint24-live-desktop-section-index.png`
- Temporary live screenshot-only suggestions were removed after capture:
  - cleanup count after removal: `0`.

Automated frontend coverage proves the banner action itself:

- `AIResearchPanel runs identify and keeps output staged`
  - clicks `Review 1 staged suggestions ->`
  - asserts the supplied review handler is called.
- `ItemDetail desktop section index jumps and expands the AI review section`
  - clicks the mocked review action
  - asserts `window.location.hash === "#ai-review"`
  - asserts the suggestion review panel is visible.
- `ItemDetail deep link opens the AI review section`
  - opens `/inventory/item-1#ai-review`
  - asserts the suggestion review panel is visible.

## Live Service

- Current service before admin restart:
  - `Get-Service Magpie`: `Running`.
  - `sc.exe queryex Magpie`: `RUNNING`, PID `8164`.
  - `GET http://127.0.0.1:8000/api/health/`: `200`.
- Restart from this non-Administrator session was attempted and denied:
  - `nssm restart Magpie`: `nssm` not on PATH.
  - repo-local NSSM binary restart: `OpenService(): Access is denied.`
- Administrator restart completed by Regan after push.
- Live service after Administrator restart:
  - `Get-Service Magpie`: `Running`.
  - `sc.exe queryex Magpie`: `RUNNING`, non-zero PID `11672`.
  - `GET http://127.0.0.1:8000/api/health/`: `{"status":"ok"}`.
  - Live app checked on port `8000`, not temporary port `8001`.
  - Item detail page served Sprint 24 collapsible sections and AI review panel after hard refresh.

## Remote Validation

- Implementation commit:
  - `5447a66ecc54b7ba5da73d7c466ab1bf4811510e`.
- GitHub dual-lane `Validation`:
  - run `28771808326`.
  - result: `success`.
- This evidence update is documentation-only; the final closure response records the latest pushed head and latest `Validation` run.

## Closure Catch-up: Sprint 23 Round 2

- Final Sprint 23 Round 2 head:
  - `b3aa7ca06e1db707ad69621a8876a79ed8ba8967`.
- GitHub dual-lane `Validation`:
  - run `28769192729`.
- Real iPhone open-picker screenshots were required and captured for:
  - Country picker open on Add Item.
  - Denomination picker open on Add Item.
  - Country picker open on item edit.
  - Denomination picker open on item edit.
- Owner note after proof:
  - The picker worked, but country choices showing both codes and names was undesirable; the dropdown was changed to show country names only in the follow-up evidence path.

## Closure Catch-up: Sprint 24 Round 1

- Round 1 head commit:
  - `b9b7d8e7171a6a0e782cf0b8623e423fb2489e35`.
- GitHub dual-lane `Validation`:
  - run `28771991489`.
- Backend:
  - `199 passed, 1 skipped`.
- Frontend:
  - `109 passed`.
- Typecheck/build/collectstatic:
  - passed.
- Screenshot note:
  - Screenshots were captured on temporary local Waitress port `8001` because NSSM restart required Administrator elevation.
- Administrator live-service restart proof later confirmed:
  - `Magpie` running on port `8000`.
  - `/api/health/` returned `200 {"status":"ok"}`.
  - Item detail served Sprint 24 collapsible sections and the AI review panel after hard refresh.

## Round 2 Implementation

- Fixed the title persistence failure by scoping item-detail saves by section:
  - Core details submits only core fields including the full title.
  - Category specifics submits descriptor/cost/source/notes fields and no longer sends stale core text fields.
  - This prevents hidden stale form state from overwriting an AI-approved title with a fragment such as `Canadian $1 m`.
- Backend full-value apply path remains explicit:
  - Approve writes the complete staged value.
  - Edit writes the complete human-edited value.
- Structured suggestion values now render as human-readable text:
  - Catalogue-ref candidate payloads render as `Pick: PM-40a`.
  - Raw structured payloads are available only behind a `Raw payload` details toggle.
- AI call UUIDs no longer appear in user-facing rationale text:
  - Serializer splits the trailing `AI call <uuid>` into `audit_metadata`.
  - The UI renders audit linkage on a quiet metadata line.
- Safe-area spacing was added to the reorganised item page:
  - Item page frame respects `env(safe-area-inset-top)`.
  - Sticky item section headers use a safe-area top offset.
  - Item section and `#ai-review` anchors use safe-area-aware scroll margins.
- Competing catalogue candidates remain unchanged and candidate-only.
- No schema changes.
- No migrations.
- No new AI paths.
- No new network paths.
- No scraping.
- No new eBay API usage.

## Round 2 Validation

- Focused backend Sprint 24 tests:
  - `python -m pytest apps/intelligence/tests/test_sprint24.py`
  - Result: `7 passed`.
  - Covers full title approve/edit round-trip and audit metadata split.
- Full backend suite:
  - `python -m pytest`
  - Result: `201 passed, 1 skipped`.
- Focused frontend tests:
  - `npm run test -- --run src/components/Sprint13Panels.test.tsx src/features/inventory/ItemDetail.test.tsx`
  - Result: `13 passed`.
  - Covers structured catalogue-ref rendering, raw payload details, full title re-render after reload, and category-specific save not sending stale title fields.
- Full frontend suite:
  - `npm run test -- --run`
  - Result: `112 passed`.
- Typecheck:
  - `npm run typecheck`
  - Result: passed.
- Build:
  - `npm run build`
  - Result: passed, with the existing Vite large-chunk warning.
- collectstatic:
  - `python manage.py collectstatic --noinput`
  - Result: `7 static files copied`, `155 unmodified`, `425 post-processed`.
- Migration check:
  - `python manage.py makemigrations --check --dry-run`
  - Result: `No changes detected`.
- Django system check:
  - `python manage.py check`
  - Result: `System check identified no issues`.
- Diff whitespace check:
  - `git diff --check`
  - Result: passed.
- Built asset hardcoded-localhost check:
  - `rg "localhost:8000|127\\.0\\.0\\.1:8000|http://localhost|https://localhost" frontend/dist backend/staticfiles`
  - Result: no matches.

## Round 2 Live Closure Status

- Pending:
  - Owner live note that a full AI-approved/edited title saves and re-renders correctly through the restarted `Magpie` service on port `8000`.
  - Phone screenshots proving the reorganised item page and AI review controls are clear of the iOS status bar.
  - Final Round 2 head commit hash.
  - Final Round 2 GitHub `Validation` run ID.

## Round 2 Follow-up: Missing Title Suggestion

- Owner live check found no title suggestion in the AI review panel after Identify & fill.
- Live DB inspection confirmed the latest AI run for `GSP-00001` staged only:
  - `notes`
  - `ai_candidate.catalogue_refs`
  - `ai_candidate.signature_variety`
- Root cause:
  - The identify scope requested copywriting drafts including `title`, but the real provider response schema only required a generic `suggestions` array, so the provider could omit `title`.
- Fix:
  - Identify & fill now adds a conservative, low-confidence editable `title` suggestion from the first AI search term when the provider omits a dedicated title draft.
  - The fallback is limited to the Identify phase.
  - Price-assist remains unable to stage title suggestions.
  - The fallback is staged only; it still requires explicit Approve/Edit and never auto-writes item data.
- Regression coverage:
  - `test_missing_title_draft_gets_editable_low_confidence_search_term_fallback`
  - `test_price_assist_surfaces_no_number_as_price`
- Validation:
  - Focused backend:
    - `python -m pytest apps/intelligence/tests/test_sprint15.py::test_price_assist_surfaces_no_number_as_price apps/intelligence/tests/test_sprint24.py`
    - Result: `9 passed`.
  - Full backend:
    - `python -m pytest`
    - Result: `202 passed, 1 skipped`.
  - Focused frontend:
    - `npm run test -- --run src/components/Sprint13Panels.test.tsx src/features/inventory/ItemDetail.test.tsx`
    - Result: `13 passed`.
  - Typecheck:
    - `npm run typecheck`
    - Result: passed.
  - Build:
    - `npm run build`
    - Result: passed, with the existing Vite large-chunk warning.
  - collectstatic:
    - `python manage.py collectstatic --noinput`
    - Result: `7 static files copied`, `155 unmodified`, `424 post-processed`.

## Round 2 Follow-up: Category Specifics Suggestions

- Owner confirmed the title fill flow works and requested the same staged Approve/Edit flow for Banknotes category-specific values:
  - Series/year
  - Prefix/serial
  - Signature/variety
  - Catalogue refs
- Live DB inspection showed recent AI responses did create these leads, but some real category fields were staged as `ai_candidate.*`:
  - `ai_candidate.series_year`
  - `ai_candidate.prefix_serial`
  - `ai_candidate.signature_variety`
- Root cause:
  - The normaliser treated `ai_candidate.*` as review-only even when the field name was listed as an editable field in the per-category identify scope.
- Fix:
  - AI suggestions now use the category identify scope as the source of truth.
  - `ai_candidate.series_year`, `ai_candidate.prefix_serial`, and `ai_candidate.signature_variety` are normalised to editable `attributes.*` suggestions for Banknotes because those fields are in the Banknotes identify scope.
  - They still appear as low-confidence/candidate-band leads and still require explicit Approve/Edit.
  - `ai_candidate.catalogue_refs` remains candidate-only and does not write into item data.
- Regression coverage:
  - `test_candidate_named_identify_scope_fields_stay_editable`
  - Existing catalogue-ref candidate-only guard remains green.
- Validation:
  - Focused backend:
    - `python -m pytest apps/intelligence/tests/test_sprint24.py apps/intelligence/tests/test_sprint15.py::test_price_assist_surfaces_no_number_as_price`
    - Result: `10 passed`.
  - Django system check:
    - `python manage.py check`
    - Result: `System check identified no issues`.
  - Full backend:
    - `python -m pytest`
    - Result: `203 passed, 1 skipped`.
- Deployment note:
  - Backend-only change; the `Magpie` service must be restarted before the live app can stage new editable category-specific suggestions.

## Follow-up: Pricing Evidence Screenshot / Link Capture

- Owner request:
  - From the item Pricing evidence & comps section, paste an eBay link or upload a sold-result screenshot and have Magpie fill the comparable capture fields.
- Implementation:
  - Added `/api/items/<item_id>/pricing-evidence/capture-draft/`.
  - Added a "Fill capture form from screenshot or link" helper above the existing "Capture verified comp" form.
  - Added local OCR parsing for uploaded screenshots when local Tesseract is available.
  - The parser fills a draft only; it does not create a `Comparable`.
  - The existing explicit `Add to grid` action remains the save/approval step.
- Marketplace safety:
  - Link-only capture records the source and URL but does not fetch the marketplace page.
  - Link-only capture does not invent price, title, date, shipping, condition, grade, or sale format.
  - Screenshot OCR can prefill visible values such as sold price, shipping, sold date, title, price basis, and sale format for human review.
  - Magpie still does not scrape, fetch, cache, summarise, or warehouse marketplace result pages.
- Test case covered:
  - eBay sold screenshot text shaped like the owner example:
    - `SOLD 14 JUN 2026`
    - sold price `AU $11.13`
    - shipping `+AU $24.29 delivery`
    - eBay short link `https://ebay.io/m/gPzKet`
  - Resulting draft:
    - source `eBay sold`
    - source tag `ebay_sold`
    - price basis `buyer_visible`
    - price `11.13`
    - shipping `24.29`
    - observed date `2026-06-14`
- Validation:
  - Focused backend:
    - `python -m pytest apps/research/tests/test_comparable_capture.py apps/research/tests/test_sprint14.py -q`
    - Result: `10 passed`.
  - Focused frontend:
    - `npm run test -- PricingEvidencePanel.test.tsx`
    - Result: `4 passed`.
  - Django system check:
    - `python manage.py check`
    - Result: `System check identified no issues`.
  - Migration check:
    - `python manage.py makemigrations --check --dry-run`
    - Result: `No changes detected`.
  - Typecheck:
    - `npm run typecheck`
    - Result: passed.
  - Build:
    - `npm run build`
    - Result: passed, with the existing Vite large-chunk warning.
  - collectstatic:
    - `python manage.py collectstatic --noinput`
    - Result: `7 static files copied`, `155 unmodified`, `425 post-processed`.
  - Full frontend:
    - `npm run test`
    - Result: `113 passed`.
  - Full backend:
    - `python -m pytest -q`
    - Result: `207 passed`, `1 skipped`.
  - No-fetch guard:
    - `rg "requests|httpx|urlopen|urllib\\.request|fetch\\(" backend/apps/research/comparable_capture.py frontend/src/components/PricingEvidencePanel.tsx frontend/src/api/pricingEvidence.ts`
    - Result: no matches.
- Live deployment note:
  - Frontend assets have been built and collected.
  - The `Magpie` service must be restarted before the live port `8000` serves the new backend endpoint and SPA bundle.

## Follow-up: Screenshot OCR Unavailable Fallback

- Owner live check:
  - The pricing evidence helper accepted an eBay link and screenshot, but the live service showed:
    - `Screenshot OCR is unavailable on this machine. Install local Tesseract, or type the sold result into the capture form.`
- Findings:
  - `tesseract.exe` was not on PATH.
  - Common Windows install locations were not present.
  - `winget` and Chocolatey are installed, but a non-admin `winget install UB-Mannheim.TesseractOCR` did not complete from this shell and was stopped.
- Fix:
  - Added `MAGPIE_TESSERACT_PATH` support so the service can use a pinned local Tesseract path even when the NSSM service PATH does not include it.
  - Added common Windows Tesseract path detection.
  - Added a `Text copied from screenshot` field as a no-install fallback.
  - Pasted eBay sold-result text uses the same parser as screenshot OCR and fills the same comparable capture draft fields.
  - Duplicate OCR-unavailable warning text was removed.
- Safety:
  - Links still are not fetched.
  - Screenshot text/OCR still only fills a draft.
  - The existing `Add to grid` button remains the explicit save step.
  - No new marketplace network path was added.
- Validation:
  - Focused backend:
    - `python -m pytest apps/research/tests/test_comparable_capture.py -q`
    - Result: `5 passed`.
  - Focused frontend:
    - `npm run test -- PricingEvidencePanel.test.tsx`
    - Result: `4 passed`.
  - Django system check:
    - `python manage.py check`
    - Result: `System check identified no issues`.
  - Migration check:
    - `python manage.py makemigrations --check --dry-run`
    - Result: `No changes detected`.
  - Typecheck:
    - `npm run typecheck`
    - Result: passed.
  - Build:
    - `npm run build`
    - Result: passed, with the existing Vite large-chunk warning.
  - collectstatic:
    - `python manage.py collectstatic --noinput`
    - Result: `7 static files copied`, `155 unmodified`, `425 post-processed`.
  - No-fetch guard:
    - `rg "requests|httpx|urlopen|urllib\\.request|fetch\\(" backend/apps/research/comparable_capture.py frontend/src/components/PricingEvidencePanel.tsx frontend/src/api/pricingEvidence.ts`
    - Result: no matches.

## Round 2 Live Closure Defect: Admin Login Route Swallowed By PWA Service Worker

- Owner live reproduction:
  - `http://127.0.0.1:8000/admin/login/?next=%2F`
  - Browser result: React SPA error page, `Unexpected Application Error! 404 Not Found`.
  - This made the `AuthRequiredState` link unusable even though it pointed at the intended Django admin login route.
- Live service reproduction from this run:
  - Direct HTTP against actual NSSM/Waitress service on port `8000`:
    - `/admin/` returned `200`, `Log in | Django site admin`, no React 404.
    - `/admin/login/?next=%2F` returned `200`, `Log in | Django site admin`, no React 404.
  - In-app browser against actual service on port `8000`:
    - `/admin/login/?next=%2F` returned the React SPA 404.
- Root cause:
  - Django URL ordering was already correct:
    - `path("admin/", admin.site.urls)` before API and before the SPA fallback.
    - SPA fallback excludes `admin/`.
  - The deployed browser failure was caused by the generated PWA service worker navigation fallback, which could intercept `/admin/login/` and serve `index.html` before Django handled the request.
- Fix:
  - Added a shared PWA navigation fallback denylist:
    - `/api`
    - `/admin`
    - `/media`
    - `/static`
  - Wired the denylist into `VitePWA({ workbox.navigateFallbackDenylist })`.
  - Added backend routing regression tests proving `/admin/` and `/admin/login/` are not served by the SPA fallback.
  - Added frontend PWA routing tests proving `/admin` and `/admin/login/?next=%2F` are denied from service-worker SPA fallback handling.
  - Hardened the backend regression to assert URL resolution (`admin:login`, `admin:index`) plus login form fields, avoiding environment-specific admin branding text.
- Built output proof:
  - `frontend/dist/sw.js` contains:
    - `denylist:[/^\/api(?:\/|$)/,/^\/admin(?:\/|$)/,/^\/media(?:\/|$)/,/^\/static(?:\/|$)/]`
- Validation:
  - Focused backend:
    - `python -m pytest apps/core/tests/test_admin_routing.py -q`
    - Result: `3 passed`.
  - Fresh CI-like SQLite backend:
    - migrate + seed + `python -m pytest -q`
    - Result: `210 passed`, `1 skipped`.
  - Focused frontend:
    - `npm run test -- pwaRouting.test.ts`
    - Result: `2 passed`.
  - Full frontend:
    - `npm run test`
    - Result: `115 passed`.
  - Django system check:
    - `python manage.py check`
    - Result: `System check identified no issues`.
  - Migration check:
    - `python manage.py makemigrations --check --dry-run`
    - Result: `No changes detected`.
  - Typecheck:
    - `npm run typecheck`
    - Result: passed.
  - Build:
    - `npm run build`
    - Result: passed, with existing Vite large-chunk warning.
  - collectstatic:
    - `python manage.py collectstatic --noinput`
    - Result: `7 static files copied`, `155 unmodified`, `425 post-processed`.
- Live closure status:
  - Not live-closed yet.
  - The current browser session still has the stale service worker active and continues to show the React 404 until the service/browser receives the rebuilt worker.
  - Required next proof after Administrator restart of `Magpie`:
    - Browser `/admin/` renders Django admin login HTML.
    - Browser `/admin/login/?next=%2F` renders Django admin login HTML.
    - Neither route shows `Unexpected Application Error`.
