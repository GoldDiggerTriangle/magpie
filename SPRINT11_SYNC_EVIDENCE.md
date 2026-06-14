# Sprint 11 Sync Evidence

Date: 2026-06-14

Status: implementation evidence captured; production eBay validation remains pending.

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
- Sync uses a 90-day first window, then a stored watermark with lookback overlap.
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
- Remote GitHub Validation for this final pushed commit is pending until commit/push completes.

## Runtime Data Safety

Secret-free live row-count check from the runtime SQLite database after Sprint 11 schema work:

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

Not yet executed in this implementation pass.

Still required with Regan present:

- complete incremental paste-back re-consent for the expanded scopes;
- prove real `getOrders` access;
- prove real `getTransactions` access;
- run a real manual sync;
- confirm real unmatched history imports into the staging queue;
- confirm the real audit entries remain secret-free.

The matched Magpie-SKU production path remains fake-validated only, as required by the spec. No fake real matched sale was engineered.

## Closure Status

Sprint 11 implementation and fake-backed CI evidence are ready for commit/push. Sprint 11 is not formally closable until the production validation section above is completed and recorded.
