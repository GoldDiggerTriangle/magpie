# Sprint 16 Evidence - AI Settings Completion + Mobile Fit

Date: 2026-06-16
Runtime checkout: `C:\Users\Regan\Documents\Codex\2026-06-13\reasoning-extra-high-i-approve-sprint-2`

## Scope

Sprint 16 completed the missing AI credential management UI in Settings and the mobile fit/readability pass. Round 2 was limited to the requested colour/legibility, safe-area/overhang, remaining mobile overflow, screenshot housekeeping, and evidence updates.

No new AI behaviour, schemas, migrations, eBay changes, photo fix-up, or app features were added in Round 2.

## Round 2 Implementation Summary

- Recoloured the shared app shell and UI components to a brighter high-contrast light scheme.
- Replaced pale grey and pastel-on-light helper/label text with dark, readable text.
- Switched dark form fields to white fields with clear outlines and dark text.
- Replaced old dark-theme cyan/pastel status and link text with darker accessible accent tones.
- Added app-shell safe-area padding for mobile top insets and bottom navigation safe-area space.
- Kept cards, forms, KPI tiles, Settings, item detail, sales, inventory, eBay, and dashboard content constrained to the viewport at phone width.
- Left the validated AI credential form and provider behaviour unchanged.
- Replaced the stale Sprint 16 screenshot files with fresh service-served Round 2 screenshots.

## AI Settings Status

The AI Settings section remains operational after Round 2:

- `/api/ai/status/`: 200.
- `configured=true`.
- `enabled=true`.
- Provider shown as `openai`.
- Active model shown as `gpt-5.4-mini`.
- Monthly usage/cap/remaining budget visible.
- API key is not returned by the API.
- Key field remains masked/empty in the UI.

## Schema / Backup

No schema changes were made.

- No Sprint 16 Round 2 migration was created.
- No pre/post migration backup was required for Round 2.

## Local Validation

Backend:

- `.venv\Scripts\python.exe -m pytest`: 134 passed, 1 skipped.
- Pytest reported a cache-write warning for `.pytest_cache`; tests still passed.

Frontend:

- `npm run test -- --run`: 75 passed.
- `npm run typecheck`: passed.
- `npm run build`: passed.
- Vite chunk-size warning remains present from the existing app build profile.

Static/service:

- `.venv\Scripts\python.exe manage.py collectstatic --noinput`: passed.
- Collectstatic result: 7 files copied, 155 unmodified, 425 post-processed.
- `Magpie` NSSM service restarted by Administrator action after collectstatic.

Health:

- `Get-Service Magpie`: Running, Automatic.
- `GET http://localhost:8000/api/health/`: 200, `{"status":"ok"}`.
- `GET http://192.168.1.86:8000/api/health/`: 200, `{"status":"ok"}`.

## Browser / Screenshot Evidence

Captured against the running `Magpie` service at `http://localhost:8000` using a short-lived authenticated Django session created for screenshot evidence and deleted by the harness afterward.

Screenshots:

- Desktop Settings: `docs\evidence\sprint16-settings-desktop.png`
- Phone Dashboard: `docs\evidence\sprint16-dashboard-phone.png`
- Phone Settings with AI section: `docs\evidence\sprint16-settings-phone.png`
- Phone Inventory: `docs\evidence\sprint16-inventory-phone.png`
- Phone Item Detail: `docs\evidence\sprint16-item-detail-phone.png`
- Phone Sales: `docs\evidence\sprint16-sales-phone.png`
- Phone eBay Orders: `docs\evidence\sprint16-ebay-orders-phone.png`

Browser assertions from `.tmp\sprint16-browser-evidence-result.json`:

- Desktop Settings has no horizontal overflow.
- Phone dashboard has no horizontal overflow at 390px.
- Phone Settings has no horizontal overflow at 390px.
- Phone inventory has no horizontal overflow at 390px.
- Phone item detail has no horizontal overflow at 390px.
- Phone sales has no horizontal overflow at 390px.
- Phone eBay orders has no horizontal overflow at 390px.
- No `NaN` text or broken-panel text was present on captured pages.
- Buttons met the minimum touch-size check.
- Settings showed the AI Provider panel, provider, model, usage, and masked key field.
- Authenticated `/api/ai/status/` returned no API key field.

## Screenshot Review Notes

Phone screenshots were visually inspected after Round 2:

- Dashboard: content fits in one column; KPI tiles and charts no longer require sideways scrolling.
- Settings: AI Provider, Order Sync, audit, and disconnect sections fit the viewport; labels and helper text are dark/high contrast.
- Item detail: forms and deep panels fit the viewport; no right-edge overhang was observed.
- Sales: item links now use a dark blue accent instead of pale cyan.
- Inventory and eBay Orders: cards, controls, and empty states fit the phone viewport.

Regan's final phone-legibility sign-off is still required before formally closing Sprint 16.

## GitHub Validation

Dual-lane GitHub `Validation` must be verified on the pushed branch-tip commit for Sprint 16 closure. The exact run ID is recorded in final closeout after the commit is pushed and the run completes.
