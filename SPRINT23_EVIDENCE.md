# Sprint 23 Evidence - Photo Source Choice, Banknotes, and Denomination Data

Status: live deployment complete pending final remote GitHub `Validation` result during closure.

## Scope Implemented

- Add Item and item-edit photo upload now expose two explicit actions:
  - `Take photo` uses `capture="environment"`.
  - `Choose from library` has no `capture` attribute and supports `multiple`.
- Both camera and library uploads flow through the same existing server-side image pipeline.
- GPS EXIF stripping is explicitly tested for library-style images before storage and before the AI/cloud send path.
- Added `Banknotes` as a real category with profile key `banknotes` and SKU prefix `NOTE`.
- Added curated Banknotes schema:
  - `country`
  - `denomination`
  - `series_year`
  - `prefix_serial`
  - `signature_variety`
  - `catalogue_refs` using the existing candidate-only repeater pattern with `Pick`, `Renniks`, `McDonald`, and `other`
  - `notes`
- Condition remains the existing global item field.
- Banknotes are wired through:
  - descriptor evidence lookup
  - eBay sold-search builder
  - multi-source pricing/source links
  - copy-pack rendering
  - AI identify field scope
- Denomination suggestions are data-driven from `backend/apps/catalog/denominations.json`.
- Denomination remains stored as plain text; custom values are allowed by the frontend combobox and backend schema.

## Migration

- Added migration:
  - `backend/apps/catalog/migrations/0003_add_banknotes_category.py`
- Live migration applied:
  - `python manage.py migrate`
  - Result: `Applying catalog.0003_add_banknotes_category... OK`.
- No existing item data was migrated or recategorised.

## Safety

- No new AI paths.
- No generated values.
- No scraping.
- No new eBay API calls.
- No new network/API dependency.
- No GPS/location metadata survives the upload pipeline.
- Catalogue references remain candidate/manual fields; no generated catalogue values are treated as authoritative.
- Category schema and denomination suggestions are data/config-driven.

## Validation

- Focused backend Sprint 23/photo tests:
  - `python -m pytest apps/catalog/tests/test_sprint23.py apps/photos/tests/test_sprint1.py -q`
  - Result: `10 passed`.
- Full backend suite:
  - `python -m pytest -q`
  - Result: `193 passed, 1 skipped`.
- Focused frontend tests:
  - `npm run test -- --run src/features/capture/AddItem.test.tsx src/features/inventory/ItemDetail.test.tsx src/components/SchemaFieldsForm.test.tsx`
  - Result: `10 passed`.
- Full frontend suite:
  - `npm run test`
  - Result: `100 passed`.
- Typecheck:
  - `npm run typecheck`
  - Result: passed.
- Build:
  - `npm run build`
  - Result: passed.
- collectstatic:
  - `python manage.py collectstatic --noinput`
  - Result: `7 static files copied`, `155 unmodified`, `425 post-processed`.
- Built asset hardcoded-localhost check:
  - `rg "localhost:8000|127\.0\.0\.1:8000|http://localhost|https://localhost" frontend/dist backend/staticfiles`
  - Result: no matches.
- Migration check:
  - `python manage.py makemigrations --check --dry-run`
  - Result: `No changes detected`.

## Backup and Restore

- Pre-migration encrypted backup:
  - `backend/backups/magpie-backup-20260706-035103.tar.gz.enc`.
- Post-migration encrypted backup:
  - `backend/backups/magpie-backup-20260706-035132.tar.gz.enc`.
- Restore spot-check performed against the post-migration backup:
  - `python manage.py restore backups\magpie-backup-20260706-035132.tar.gz.enc --target tmp\sprint23-restore --force`
  - Restore counts included:
    - `items=8`
    - `photos=2`
    - `comparables=4`
    - `valuations=5`
    - `drafts=2`
    - `sales=4`
    - `ebay_staging=4`
    - `field_suggestions=2`
    - `ai_credentials=1`
    - `credential=1`
- Restored database spot-check:
  - `catalog_productcategory` contains `('Banknotes', 'NOTE', 'banknotes')`.
- Temporary restore directory removed after spot-check.

## Live Deployment

- Magpie was running before live migration.
- Non-admin service stop attempt from this session was denied by Windows:
  - `sc.exe stop Magpie` -> `Access is denied.`
- Because the Sprint 23 migration is an additive category data insert, the live migration was applied with the pre-migration backup already in place.
- Administrator service restart performed after build/collectstatic.
- Service health after restart:
  - `sc.exe queryex Magpie`: `RUNNING` with non-zero PID.
  - `GET http://localhost:8000/api/health/`: `{"status":"ok"}`.
  - `GET http://localhost:8000/`: `200`.
- Served SPA asset verified:
  - `http://127.0.0.1:8000/assets/index-CCNciJzl.js`.
- Live UI screenshots were captured from a clean temporary phone-width Chrome profile against the restarted service. A short-lived local Django session was used only for read-only UI proof; no item was saved.

## Live UI Evidence

- Phone screenshot, photo chooser with `Take photo` and `Choose from library`:
  - `evidence/sprint23/phone-photo-source-choice.png`.
  - DOM proof from the live app:
    - `Take photo`: `accept="image/*"`, `capture="environment"`, `multiple=false`.
    - `Choose from library`: `accept="image/*"`, no `capture` attribute, `multiple=true`.
- Phone screenshot, Banknotes form with denomination combobox:
  - `evidence/sprint23/phone-banknotes-denomination-form.png`.
  - The live form selected `Banknotes`, displayed the curated fields, and accepted custom denomination text `Ten shillings` without saving an item.
  - DOM proof from the live app showed the data-driven denomination list:
    - `$1`, `$2`, `$5`, `$10`, `$20`, `$50`, `$100`, `1 pound`, `5 pounds`, `10 shillings`, `10 dollars`, `20 dollars`, `50 dollars`, `100 dollars`.
- Candidates-only catalogue reference proof:
  - The live Banknotes form showed the `Catalogue refs` repeater with the text `Candidate references only; confirm manually before relying on them.`
- GPS EXIF stripping proof: covered by backend test `test_library_gps_exif_is_stripped_before_storage_and_ai_send_path`.

## Remote Validation

- GitHub `Validation` run: pending final closure update.
