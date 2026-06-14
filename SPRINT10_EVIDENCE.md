# Sprint 10 Evidence

Date: 2026-06-14

Runtime checkout:

`C:\Users\Regan\Documents\Codex\2026-06-13\reasoning-extra-high-i-approve-sprint-2`

## Implementation Summary

- Added `InventoryItem.quantity_total` with default `1`.
- Added derived `quantity_sold` and `quantity_remaining` from active, non-superseded sale records.
- Added lifecycle status `partially_sold` to the existing `InventoryItem.status` field.
- Added `apps.sales` with `SaleRecord` as the append/correct source of record.
- Added sale snapshots for current valuation and estimated fees at sale time.
- Added Decimal two-decimal money rounding for net proceeds, allocated cost basis, and realised profit.
- Added proportional cost-basis allocation from item acquisition cost and quantity, plus per-sale override.
- Added transactional sale creation/correction with item status recomputed in the same transaction.
- Added DRF endpoints for global sales, item sales, and correction-as-new-row.
- Added manual sale entry, item sale history, correction UI, and a minimal global sales history page.
- Added backup coverage for `sales_salerecord`.

## Migrations

- `backend/apps/inventory/migrations/0003_inventoryitem_quantity_total_and_more.py`
  - Adds `quantity_total`.
  - Adds `partially_sold` to status choices.
- `backend/apps/sales/migrations/0001_initial.py`
  - Creates `sales_salerecord`.
  - Adds indexes for item/date, channel, provenance, and correction lineage.

Migration drift check:

- `python manage.py makemigrations --check --dry-run --noinput`: PASS, no changes detected.
- `python manage.py check`: PASS, no issues.

## Backend Tests

Local SQLite validation with isolated temp database:

- `python -m pytest backend --basetemp .tmp\pytest-backend-sprint10`
- Result: `98 passed, 1 skipped`.

Focused Sprint 10 backend coverage:

- Partial sale lifecycle: qty 10, sell 3 -> remaining 7 and `partially_sold`; sell remaining -> `sold`; oversell rejected.
- Corrections: new row points at `corrected_from`; superseded row remains auditable; only active rows count quantity and profit.
- Cost basis: proportional allocation rounds to cents; override wins.
- Snapshots: valuation and estimated-fee snapshots remain stable after later valuation/fee changes.
- API: item-scoped create/list and global correction endpoint.
- Backup/restore: encrypted archive includes `sales_salerecord` and restored sales row.

## Frontend Tests

- `npm run typecheck`: PASS.
- `npm run test`: PASS, `49 passed` across `18` files.
- `npm run build`: PASS.

Sprint 10 frontend coverage:

- Sales API wrapper uses relative same-origin `/api/...` endpoints.
- Manual sale panel posts sale records with fee prefill and cost-basis preview.
- Correction UI calls the correction endpoint instead of editing the original row.
- Inventory cards/detail surfaces show quantity remaining and `partially_sold`.

Production build API-origin check:

- Built bundle scan for `localhost:8000`, `127.0.0.1:8000`, and `192.168.1.86:8000`: PASS, no matches.

## Production Smoke

Isolated local production smoke:

- Built frontend with Vite.
- Migrated a temp SQLite database.
- Ran `collectstatic` into `backend/staticfiles`.
- Ran `scripts/production_smoke.py` on isolated local port `8766`.
- Result: PASS, Waitress/WhiteNoise served `/`, deep link, `/admin/login/`, static asset, `/api/health/`; unlisted Host was rejected.

## Backup And Restore Proof

Local proof:

- Full backend test suite includes `test_backup_restore_includes_sales_table`.
- That test creates a sale, runs encrypted backup, restores to a clean target, and verifies `sales_salerecord` exists with the restored sale row.

CI proof added:

- `.github/workflows/postgresql-validation.yml` SQLite backup/restore step now asserts:
  - `count_key_rows(restored_db)["sales"] == 0` for seeded CI data.
  - `select count(*) from sales_salerecord` succeeds after restore.

## Live Runtime Data Safety

No Sprint 10 migrations were applied to the live NSSM runtime database during implementation.
Live deployment happened later as a deliberate service deployment after a fresh encrypted backup.

Read-only live data check after implementation:

| Runtime checkout | Items | Photos | Valuations | Drafts | Credential | Media files |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Sprint 9 service checkout | 8 | 2 | 5 | 2 | 1 | 6 |

Service health after implementation:

- `http://localhost:8000/api/health/`: 200, `{"status":"ok"}`.

This confirms the reconciled Sprint 8 business data was not damaged by Sprint 10 implementation/testing.

## Live Deployment

Deployment date: 2026-06-14.

Runtime checkout:

`C:\Users\Regan\Documents\Codex\2026-06-13\reasoning-extra-high-i-approve-sprint-2`

Deployment head:

- `80d1be7` (`Make backups tolerate pre-migration sales tables`).
- GitHub Actions `Validation` for `80d1be7`: PASS, https://github.com/GoldDiggerTriangle/magpie/actions/runs/27486793983.

Pre-migration backup:

- Archive: `magpie-backup-20260614-031153.tar.gz.enc`.
- Result: PASS, encrypted archive created before touching the live database.
- Deployment fix: backup row-count collection now tolerates newly added app tables that are not yet migrated, so pre-migration backups can still run safely.

Live migration:

- `inventory.0003_inventoryitem_quantity_total_and_more`: applied.
- `sales.0001_initial`: applied.

Build/static/service:

- `npm run build`: PASS.
- `python manage.py collectstatic --noinput`: PASS.
- `Magpie` NSSM service: running after Administrator start.
- Port `0.0.0.0:8000`: listening on PID `13656`.

HTTP verification:

- `http://localhost:8000/api/health/`: 200, `{"status":"ok"}`.
- `http://localhost:8000/`: 200, built SPA index for `Gold, Stamps & Phonetech`.
- `http://localhost:8000/sales`: 200, built SPA deep-link route.
- `http://192.168.1.86:8000/`: 200, built SPA index from the LAN URL.
- `http://localhost:8000/api/sales/`: endpoint present; unauthenticated shell request returned 403 rather than 404, as expected for session-protected API access.

Post-migration live data:

| Items | Photos | Valuations | Drafts | Sales | Credential |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 8 | 2 | 5 | 2 | 0 | 1 |

Quantity defaults:

- Existing item count: 8.
- `quantity_total` minimum: 1.
- `quantity_total` maximum: 1.
- Items with `quantity_total=1`: 8.

Sales UI/API:

- The collected production bundle contains the `/sales` route, `Record sale`, `Save correction`, `/api/sales/`, and item-scoped `/api/items/{id}/sales/` calls.
- No fake live sales were created.

Post-migration backup and restore:

- Archive: `magpie-backup-20260614-041510.tar.gz.enc`.
- Restore target: `.tmp\sprint10-live-post-restore`.
- Restored counts: `items=8`, `photos=2`, `valuations=5`, `drafts=2`, `sales=0`, `credential=1`.
- Restored migrations include `inventory.0003_inventoryitem_quantity_total_and_more` and `sales.0001_initial`.
- Restored `sales_salerecord` table/schema: PASS, required Sprint 10 columns present.

## Remote Validation

Remote GitHub Actions dual-lane `Validation` result: PASS.

- Commit: `707d5c7`.
- Run: https://github.com/GoldDiggerTriangle/magpie/actions/runs/27486309712.
- `sqlite` job: completed successfully.
- `postgres` job: completed successfully.

Lanes covered:

- `sqlite`: SQLite runtime lane, backend tests, encrypted backup/restore, frontend tests/typecheck/build, collectstatic, deploy check, Waitress/WhiteNoise smoke.
- `postgres`: PostgreSQL lane, migrations, seed, schema/fake-adapter assertions, backend tests.

## Out Of Scope Held

- No eBay order sync.
- No eBay API calls.
- No dashboards/charts or analytics endpoints.
- No FIFO/LIFO accounting.
- No tax/accounting export.
- No public exposure or HTTPS execution changes.
- No unrelated feature work.
