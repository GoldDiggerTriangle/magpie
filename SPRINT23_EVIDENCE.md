# Sprint 23 Evidence - Photo Source Choice, Banknotes, and Denomination Data

Status: live deployment complete. Sprint 23 implementation was validated locally and by GitHub dual-lane `Validation`; the final closure response records the latest pushed head and run ID.

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

- Remote run for implementation commit `a79177c29ad156e590f357b6708b15070c84acb1`:
  - Run `28767196470`.
  - SQLite job `85293740488`: success.
  - Postgres job `85293740499`: success.

---

# Round 2 Reopen Evidence - iOS Picker Closure Fix

## Scope

- Reopened because the live iPhone edit form showed `Denomination` as a bare text/datalist control with no visible picker affordance.
- Round 2 replaces datalist-only behaviour with a real visible picker pattern:
  - native select
  - visible chevron affordance
  - final `Other / custom...` option
  - custom text input when needed
  - stored value remains plain text
- `Country` now uses the same picker/custom pattern.
- The registry was generalized from denomination-only to per-category/per-field choice lists.

## Implementation

- Added data/config registry:
  - `backend/apps/catalog/field_choices.json`
  - `backend/apps/catalog/field_choices.py`
- Removed the old denomination-only registry:
  - `backend/apps/catalog/denominations.json`
  - `backend/apps/catalog/denominations.py`
- `GET /api/categories/{id}/schema/` now applies configured field choices for any configured category/field pair.
- Banknotes and Coins now include configured `country` and `denomination` lists.
- Live stored values are merged into the suggestions so existing custom data remains visible.
- The shared `SchemaFieldsForm` now renders string fields with suggestions as a native select plus explicit custom entry.
- Add Item and item edit both use the same control through the shared schema form.

## Data/Config Proof

- A test fixture edits only registry JSON to add:
  - a new value for an existing mapped field
  - a new field mapping (`signature_variety`)
- The schema response receives those suggestions without UI or business-logic changes.
- No schema migration was needed:
  - `python manage.py makemigrations --check --dry-run`
  - Result: `No changes detected`.

## Validation

- Focused backend Sprint 23 tests:
  - `python -m pytest apps/catalog/tests/test_sprint23.py -q`
  - Result: `8 passed`.
- Full backend suite:
  - `python -m pytest -q`
  - Result: `194 passed, 1 skipped`.
- Focused frontend picker/parity tests:
  - `npm run test -- --run src/components/SchemaFieldsForm.test.tsx src/features/capture/AddItem.test.tsx src/features/inventory/ItemDetail.test.tsx`
  - Result: `12 passed`.
- Full frontend suite:
  - `npm run test -- --run`
  - Result: `102 passed`.
- Typecheck:
  - `npm run typecheck`
  - Result: passed.
- Build:
  - `npm run build`
  - Result: passed. Existing large chunk warning only.
- collectstatic:
  - `python manage.py collectstatic --noinput`
  - Result: `7 static files copied`, `155 unmodified`, `425 post-processed`.

## Round 1 Regression Coverage

- Photo source choice remains split between `Take photo` and `Choose from library`.
- Library input still has no `capture` attribute and supports `multiple`.
- GPS EXIF stripping remains covered by backend tests.
- Banknotes remain wired through:
  - descriptor evidence lookup
  - sold-search building
  - pricing/source links
  - copy packs
  - AI identify curated field scope
- Catalogue refs remain candidate/manual fields.

## Remaining Live Closure Gates

- Administrator restart is required before the running service can prove the new backend schema metadata and rebuilt SPA.
- Sprint 23 Round 2 is not reclosed until real iPhone screenshots show the picker open on-device:
  - Denomination picker open on Add Item.
  - Denomination picker open on item edit.
  - Country picker open on Add Item.
  - Country picker open on item edit.
- Selection save and custom-entry save are test-proven locally, but live iPhone proof remains pending.

## Round 2 Live Closure Proof

- Administrator restart completed after Round 2 commit `fab6a529e9c511356a087d9419439398cc2c930c`.
- Live health check:
  - `/api/health/` returned `200`.
- iPhone loaded the updated app with cache-buster `?v=fab6a52`.
- Real iPhone picker-open proof captured:
  - Add Item, Country picker open: `evidence/sprint23/round2-add-country-picker-open.jpg`.
  - Add Item, Denomination picker open: `evidence/sprint23/round2-add-denomination-picker-open.jpg`.
  - Item edit, Country picker open: `evidence/sprint23/round2-edit-country-picker-open.jpg`.
  - Item edit, Denomination picker open: `evidence/sprint23/round2-edit-denomination-picker-open.jpg`.
- The screenshots prove the updated native picker opens on the real device for both Add Item and item edit.
- Selection save and custom entry save remain covered by frontend tests:
  - `AddItem saves banknote picker selections and custom country values`.
  - `ItemDetail edit saves banknote picker selections and custom country values`.

## Country List Cleanup

- After the picker-open proof, Regan requested country names only in the dropdown, not duplicate code/name entries such as `CA` and `Canada`.
- The field-choice registry was updated to remove country-code aliases from Banknotes and Coins.
- Country values now use names such as `Australia`, `Canada`, `United States`, `United Kingdom`, and `New Zealand`.
- Custom country entry remains available for defunct or non-standard issuers such as `Rhodesia`.
- This was a data/config-only cleanup; no schema migration was needed.

## Round 2 Remote Validation

- Remote Validation run for Round 2 implementation commit `fab6a529e9c511356a087d9419439398cc2c930c`:
  - Run `28768627315`.
  - Postgres job: success.
  - SQLite job: success.

## Round 2 Closure Status

- Sprint 23 Round 2 acceptance gate is satisfied:
  - real iPhone Denomination picker open on Add Item: proven
  - real iPhone Denomination picker open on item edit: proven
  - real iPhone Country picker open on Add Item: proven
  - real iPhone Country picker open on item edit: proven
  - selection save: test-proven
  - custom entry save: test-proven
  - Round 1 regressions: test-proven
- Sprint 23 Round 2 is formally reclosed.
