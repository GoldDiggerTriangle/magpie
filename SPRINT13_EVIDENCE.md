# Sprint 13 Evidence - Phase 5 Local Floor

Date: 2026-06-15

## Scope

Sprint 13 delivered the local-only Phase 5 foundation:

- eBay sold-search URL builder on item detail.
- Local OCR adapter seam with graceful unavailable state.
- Staged `FieldSuggestion` review with Approve / Edit / Reject.
- Duplicate-image fingerprinting and near-duplicate review candidates.

Out-of-scope controls remained intact:

- No cloud AI.
- No API key or external AI provider.
- No Magpie network calls for OCR, duplicate detection, or eBay sold results.
- No eBay scraping, fetching, caching, warehousing, or summarising.
- No AI numeric price bands.
- No catalogue ID or grade promoted as authoritative data.
- No duplicate auto-merge.
- No suggestion writes live item data without explicit human Approve/Edit.

## Implementation Summary

Backend:

- Added `apps.intelligence`.
- Added additive migration `intelligence.0001_initial`.
- Added `FieldSuggestion` for staged suggestions.
- Added `ImageFingerprint` for photo perceptual hashes.
- Added item endpoints:
  - `GET /api/items/<id>/sold-searches/`
  - `POST /api/items/<id>/ocr/`
  - `POST /api/items/<id>/duplicate-scan/`
- Added `GET /api/field-suggestions/` and per-suggestion approve/edit/reject actions.
- Wired photo upload fingerprinting so new uploaded photos are fingerprinted and near-duplicate candidates are staged for review.
- Updated backup/restore table coverage for Sprint 13 tables.

Frontend:

- Added item-detail "Search eBay sold" panel.
- Added item-detail "Suggested fields" review panel.
- Added OCR and duplicate-scan actions with loading, empty, success, warning, and error states.
- Split medium/high suggestions from low/candidate leads.
- Kept candidate duplicate rows as review-only; they do not alter item data.

## Migration And Live Data

Pre-migration encrypted backup:

- `backend/backups/magpie-backup-20260614-210945.tar.gz.enc`

Migration applied while the `Magpie` service was stopped:

- `intelligence.0001_initial` applied successfully.

Post-migration live counts:

- Items: 8
- Photos: 2
- Valuations: 5
- Drafts: 2
- Credentials: 1
- Sales: 4
- Field suggestions: 0
- Image fingerprints: 0

The browser evidence did not run OCR, scan duplicates, approve, edit, reject, or create live suggestions. Final live counts stayed unchanged after screenshots.

## Backup / Restore Proof

Post-migration encrypted backup:

- `backend/backups/magpie-backup-20260614-225724.tar.gz.enc`

Restore spot-check target:

- `C:\Users\Regan\Documents\Codex\2026-06-13\magpie-sprint13-restore-spotcheck`

Restore spot-check confirmed:

- `intelligence_fieldsuggestion` table present.
- `intelligence_imagefingerprint` table present.
- Items: 8
- Photos: 2
- Valuations: 5
- Drafts: 2
- Credentials: 1
- Sales: 4
- Field suggestions: 0
- Image fingerprints: 0

## Validation

Backend:

- `backend\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run` - passed.
- `backend\.venv\Scripts\python.exe manage.py check` - passed.
- `backend\.venv\Scripts\python.exe -m pytest -p no:cacheprovider` - passed: 118 passed, 1 skipped.

Frontend:

- `npm run test` - passed: 66 tests.
- `npm run typecheck` - passed.
- `npm run build` - passed.

Static:

- `backend\.venv\Scripts\python.exe manage.py collectstatic --noinput` - passed.

Backup:

- Post-migration encrypted backup succeeded.
- Restore spot-check succeeded and included Sprint 13 schema.

## Live Service Verification

After migration and `collectstatic`, the `Magpie` NSSM service was restarted.

Verified:

- `Get-Service Magpie` showed `Running`.
- Waitress listened on `0.0.0.0:8000`.
- `http://localhost:8000/api/health/` returned `200` with `{"status":"ok"}`.
- `http://localhost:8000` served the built SPA.
- `http://192.168.1.86:8000/api/health/` returned `200` with `{"status":"ok"}`.
- `http://192.168.1.86:8000` served the built SPA.

## Browser Evidence

Screenshots:

- `docs/evidence/sprint13-item-detail-desktop.png`
- `docs/evidence/sprint13-item-detail-phone.png`

The evidence script opened a real item detail page through the running service and verified:

- Sold-search panel present.
- Suggested-fields panel present.
- Human-in-the-loop copy present.
- 7 eBay sold-search links rendered.
- All sold-search links open in new tabs.
- All sold-search links target `https://www.ebay.com.au/sch/i.html`.
- All sold-search links include `LH_Sold=1` and `LH_Complete=1`.
- OCR and duplicate-scan buttons are present.
- No broken panel text was present.

Evidence item:

- SKU: `COIN-00001`
- Title: `Seed/example coin - 1937 Australian Crown`

## Human-In-The-Loop Guarantee

Test coverage proves:

- OCR stages `FieldSuggestion` rows and does not mutate item attributes.
- Approve writes the proposed value.
- Edit writes the human-edited value.
- Reject leaves item data unchanged.
- Duplicate-image detection stages candidate review rows and never merges items.
- The UI does not call approve/edit/reject until the user explicitly clicks an action.

Live evidence did not perform any approve/edit/reject action and left all staged counts at zero.

## Remote Validation

Pending final commit and push.
