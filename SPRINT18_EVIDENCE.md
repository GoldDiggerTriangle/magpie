# Sprint 18 Evidence

Date: 2026-07-03

Head: `cf1b35e` at implementation start.

## Implemented

- Added 2026 eBay AU fee model support:
  - seller-mode setting defaults to `free_selling`
  - Buyer Protection Fee forward formula
  - exact piecewise inverse from buyer-visible total to seller price
  - fee preview endpoint
  - FeeSchedule 2026 metadata fields
  - Comparable `price_basis`
  - canonical seller-receives normalization for pricing evidence
  - unknown-basis rows remain visible but excluded from precise low/median/high math
- Added Buy Calculator v1:
  - mobile-first `/buy-calculator` page
  - Max Buy / Max Bid mode
  - flat profit target
  - ROI target with all-in cash default and on-buy-price option
  - BUY / MAYBE / PASS verdict
  - expected profit and ROI at asking
  - own-sales / approved-comp evidence lookup only
  - what-if inputs labelled as user estimates and not persisted as evidence
- Added Settings profit-engine section:
  - seller mode
  - Pro/manual fee settings
  - default ROI / flat profit / maybe-band settings

## Additive Migrations

- `profit.0001_initial`
- `research.0003_comparable_price_basis`
- `valuation.0003_feeschedule_2026_mode_fields`

Live SQLite migrations applied successfully on 2026-07-03.

## Backup / Restore

Pre-migration encrypted backup:

- `backend/backups/magpie-backup-20260702-211136.tar.gz.enc`

Post-migration encrypted backup:

- `backend/backups/magpie-backup-20260702-211212.tar.gz.enc`

Restore spot-check target:

- `backend/.tmp/sprint18-restore-check`

Restore spot-check confirmed:

- `profit_profitsetting` table exists
- `research_comparable.price_basis` exists
- `valuation_feeschedule.seller_mode` exists
- `valuation_feeschedule.price_basis` exists
- `valuation_feeschedule.buyer_protection_fee_enabled` exists
- `valuation_feeschedule.international_delivery_pct` exists

Restored row counts included:

- items: 8
- photos: 2
- comparables: 4
- valuations: 5
- drafts: 2
- sales: 4
- eBay staging: 4
- credentials: 1

## Validation

Backend:

- `python -m pytest -q`
- Result: 155 passed, 1 skipped

Focused backend Sprint 18/pricing evidence:

- `python -m pytest apps/profit/tests/test_sprint18.py apps/research/tests/test_sprint14.py -q`
- Result: 23 passed

Frontend:

- `npm run test`
- Result: 82 passed

Typecheck:

- `npm run typecheck`
- Result: passed

Build:

- `npm run build`
- Result: passed

Remote Validation:

- GitHub Actions `Validation` run `28622061121`
- Commit: `df54de0`
- Result: success

Collectstatic:

- `python manage.py collectstatic --noinput`
- Result: 7 files copied, 155 unmodified, 424 post-processed

Migration check:

- `python manage.py makemigrations --check --dry-run`
- Result: no changes detected

## Formula Coverage

Tests cover:

- BPF breakpoints at 20, 500, and 5000
- BPF cap above 5000
- exact inverse round-trips from seller price to buyer-visible total and back
- free-selling vs Pro Starter fee behavior
- ROI all-in cash formula
- ROI on-buy-price formula
- zero-cost equivalence of ROI formulas
- BUY / MAYBE / PASS verdict bands
- what-if calculator inputs do not create Comparable or SaleRecord rows
- evidence lookup prefers exact own sales and excludes unknown-basis comps from precise calculator math

## Live Service Status

Live database:

- migrated
- post-migration backup succeeded
- restore spot-check succeeded

Live service:

- `Magpie` service is still running
- `/api/health/` returns 200
- SPA route `/buy-calculator` serves the rebuilt bundle `index-BAwE9O8e.js`
- new API routes still 404 until the service process is restarted:
  - `/api/buy-calculator/evidence/`
  - `/api/profit/settings/`

Restart attempt:

- NSSM service stop was denied by Windows service permissions
- direct kill of the port-8000 Python process was denied by Windows process permissions

Open operational gate:

- Administrator restart of `Magpie` is required.
- After restart, verify:
  - `/api/health/` 200
  - `/api/profit/settings/` 200
  - `/api/buy-calculator/evidence/` 200 when authenticated
  - `/buy-calculator` renders the calculator UI
  - LAN access still works
  - mobile screenshot around 390px width
  - desktop screenshot

## Scope Guard

- No AI-produced price numbers.
- No scraping.
- No new eBay API calls.
- No new network calls from Magpie.
- What-if calculator values are not persisted as evidence.
- Unknown-basis comps are visibly labelled and excluded from precise normalized math.

## Closure Bug Follow-Up: Buy Calculator Auth Block

Date: 2026-07-05

User-reported live failure:

- `/buy-calculator` route loaded after service restart.
- Typed what-if input did not calculate.
- Result panel stayed at "Enter a sell price".
- Red error showed "Authentication credentials were not provided."

Confirmed failing request:

- `POST /api/buy-calculator/calculate/`
- Unauthenticated shell response: `403 {"detail":"Authentication credentials were not provided."}`
- `GET /api/profit/settings/` and `GET /api/buy-calculator/evidence/` are active routes, but also return `403` without an authenticated app session under the global DRF auth policy.

Fix implemented:

- The `/buy-calculator` page now performs typed what-if calculation locally in the frontend using the Sprint 18 fee/ROI formulas.
- Authenticated evidence/settings lookup still uses the existing shared API client with `credentials: "include"`.
- If saved evidence/settings lookup fails auth, the evidence panel explains that Django admin sign-in is required for saved evidence while typed what-if calculations still work.
- No backend schema, migration, eBay API call, scraping, AI pricing, or persistence change was added.

Exact regression proof:

- Frontend test added for the reported input:
  - expected sell price: `100`
  - price basis: `seller_receives`
  - seller mode: `free_selling`
  - asking price: `60`
  - postage/packaging/refurb: `0`
  - mode: Max Buy
  - ROI target: `30`
  - ROI basis: all-in cash
- Expected and asserted result: `$76.92` Max Buy and `BUY`.
- The same test forces item/evidence lookups to fail with "Authentication credentials were not provided." and confirms the typed what-if calculation still renders.

Follow-up validation:

- `npm run test -- BuyCalculator`: 4 passed.
- `npm run test`: 26 files passed, 83 tests passed.
- `npm run typecheck`: passed.
- `npm run build`: passed; generated `index-CwMlbq2l.js` / `index-CC9TAzak.css`.
- `python -m pytest apps/profit/tests/test_sprint18.py -q`: 17 passed.
- `python manage.py collectstatic --noinput`: 7 files copied, 155 unmodified, 425 post-processed.
- `/api/health/`: 200.

Live deployment state after fix:

- The running service served the rebuilt `/buy-calculator` index pointing at `index-CwMlbq2l.js`.
- The running Waitress/WhiteNoise process still served the previous asset map until restart:
  - previous bundle `index-BAwE9O8e.js`: 200
  - new bundle `index-CwMlbq2l.js`: 404 before restart
- NSSM restart from this non-elevated shell failed:
  - `OpenService(): Access is denied.`
- Administrator restart of `Magpie` is required before final live-browser proof.

Remaining open closure gate:

- Restart `Magpie` from Administrator PowerShell.
- Re-check that `/assets/index-CwMlbq2l.js` returns 200.
- In the live browser UI, enter the exact reported values and confirm `$76.92` and `BUY`.
- Confirm authenticated sessions can access `/api/profit/settings/` and `/api/buy-calculator/evidence/`.
- Capture the required mobile proof screenshot.

Sprint 18 remains not live-closed until the post-restart browser proof succeeds.
