# Sprint 20 Evidence - Profit Intelligence v1

Date: 2026-07-05

## Scope

Sprint 20 adds a read-only Profit page and live DRF aggregates for realised P&L, profit/day velocity, cash-lock buckets, buy-more ranking, and AU financial-year export.

No AI, scraping, marketplace API usage, background jobs, warehouse tables, or predictive fields were added.

## Implementation

- Added `/api/profit/ledger/` for live profit aggregates.
- Added `/api/profit/ledger.csv` for Australian financial-year CSV export.
- Added `/profit` frontend page and navigation entry.
- Reused Sprint 18 fee helpers for schedule-derived eBay AU fees.
- Actual sale fees are authoritative when `fee_status=authoritative`; schedule-derived fees are only used when actual fees are missing/unmapped.
- Fee provenance is labelled as `actual_recorded` or `schedule_derived`.
- Revenue is normalised to canonical `seller_receives`.
- Missing acquisition dates produce an unknown-date velocity state instead of silently using today, created date, or one day.
- Missing acquisition/material cost produces an unknown-cost state and warning instead of treating cash lock or profit as zero.
- Cash lock is computed from unsold owned stock and bucketed as unlisted, listed-fresh, or listed-stale.
- No listed/published timestamp means unlisted by honest default, with a hint to set a listed date if listed elsewhere.
- Buy-more ranking uses category + channel groups, `n >= 3`, and excludes loss-making groups from recommendations.
- FY export uses Australian Jul-Jun financial-year boundaries and includes the required not-tax-advice label.

## Migration / Backup

No schema migration was generated.

Command:

```powershell
$env:DATABASE_URL='sqlite:///db.sqlite3'; python manage.py makemigrations --check --dry-run --noinput
```

Result: `No changes detected`.

Because Sprint 20 required backup/restore proof only if a migration occurred, no pre-migration live DB change or restore drill was needed for this sprint.

## Tests

Backend focused Sprint 20 tests:

```powershell
$env:DATABASE_URL='sqlite:///db.sqlite3'; python -m pytest apps/profit/tests/test_sprint20.py -q
```

Result: `6 passed`.

Backend full suite:

```powershell
$env:DATABASE_URL='sqlite:///db.sqlite3'; python -m pytest -q
```

Result: `168 passed, 1 skipped`.

Frontend focused Sprint 20 tests:

```powershell
npm run test -- ProfitPage.test.tsx
```

Result: `3 passed`.

Frontend full suite:

```powershell
npm run test
```

Result: `27 passed` test files, `91 passed` tests.

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
$env:DATABASE_URL='sqlite:///db.sqlite3'; python manage.py collectstatic --noinput
```

Result: `7 static files copied`, `155 unmodified`, `425 post-processed`.

Django check:

```powershell
$env:DATABASE_URL='sqlite:///db.sqlite3'; python manage.py check
```

Result: `System check identified no issues`.

Authenticated API route smoke:

```powershell
$env:DATABASE_URL='sqlite:///db.sqlite3'; python manage.py shell -c "<authenticated APIClient GET /api/profit/ledger/>"
```

Result: HTTP `200`; payload contained `summary`, `ledger`, `aggregates`, `velocity`, `cash_lock`, `buy_more`, and `financial_years`; not-tax-advice label returned.

## Required Behaviour Proof

- Per-sale P&L across seller modes: covered by `test_profit_ledger_uses_actual_fees_before_schedule_and_keeps_losses`.
- Actual-fee vs schedule-derived fee handling: covered by `test_profit_ledger_uses_actual_fees_before_schedule_and_keeps_losses`.
- Negative-profit sale remains negative: covered by `test_profit_ledger_uses_actual_fees_before_schedule_and_keeps_losses` and frontend proof.
- Days-held guard including zero/negative duration: covered by `test_profit_ledger_uses_actual_fees_before_schedule_and_keeps_losses`.
- Missing acquisition date/cost honest states: covered by `test_missing_dates_and_costs_are_honest_states`.
- Cash-lock buckets and stale nudge: covered by `test_cash_lock_buckets_stale_nudge_and_unknown_cost_warning`.
- Ranking threshold and loss-making groups: covered by `test_buy_more_threshold_and_loss_groups_are_not_recommended`.
- FY 30 June / 1 July boundary: covered by `test_financial_year_boundary_and_csv_columns`.
- CSV golden columns and known row: covered by `test_financial_year_boundary_and_csv_columns`.
- Not-tax-advice label: covered by backend and frontend tests.
- No predictive fields in API response: covered by `test_profit_api_has_no_predictive_fields_or_network_terms`.
- No new network call path in profit helper: covered by `test_profit_api_has_no_predictive_fields_or_network_terms`.

## Live Runtime Evidence

Magpie service was restarted by Regan, then verified locally.

- `Get-Service Magpie`: `Running`.
- `sc.exe queryex Magpie`: `STATE RUNNING`, PID `9668`.
- `/api/health/`: HTTP `200`, `{"status":"ok"}`.
- `/profit`: HTTP `200`, served the Magpie SPA.
- Live browser proof: `/profit` loaded the new Profit page after a cache-busted navigation.
- Mobile viewport DOM checks around phone width showed no horizontal overflow: `scrollWidth == clientWidth` on Profit top, cash-lock, and FY export views.

Screenshots:

- `docs/evidence/sprint20-profit-phone.png`
- `docs/evidence/sprint20-cash-lock-phone.png`
- `docs/evidence/sprint20-fy-export-phone.png`
- `docs/evidence/sprint20-profit-desktop.png`

Note: the evidence browser needed a temporary normal Django session to capture authenticated read-only Profit page screenshots. No credential values were printed or committed.

## GitHub Validation

Pending after commit/push.
