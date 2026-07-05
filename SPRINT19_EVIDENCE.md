# Sprint 19 Evidence

Date: 2026-07-05

Head at implementation start: `efc46fe`.

## Implemented

- Descriptor-based evidence lookup:
  - query by category, key terms, and simple attributes
  - exact own `SaleRecord` matches rank first
  - similar own `SaleRecord` matches rank second
  - approved/manual `Comparable` rows rank third
  - match reasons are deterministic strings such as same category, matched terms, or same descriptor attribute
  - no AI scoring, opaque similarity score, scraping, eBay API usage, or marketplace fetching
- Known-basis-only stats:
  - canonical basis is `seller_receives`
  - low / median / high / count / newest age use only rows with a confident seller-receives basis
  - unknown-basis rows remain visible as basis-uncertain and are excluded from precise stats
- Evidence panel:
  - added to `/buy-calculator`
  - added to item detail
  - mobile panel defaults collapsed by viewport match
  - “Use this” applies a known-basis evidence price to the calculator and updates the source label
- Fast-capture v2:
  - starts from the open descriptor lookup
  - category and terms are carried into the saved row
  - price is human-entered
  - basis quick-pick defaults to `unknown`
  - source, date, link, and note are captured
  - saved row is an approved/manual `Comparable`
  - the same lookup refreshes immediately after capture
- Bought-it flow:
  - creates an `InventoryItem` from the calculator context
  - `acquisition_cost` equals the agreed buy price
  - category/descriptors are carried into the item
  - notes record the calculator context
  - no evidence rows, listing drafts, publications, or sales are created
- Folded Sprint 18 polish:
  - `/buy-calculator` respects top safe-area inset
  - shared formula parity fixture added for backend and frontend
  - canonical `$76.92` free-selling case asserted in backend and frontend
  - Pro Starter case asserted
  - BPF breakpoint round-trip case asserted

## Additive Migration

- `research.0004_comparable_descriptor_lookup`
  - makes `Comparable.item` nullable so descriptor-captured comps can exist before an item is bought
  - adds `descriptor_category`
  - adds `descriptor_terms`
  - adds `descriptor_attributes`
  - adds descriptor-category index

Migration consistency:

- `python manage.py makemigrations --check --dry-run`
- Result: no changes detected

## Backup / Restore

Pre-migration encrypted backup:

- `backend/backups/magpie-backup-20260705-090602.tar.gz.enc`

Live migration status:

- `Magpie` was stopped by Administrator PowerShell before migration.
- `python manage.py migrate`
- Result: `Applying research.0004_comparable_descriptor_lookup... OK`

Post-migration encrypted backup:

- `backend/backups/magpie-backup-20260705-091850.tar.gz.enc`

Restore spot-check target:

- `backend/.tmp/sprint19-restore-check`

Restore spot-check confirmed:

- `research_comparable.descriptor_category_id` exists
- `research_comparable.descriptor_terms` exists
- `research_comparable.descriptor_attributes` exists
- descriptor-category index exists

Restored row counts included:

- items: 8
- photos: 2
- comparables: 4
- valuations: 5
- drafts: 2
- sales: 4
- eBay staging: 4
- credential present

## Validation

Backend focused:

- `python -m pytest apps/profit/tests/test_sprint19.py apps/profit/tests/test_sprint18.py -q`
- Result: 24 passed

Backend focused with pricing evidence:

- `python -m pytest apps/profit/tests/test_sprint19.py apps/profit/tests/test_sprint18.py apps/research/tests/test_sprint14.py -q`
- Result: 30 passed

Backend full:

- `python -m pytest -q`
- Result: 162 passed, 1 skipped

Frontend focused:

- `npm run test -- BuyCalculator.test.tsx`
- Result: 8 passed

Frontend full:

- `npm run test`
- Result: 26 files passed, 88 tests passed

Typecheck:

- `npm run typecheck`
- Result: passed

Build:

- `npm run build`
- Result: passed; production bundle built in `frontend/dist`

Collectstatic:

- `python manage.py collectstatic --noinput`
- Result: 7 files copied, 155 unmodified, 425 post-processed

## Test Coverage Added

- descriptor lookup ranking exact own sale → similar own sale → approved comparable
- known-basis-only stats
- unknown-basis exclusion from precise low / median / high
- unknown-basis rows visible as basis-uncertain
- fast capture creates a source-tagged `Comparable`
- fast capture refreshes the same lookup payload
- bought-it item creation
- bought-it does not create `Comparable` or `SaleRecord`
- lookup transience: no persisted lookup history
- Sprint 18 what-if non-persistence
- backend/frontend shared formula parity fixture
- canonical `$76.92` free-selling case
- Pro Starter fee case
- BPF breakpoint round-trip
- descriptor evidence path no external network call tokens

## Scope Guard

- No AI in the evidence path.
- No scraping.
- No new eBay API usage.
- No new network calls.
- No persisted lookup history.
- What-if inputs remain non-persistent.
- Unknown-basis Sprint 18 behaviour preserved.
- No secrets printed or committed.

## Live Service Proof

Administrator PowerShell restart proof supplied by Regan:

- `Get-Service -Name Magpie` returned `Running`
- `sc.exe queryex Magpie` returned `STATE RUNNING` with a non-zero PID
- `/api/health/` returned 200 OK

Shell proof after restart:

- `Invoke-WebRequest http://127.0.0.1:8000/api/health/`
- Result: `200 {"status":"ok"}`
- `Invoke-WebRequest http://127.0.0.1:8000/buy-calculator`
- Result: 200

Live authenticated descriptor API proof:

- Authenticated lookup for Stamps + `First Flight`
- Result: `status=200`, `rows=3`, `median=1.00`, `count=3`, `strength=THIN`, `transient=True`

Live UI proof:

- Phone-width lookup/use-this/verdict screenshot:
  - `evidence/sprint19/phone-lookup-use-this-verdict.png`
  - Descriptor lookup shows own-sale rows first for `First Flight`
  - Strength/freshness displayed: `THIN`, `n = 3`, newest age
  - One-tap `Use this` applied the own-sale evidence price
  - Calculator verdict updated to `BUY`
- Phone-width capture round-trip screenshot:
  - `evidence/sprint19/phone-capture-round-trip.png`
  - A clearly temporary UI-validation comp was captured from the open lookup
  - Basis defaulted to `unknown`
  - The row appeared immediately as basis-uncertain
  - Precise stats stayed at known-basis count `3`
- Desktop screenshot:
  - `evidence/sprint19/desktop-buy-calculator-evidence.png`

Temporary validation cleanup:

- Temporary comparable source `Sprint 19 temporary UI validation comp` was deleted after screenshot proof
- Temporary staff user `sprint19_ui_validation` was deleted after screenshot proof
- Final live counts after cleanup:
  - items: 8
  - photos: 2
  - comparables: 4
  - valuations: 5
  - drafts: 2
  - sales: 4
  - eBay staging: 4
  - AI credentials: 1
  - temporary validation users: 0

User-supplied mobile what-if proof:

- Phone screen showed canonical Sprint 18/19 case:
  - Max Buy Price: `$76.92`
  - Verdict: `BUY`
  - Expected profit at asking: `$40.00`
  - ROI at asking: `66.67%`
  - Seller fees: `$0.00`
  - Non-buy costs: `$0.00`
  - ROI basis: all-in cash
  - Source: what-if

Remote Validation:

- Commit: `cc291e8e5e6fee35b0f0382624bf02a1c5e6f4ee`
- GitHub `Validation`: success
- Run: https://github.com/GoldDiggerTriangle/magpie/actions/runs/28736480903
