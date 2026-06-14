# Sprint 12 Evidence - Command-centre dashboard

Captured: 2026-06-15

## Scope

Sprint 12 adds the Phase 6 command-centre dashboard:

- live read-only DRF analytics endpoints under `/api/analytics/`
- backend-persisted KPI preferences at `/api/dashboard/preferences/`
- one additive `DashboardPreference` migration
- a light-first dealer-ledger dashboard UI using Recharts
- desktop chart view and phone estimate-vs-actual table fallback

No eBay sync changes, sales-capture changes, AI/photo work, warehouse/precompute layer, public exposure, HTTPS changes, destructive migrations, or background jobs were added.

## Migration and runtime data

Migration applied to the live SQLite runtime database:

- `dashboard.0001_initial`

Pre-migration encrypted backup:

- `backend/backups/magpie-backup-20260614-190917.tar.gz.enc`

Runtime data counts after migration and service restart:

| Check | Count |
| --- | ---: |
| Inventory items | 8 |
| Photo assets | 2 |
| Valuation reports | 5 |
| Listing drafts | 2 |
| eBay credentials | 1 |
| Sales | 4 |
| Pending eBay staging rows | 0 |
| Dashboard preferences | 0 |

`DashboardPreference` count is intentionally `0` until the user saves a custom KPI row; GET returns the default row without creating a record.

## Local validation

Backend:

- `python manage.py check` - passed
- `python manage.py makemigrations --check --dry-run --noinput` - passed, no changes detected
- `python -m pytest` - passed: 113 passed, 1 skipped

Frontend:

- `npm run test` - passed: 63 passed
- `npm run typecheck` - passed
- `npm run build` - passed
- Build warning: Vite reports the main bundle is larger than 500 kB after adding Recharts. This is a follow-up bundle-splitting hygiene issue, not a runtime blocker.

Static and service:

- `python manage.py collectstatic --noinput` - passed
- Magpie NSSM service restarted after the final build
- `Get-Service Magpie` - Running
- `http://localhost:8000/api/health/` - 200, `{"status":"ok"}`
- `http://localhost:8000/dashboard` - 200, built SPA bundle served
- `http://192.168.1.86:8000/dashboard` - 200, built SPA bundle served

## Browser evidence

Screenshots captured from the running Magpie service using a short-lived Django session that was deleted after capture.

- Desktop: `docs/evidence/sprint12-dashboard-desktop.png`
- Phone: `docs/evidence/sprint12-dashboard-phone.png`

Automated browser checks:

| Check | Desktop | Phone |
| --- | --- | --- |
| Dealer ledger page rendered | yes | yes |
| KPI tiles rendered | yes | yes |
| P&L section rendered | yes | yes |
| Estimate-vs-actual section rendered | yes | yes |
| Aging inventory section rendered | yes | yes |
| Listing opportunities section rendered | yes | yes |
| Broken-panel text detected | no | no |
| Estimate chart visible | yes | no |
| Estimate table visible | no | yes |

## Dashboard behaviour proven by tests

- default KPI row appears with no preference record
- KPI tile changes persist via backend preference PUT
- saved tile order is the rendered order
- unknown tile IDs are stripped safely
- max 5 and min 3 KPI selection enforced
- read-only aggregate endpoints return realistic multi-category, multi-month payloads
- external/cost-basis-unknown sales count toward revenue/fees but are excluded from profit/margin/valuation accuracy
- empty states point to operational next actions
- small-sample states are explicit
- impossible negative time-to-sale intervals are excluded from the average instead of displaying negative days

## Design review notes

Implementation uses the Sprint 12 light-first dealer-ledger direction:

- cool paper background, ink text, hairline rules
- restrained antique-gold accent
- muted green/red semantic colour
- tabular numeric presentation
- signature estimate-vs-actual scatter with a gold 45-degree reference line
- phone reflow into single-column sections with estimate-vs-actual table fallback

Regan sign-off is still required for the final aesthetic gate. Codex cannot sign off on Regan's behalf.

## Remote Validation

Remote dual-lane GitHub Actions Validation for Sprint 12 implementation commit `32e2511`:

- Run: `27509514825`
- URL: `https://github.com/GoldDiggerTriangle/magpie/actions/runs/27509514825`
- Result: success
- Jobs: `sqlite` success, `postgres` success
