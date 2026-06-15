# Sprint 16 Evidence - AI Settings Completion + Mobile Fit

Date: 2026-06-16
Runtime checkout: `C:\Users\Regan\Documents\Codex\2026-06-13\reasoning-extra-high-i-approve-sprint-2`

## Scope

Sprint 16 completed the missing AI credential management UI in Settings and a mobile fit/readability pass across the existing app. No new AI behavior, real provider call, schema change, migration, photo fix-up, or redesign was added.

## Model Check

OpenAI model documentation was checked during implementation:

- https://platform.openai.com/docs/models

The Sprint 15 default `gpt-4.1-mini` was replaced with `gpt-5.4-mini` for the OpenAI default model. The model remains user-settable through Settings and stored on the provider-agnostic AI credential record.

## Implementation Summary

AI Settings:

- Added an `AI Provider` section to Settings beside the existing eBay credential flow.
- Reused the encrypted `AICredential` backend path.
- Added UI controls for provider, model, monthly cap, and API key.
- Save supports first-time key setup and later model/cap updates without resubmitting the stored key.
- Disconnect removes the encrypted AI credential after confirmation.
- Stored keys are never returned, logged, displayed, or committed; the Settings UI only shows configured/masked state.
- `/api/ai/status/` supplies configured/enabled status, provider, model, monthly usage, cap, remaining budget, and disabled reason.

Mobile fit/readability:

- Removed horizontal overflow at phone width across dashboard, Settings, inventory list, item detail, sales, and eBay orders.
- Converted sales tables/history to mobile card layouts where needed.
- Added mobile wrapping/containment for Settings, audit rows, pricing evidence grids, form controls, cards, and action buttons.
- Preserved the existing dealer's-ledger visual language.

## Schema / Backup

No schema changes were made.

- `python manage.py makemigrations --check --dry-run --noinput`: no changes detected.
- No Sprint 16 migration was created.
- No Sprint 16 pre/post migration backup was required.

## Local Validation

Backend:

- `.venv\Scripts\python.exe -m pytest`: 134 passed, 1 skipped.
- Pytest reported a cache-write warning for `.pytest_cache`; tests still passed.

Frontend:

- `npm run test`: 75 passed.
- `npm run typecheck`: passed.
- `npm run build`: passed.
- `python manage.py collectstatic --noinput --clear`: passed, 162 files copied and 468 post-processed.

Build note:

- Vite chunk-size warning remains present from the existing app build profile.

## Service Deployment

After the production build and collectstatic, the `Magpie` NSSM service was restarted by Administrator action.

Verified service state:

- `Get-Service Magpie`: Running, Automatic.
- Port `0.0.0.0:8000` listening, owned by PID 4824 at verification time.
- `GET http://localhost:8000/api/health/`: 200, `{"status":"ok"}`.
- `GET http://192.168.1.86:8000/api/health/`: 200, `{"status":"ok"}`.
- Built SPA index references `/assets/index-B1i0QYKv.js` and `/assets/index-DiAKKLTS.css`.

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

Browser assertions:

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
- Authenticated `/api/ai/status/` returned status 200 with:
  - configured=false
  - enabled=false
  - provider=openai
  - model_id=`gpt-5.4-mini`
  - monthly cap visible
  - remaining budget visible
  - disabled reason present
  - no API key returned

Live key note:

- No real API key was entered during Sprint 16 evidence. The save/replace/remove paths are covered by backend and frontend tests; live real-provider validation remains the explicit Sprint 15 follow-up when Regan chooses to configure a key.

## GitHub Validation

Pending at the time this evidence file was first written. It will be updated after commit/push and the dual-lane `Validation` workflow completes.
