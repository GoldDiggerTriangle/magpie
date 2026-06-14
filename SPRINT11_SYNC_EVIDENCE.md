# Sprint 11 Sync Evidence

Date: 2026-06-14

Status: implementation, CI, and production eBay validation complete.

## Scope Implemented

- eBay own-order sync is manual-trigger only.
- eBay calls are read-only for Sprint 11 order sync:
  - Fulfillment `GET /sell/fulfillment/v1/order`
  - Finances `GET /sell/finances/v1/transaction`
- HTTP adapter code is confined to `backend/apps/ebay/adapters.py`; `backend/integrations/ebay.py` is now a compatibility shim.
- Existing paste-back OAuth flow now requests the expanded order-sync scopes and reports missing scopes as re-consent-required.
- Order sync imports into Sprint 10 `SaleRecord`.
- Matched SKU path creates `SaleRecord(provenance=ebay_sync)`.
- Unmatched SKU path creates `EbayOrderStaging(pending)`.
- Staging supports link, quick-create, and mark-external resolution.
- Duplicate candidates are flagged in `EbayOrderDuplicateCandidate`; they are not auto-created or auto-merged.
- External sales can be accepted without an item and carry `cost_basis_unknown=True`; realised profit remains null.
- Sync uses a 90-day default first window, then a stored watermark with lookback overlap.
- Production validation used the approved 365-day bounded first-sync override.
- Idempotency is keyed by eBay order ID plus line item ID across sale records, staging rows, and duplicate candidates.
- Finances transaction ID is captured when an authoritative line-level join exists.
- Conservative fee mapping is implemented:
  - if a Finance transaction cannot be confidently joined to one order line, the raw finance snapshot is retained;
  - `fee_status=estimated_or_unmapped` is set;
  - the UI surfaces review-needed fee rows;
  - uncertain fees are not treated as authoritative.

## Scope Verification

Official eBay documentation was checked before locking the OAuth scope list.

- eBay OAuth guidance says method access depends on the scopes included in the generated user token, and adding a new scope to an existing user token requires a new permission grant: https://developer.ebay.com/develop/guides-v2/authorization
- Fulfillment OpenAPI for `getOrders` lists both `https://api.ebay.com/oauth/api_scope/sell.fulfillment` and `https://api.ebay.com/oauth/api_scope/sell.fulfillment.readonly`; Sprint 11 uses the read-only scope: https://developer.ebay.com/api-docs/master/sell/fulfillment/openapi/3/sell_fulfillment_v1_oas3.json
- Finances `getTransactions` requires `https://api.ebay.com/oauth/api_scope/sell.finances`; the current official docs do not list a separate `sell.finances.readonly` scope for this method: https://developer.ebay.com/api-docs/sell/finances/resources/transaction/methods/getTransactions
- Fulfillment `getOrders` can retrieve orders up to two years old, so a 365-day first-sync window is supported.
- Finances `getTransactions` can retrieve transactions from the last five years, and the `transactionDate` filter supports a maximum range of 36 months, so a 365-day first-sync window is supported.
- Finances `getTransactions` uses the `apiz.ebay.com` root URI, not the normal `api.ebay.com` root URI.
- Both real order-sync adapters now format date filters as UTC `YYYY-MM-DDTHH:MM:SS.000Z`.

Implemented scope list:

- `https://api.ebay.com/oauth/api_scope/sell.inventory`
- `https://api.ebay.com/oauth/api_scope/sell.account.readonly`
- `https://api.ebay.com/oauth/api_scope/sell.fulfillment.readonly`
- `https://api.ebay.com/oauth/api_scope/sell.finances`

## Migrations

- `backend/apps/sales/migrations/0002_salerecord_channel_data_and_more.py`
  - nullable `SaleRecord.item`
  - external/cost-basis flags
  - eBay order, line, transaction identity fields
  - `fee_status`
  - `channel_data`
  - eBay order-line uniqueness guard
- `backend/apps/ebay/migrations/0003_ebayordersyncstate_ebayorderduplicatecandidate_and_more.py`
  - `EbayOrderSyncState`
  - `EbayOrderStaging`
  - `EbayOrderDuplicateCandidate`

## Automated Evidence

Backend:

- `python manage.py check`
  - passed
- `python manage.py makemigrations --check --dry-run --noinput`
  - passed, no changes detected
- `python -m pytest`
  - passed: 108 passed, 1 skipped
- Focused eBay regression after production-validation adapter fixes:
  - `python -m pytest apps/ebay/tests/test_sprint11.py apps/ebay/tests/test_sprint6.py`
  - passed: 27 passed, 1 skipped

Sprint 11 fake-backed coverage includes:

- matched SKU import creates `SaleRecord(provenance=ebay_sync)`
- partial quantity sync updates remaining quantity and status
- valuation and fee snapshots are captured at sale time
- local listing state is updated without writing to eBay
- idempotent re-sync does not duplicate sale records or staging rows
- unmatched SKU imports to staging
- staging resolves by link, quick-create, and mark-external
- external cost-basis-unknown sale has null realised profit
- duplicate candidate is flagged instead of auto-created or auto-merged
- insufficient old scopes trigger re-consent requirement
- manual API trigger and staging resolution endpoints work
- Sprint 8 encrypted backup includes the new staging and duplicate tables
- audit payloads remain secret-free
- 90-day first window and watermark/lookback behavior are exercised
- conservative Finance joins keep matched and unmatched uncertain fees as `estimated_or_unmapped`

Frontend:

- `npm run test`
  - passed: 18 files, 50 tests
- `npm run typecheck`
  - passed
- `npm run build`
  - passed

Workflow:

- `.github/workflows/postgresql-validation.yml` remains the dual-lane `Validation` workflow.
- SQLite lane now checks the new backup tables.
- eBay HTTP confinement guard now enforces the Sprint 11 boundary at `backend/apps/ebay/adapters.py`.
- Remote GitHub Validation for `04705e0` passed:
  - run: https://github.com/GoldDiggerTriangle/magpie/actions/runs/27492254694
  - sqlite: success
  - postgres: success

## Runtime Data Safety

Secret-free live row-count check from the runtime SQLite database before production sync:

- items: 8
- photos: 2
- valuations: 5
- drafts: 2
- credential: 1
- sales: 0
- eBay staging rows: 0
- eBay duplicate candidates: 0

No fake live sales were created.

## Production Validation

Executed on 2026-06-14 against the production eBay credential and the runtime SQLite database in the service checkout.

Pre-sync checks:

- checkout: `main` at `04705e0` before production validation fixes;
- service backend path: `C:\Users\Regan\Documents\Codex\2026-06-13\reasoning-extra-high-i-approve-sprint-2\backend`;
- production credential existed and was missing the two new order-sync scopes before re-consent;
- baseline counts: 8 items, 2 photos, 5 valuations, 2 drafts, 1 credential, 0 sales, 0 staging rows, 0 duplicate candidates.

Re-consent:

- incremental paste-back re-consent completed with Regan present;
- stored production credential scope count is now 4 of 4 required scopes;
- missing required scope count is 0;
- OAuth URL, OAuth code, tokens, secrets, and credential payloads were not printed or committed.

Production validation findings fixed during the run:

- first real Fulfillment attempt reached eBay and failed with an eBay date-filter validation error;
- fix: send date filters as documented UTC millisecond `Z` timestamps;
- first real Finances attempt then reached the wrong host and returned 404;
- fix: use the documented Finances root `https://apiz.ebay.com` and include `X-EBAY-C-MARKETPLACE-ID`.

Successful 365-day production sync:

- first sync environment: production;
- first sync counts:
  - created: 0
  - staged: 4
  - duplicate-flagged: 0
  - skipped: 0
  - fee authoritative: 4
  - fee estimated or unmapped: 0
- after first sync:
  - sales: 0
  - eBay sync sales: 0
  - staging rows: 4
  - pending staging rows: 4
  - duplicate candidates: 0
- real `getOrders` access succeeded because four real order lines were returned and staged.
- real `getTransactions` access succeeded because all four staged rows received authoritative fee mapping.
- no accepted live sale records were created.
- no fake live sales were created.
- no engineered matched Magpie sale was created.

Idempotency proof:

- second proof pass scanned the same 365-day window;
- second sync counts:
  - created: 0
  - staged: 0
  - duplicate-flagged: 0
  - skipped: 4
  - fee authoritative: 0
  - fee estimated or unmapped: 0
- counts after first and second sync were stable:
  - sales: 0
  - eBay sync sales: 0
  - staging rows: 4
  - pending staging rows: 4
  - duplicate candidates: 0
- sync watermark exists after the production run;
- future overlap lookback was restored to 2 days after the idempotency proof.

Fee mapping:

- staged fee status counts:
  - authoritative: 4
- no uncertain Finances joins appeared in this real run;
- conservative fee handling remains covered by CI fakes for uncertain/unmapped rows.

Audit:

- sync started/completed audit events were recorded;
- failed audit events from the two pre-fix production-validation attempts remain as honest evidence;
- secret marker check across eBay audit payloads found 0 markers.

The matched Magpie-SKU production path remains fake-validated only, as required by the spec. No fake real matched sale was engineered.

## Closure Status

Sprint 11 is formally closable after this evidence is committed and the final Validation workflow is green.
