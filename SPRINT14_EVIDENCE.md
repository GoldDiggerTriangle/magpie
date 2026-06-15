# Sprint 14 Evidence - Pricing Evidence Layer

Date: 2026-06-15

Runtime checkout:

`C:\Users\Regan\Documents\Codex\2026-06-13\reasoning-extra-high-i-approve-sprint-2`

## Scope Guard

- Implemented item-level pricing evidence only.
- No cloud AI, no API key, no external AI provider.
- No AI-produced numeric price bands.
- No server-side marketplace fetch, scrape, cache, summary, or warehouse.
- External sources are URL-only links that open in a browser tab.
- Pricing grids are computed only from Magpie `SaleRecord` rows and user-recorded `Comparable` rows.
- User-captured comparable URLs are stored only when the user enters them; Magpie does not visit them server-side.

## Code Changes

- Added URL-template pricing source registry for eBay sold, Facebook Marketplace, auction archive, price-guide, Google, and category-specific view-only links.
- Added live pricing evidence aggregate for item detail:
  - own sales first
  - exact-item rows before explainable similar-item rows
  - source-tagged comparable rows
  - grids by condition/grade, sale format, recency, and source
  - low / median / high / count per grid cell
- Extended `Comparable` additively with:
  - `grade`
  - `sale_format`
  - `source_tag`
  - `match_scope`
  - `match_reason`
- Added `/api/items/<item_id>/pricing-evidence/`.
- Added item-detail pricing evidence panel and fast capture-to-grid flow.
- Extended backup key-row coverage to include `research_comparable`.
- Extended the CI marketplace URL-only guard to Sprint 14 pricing sources.

## Migration

Applied live migration:

- `research.0002_comparable_grade_comparable_match_reason_and_more`

The migration is additive only.

## Local Validation

Completed before live deployment:

- Backend focused Sprint 14 tests: `6 passed`
- Backend full suite: `124 passed, 1 skipped`
- Frontend tests: `69 passed`
- Typecheck: passed
- Build: passed
- Django `check`: passed
- `makemigrations --check --dry-run`: passed
- Local marketplace URL-only confinement guard: passed

## Live Deployment

Pre-migration encrypted backup:

- `backend/backups/magpie-backup-20260615-010344.tar.gz.enc`

Deployment steps completed:

- Stopped `Magpie` service before live DB migration.
- Applied Sprint 14 migration to live SQLite DB.
- Ran `collectstatic`.
- Restarted `Magpie` service.
- Verified `Get-Service Magpie` reports `Running`.
- Verified `http://localhost:8000/api/health/` returns `200` with `{"status":"ok"}`.
- Verified `http://192.168.1.86:8000/` returns the built SPA.

Live post-deployment counts:

- items: 8
- photos: 2
- valuations: 5
- drafts: 2
- credentials: 1
- sales: 4
- comparables: 4
- eBay staging rows: 4
- eBay duplicate candidates: 0

No live comparable rows or sales were created during browser evidence.

## Browser Evidence

The in-app browser bridge failed with its known local kernel-assets issue, so screenshot evidence used the prior proven headless Chrome path against the running `Magpie` service. The script created a short-lived Django session, captured the real built UI, and deleted the session afterward.

Captured live item:

- SKU: `COIN-00001`
- Evidence source rows: 4 user-recorded comparables
- Own sale rows on this item: 0

Desktop and phone proof:

- `docs/evidence/sprint14-pricing-desktop.png`
- `docs/evidence/sprint14-pricing-phone.png`

Browser checks:

- Pricing panel present on item detail.
- Own-sales-first headline present.
- URL-only copy present: Magpie does not fetch or store marketplace result pages.
- Capture-to-grid form present.
- Condition/grade, sale-format, recency, and source grids present.
- 6 source links visible.
- All source links open in new tabs.
- Primary source link is eBay AU sold/completed search with `LH_Sold=1` and `LH_Complete=1`.
- API returned `200` for pricing evidence with 6 source links, 4 priced rows, 0 own sales, 4 comparables.
- No broken panel, request failure, or `NaN` text was detected.

## Backup / Restore

Post-migration encrypted backup:

- `backend/backups/magpie-backup-20260615-013714.tar.gz.enc`

Restore spot-check target:

- `C:\Users\Regan\Documents\Codex\2026-06-13\magpie-sprint14-restore-spotcheck`

Restore output confirmed:

- items: 8
- photos: 2
- comparables: 4
- valuations: 5
- drafts: 2
- sales: 4
- eBay staging rows: 4
- eBay duplicate candidates: 0
- credentials: 1

Schema spot-check confirmed `research_comparable` contains:

- `grade`
- `sale_format`
- `source_tag`
- `match_scope`
- `match_reason`

## Remote Validation

Pending final push. To close Sprint 14, the pushed head must pass dual-lane GitHub `Validation` for SQLite and Postgres.

## Closure Status

Sprint 14 implementation and live deployment evidence are complete locally. Formal closure is pending commit, push, and green remote dual-lane `Validation`.
