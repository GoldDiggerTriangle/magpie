# Sprint 21 Evidence - Lot Purchase Manager and Source ROI

Date: 2026-07-06

## Scope

Sprint 21 adds a lot purchase manager, source tagging, human-driven cost allocation, scrapped-member ledger losses, source dimensions in profit intelligence, and Lot mode in the Buy Calculator.

No AI numbers, scraping, new eBay API usage, new network calls, automated valuation, retroactive P&L rewrites, warehouse tables, or automated allocation decisions were added.

## Implementation

- Added `Source` for purchase/source tagging with the approved type list: market, estate, auction, op_shop, online, private, other.
- Added `Lot` as one purchase event with label, purchase date, total all-in cost, source, and note.
- Added item fields for lot membership, direct source for single-item buys, disposition, and scrapped date.
- Lot-linked items inherit the lot source in serializers and profit ledger logic; source is not duplicated onto lot members.
- The allocated lot cost is the existing `InventoryItem.acquisition_cost`; no parallel cost field was created.
- Added allocation helpers for equal split, proportional-to-estimate split, and manual allocation with visible live tally.
- Allocation helpers operate only on unsold/unlocked members; sold and scrapped members keep their locked acquisition cost.
- Allocation uses cent rounding and puts rounding residue onto the last affected unlocked member so affected allocations sum exactly.
- Over-allocation and partial-allocation states remain visible in the lot payload and UI.
- Marking a member scrapped sets disposition and scrapped date, locks the cost basis, and surfaces a zero-revenue ledger loss with provenance `scrapped`.
- Scrapped rows flow into the AU financial-year CSV export.
- Lot P&L reports total cost, allocated, unallocated, realised revenue, realised profit, remaining unsold cost basis, and a plain recovered line.
- Profit ledger rows now include lot/source/provenance fields, and aggregates include `by_source`.
- Buy-more ranking now groups by category + channel + source and keeps the Sprint 20 standards: `n >= 3`, thin states, and no loss-making recommendations.
- Buy Calculator now includes Lot mode, treating expected resale as one transient lot total while reusing the shared reverse-margin engine.
- Added `/lots` and `/lots/:id` UI routes plus the Lots nav entry.

## Migrations

Additive migrations only:

- `backend/apps/profit/migrations/0002_source_lot.py`
- `backend/apps/inventory/migrations/0004_inventoryitem_disposition_inventoryitem_lot_and_more.py`

Live migration result:

```powershell
python manage.py migrate
```

Result:

- `profit.0002_source_lot... OK`
- `inventory.0004_inventoryitem_disposition_inventoryitem_lot_and_more... OK`

Post-migration live schema/count spot-check:

- `lots=0`
- `sources=0`
- `items_with_lot_field=0`
- `items_with_source_field=0`
- `scrapped_items=0`

No fake live lot, source, item, sale, or scrapped row was created for evidence.

## Backup / Restore

Pre-migration encrypted backup:

- `magpie-backup-20260705-123704.tar.gz.enc`

Post-migration encrypted backup:

- `magpie-backup-20260705-192631.tar.gz.enc`

Restore spot-check target:

- `.tmp/sprint21-restore-post`

Restore output confirmed existing live counts after migration:

- `items=8`
- `photos=2`
- `comparables=4`
- `valuations=5`
- `drafts=2`
- `sales=4`
- `ebay_staging=4`
- `credential=1`

Schema spot-check against the restored SQLite DB:

- `profit_source` table present
- `profit_lot` table present
- `inventory_inventoryitem.lot_id` field present
- `inventory_inventoryitem.source_id` field present
- `inventory_inventoryitem.disposition` field present
- `inventory_inventoryitem.scrapped_at` field present

## Tests

Backend focused Sprint 20/21 regression suite:

```powershell
$env:DATABASE_URL='sqlite:///db.sqlite3'; python -m pytest apps/profit/tests/test_sprint20.py apps/profit/tests/test_sprint21.py -q
```

Result: `14 passed`.

Backend full suite:

```powershell
$env:DATABASE_URL='sqlite:///db.sqlite3'; python -m pytest -q
```

Result: `176 passed, 1 skipped`.

Migration consistency:

```powershell
$env:DATABASE_URL='sqlite:///db.sqlite3'; python manage.py makemigrations --check --dry-run
```

Result: `No changes detected`.

Frontend focused Sprint 21 tests:

```powershell
npm run test -- BuyCalculator.test.tsx LotsPage.test.tsx ProfitPage.test.tsx
```

Result: `13 passed`.

Frontend full suite:

```powershell
npm run test
```

Result: `28 passed` test files, `93 passed` tests.

Typecheck:

```powershell
npm run typecheck
```

Result: passed.

Build:

```powershell
npm run build
```

Result: passed. Vite emitted the existing large-chunk warning class.

Collectstatic:

```powershell
python manage.py collectstatic --noinput
```

Result: `7 static files copied`, `155 unmodified`, `425 post-processed`.

## Required Behaviour Proof

- Equal split allocation: covered by `test_allocation_helpers_round_to_cent_and_warn_on_overallocation`.
- Manual tally and over-allocation warning: covered by `test_allocation_helpers_round_to_cent_and_warn_on_overallocation` and `LotsPage.test.tsx`.
- Proportional helper availability and estimate requirement: covered by `test_proportional_helper_requires_estimates_and_puts_residue_on_last_member`.
- Sum-to-the-cent rounding residue: covered by allocation helper tests.
- Sold lock: covered by `test_sold_lock_keeps_historical_profit_and_redistributes_only_unlocked`.
- Scrapped lock: covered by `test_scrapped_lock_creates_ledger_loss_and_fy_export`.
- Scrapped ledger loss: covered by `test_scrapped_lock_creates_ledger_loss_and_fy_export`.
- Scrapped FY export: covered by CSV assertion in `test_scrapped_lock_creates_ledger_loss_and_fy_export`.
- Scrapped item cannot later receive a new sale: covered by `test_scrapped_lock_creates_ledger_loss_and_fy_export`.
- Lot P&L across sold/unsold/scrapped mixes: covered by `test_lot_pnl_handles_sold_unsold_and_scrapped_mix`.
- Source inheritance: covered by `test_source_inheritance_ledger_aggregate_and_source_ranking`.
- Source dimension in ledger aggregates: covered by `test_source_inheritance_ledger_aggregate_and_source_ranking`.
- Source dimension in buy-more ranking: covered by `test_source_inheritance_ledger_aggregate_and_source_ranking`.
- `n >= 3` ranking threshold: covered by Sprint 20 and Sprint 21 ranking tests.
- No loss-making source/category/channel group recommended: covered by Sprint 20 and Sprint 21 ranking tests.
- Lot mode Max Buy via shared engine: covered by backend `test_lot_mode_max_buy_uses_shared_engine_and_what_if_stays_transient` and frontend `BuyCalculator Lot mode reuses the same max-buy engine for total resale`.
- What-if transience: covered by backend and frontend Buy Calculator tests.
- No new network calls: covered by `test_no_new_network_calls_in_lot_profit_paths` and existing Sprint 20 no-network profit guard.

## Live Runtime Evidence

Magpie was stopped by Regan for migration, then restarted by Regan after deployment.

Post-restart checks:

- `Get-Service Magpie`: `Running`.
- `netstat`: `0.0.0.0:8000 LISTENING` with PID `10908`.
- `/api/health/`: HTTP `200`, `{"status":"ok"}`.
- `/lots`: HTTP `200`, served the Magpie SPA.
- Live `/lots` browser route loaded after cache-busted navigation.
- Live `/profit` browser route loaded at phone width with no horizontal overflow (`scrollWidth == clientWidth`).
- Live `/buy-calculator` Lot mode produced `Max Lot Buy $76.92`, verdict `BUY`, expected profit `$40.00`, ROI `66.67%` for the canonical $100 seller-receives / $60 asking / 30% all-in ROI case.

Screenshots:

- `evidence/screenshots/sprint21-phone-lots-empty-live.png`
- `evidence/screenshots/sprint21-phone-profit-source-ranking.png`
- `evidence/screenshots/sprint21-phone-buy-calculator-lot-mode.png`
- `evidence/screenshots/sprint21-desktop-lots.png`

Evidence caveat: the live DB had no Lot/Source rows immediately after migration, and no fake live data was created. Therefore the live Lot screenshot shows the reachable empty state. The tally and sold-locked member states are proven by backend tests and `LotsPage.test.tsx`, not by fake live business rows.

## GitHub Validation

Implementation commit: `b5a593d`.

Run: https://github.com/GoldDiggerTriangle/magpie/actions/runs/28752285740

Result: success.

- `sqlite`: completed, success.
- `postgres`: completed, success.

This evidence file update is documentation-only and was pushed after the green implementation run.

