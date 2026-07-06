# Sprint 24 Evidence - AI Review Flow and Collapsible Item Page

Status: implementation validated locally. Live NSSM restart and remote dual-lane `Validation` are closure gates after commit/push.

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
- Required closure action:
  - Restart `Magpie` from Administrator PowerShell after this commit is pulled/applied.
  - Verify `/api/health/` returns `200`.
  - Verify the item detail page serves the rebuilt collapsible UI.

## Remote Validation

- Pending until commit is pushed and GitHub dual-lane `Validation` is checked.
