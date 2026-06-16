# Sprint 17 Evidence - Local Photo Fix-up

Date: 2026-06-16  
Runtime checkout: `C:\Users\Regan\Documents\Codex\2026-06-13\reasoning-extra-high-i-approve-sprint-2`

## Scope

Sprint 17 implemented the final local photo fix-up sprint for the user's own photos only.

Built:

- Local one-tap photo fix-up pipeline.
- Crop / straighten / rotate, white-balance, gentle exposure / contrast, and clean white-background cleanup.
- Non-destructive `PhotoDerivative` storage linked to the original `PhotoAsset`.
- Pending review state with before/after comparison.
- Explicit Approve / Tweak / Reject and Revert-to-original flows.
- Batch-friendly "Fix up all photos" action from item detail.
- Backend and frontend tests for no-auto-apply, approval, reject, tweak, revert, backup coverage, and no external calls.

Not built:

- No cloud processing.
- No API key or external provider.
- No network call from the fix-up pipeline.
- No generative fill.
- No beautify/retouch step.
- No scratch/wear removal.
- No shine/gloss boosting.
- No condition smoothing.
- No third-party or marketplace images.
- No auto-apply on upload.

## Implementation Summary

Backend:

- Added additive migration `photos.0002_sprint17_photo_fixups`.
- Added `PhotoDerivative` for derived fixed image versions.
- Added `PhotoAsset.fixup_status` and `PhotoAsset.active_derivative`.
- Added local `PhotoFixupService` and conservative Pillow-based pipeline.
- Added API actions:
  - `POST /api/photos/{id}/fixup/`
  - `POST /api/photos/{id}/fixup/tweak/`
  - `POST /api/photos/{id}/fixup/approve/`
  - `POST /api/photos/{id}/fixup/reject/`
  - `POST /api/photos/{id}/fixup/revert/`
  - `POST /api/items/{id}/photos/fixup/`
- Added derivative file cleanup on delete.
- Extended photo serializers with pending/approved derivative details and media URLs.

Frontend:

- Added typed photo derivative fields.
- Added photo fix-up API client methods.
- Added `PhotoFixupPanel` on item detail below the gallery.
- The panel shows before/after, condition-integrity warning, per-photo controls, batch generation, tweak inputs, approval, rejection, and revert.
- UI uses Sprint 16 bright high-contrast tokens and fits phone width.

## Local Pipeline

Pipeline operations are intentionally limited to:

- `exif_orientation`
- `conservative_autocrop`
- `straighten_rotate`
- `gray_world_white_balance`
- `gentle_auto_levels`
- `local_background_cleanup`

Prohibited operation names are asserted in tests:

- `generative_fill`
- `retouch`
- `beautify`
- `scratch_removal`
- `wear_removal`
- `condition_smoothing`
- `shine_boost`
- `gloss_boost`

Background cleanup mode used in live evidence: `local_threshold_fallback`.

The offline model path is probed locally; no bundled local model was configured in this runtime, so Sprint 17 used the documented local threshold fallback. No network-backed background model or cloud fallback was used.

## Live Deployment

Pre-migration:

- Pre-migration encrypted backup command succeeded before applying the migration:
  - `magpie-backup-20260616-102703.tar.gz.enc`
- This local archive was later pruned by the backup command's retention pass when the post-migration backup was created. The creation was verified from command output before migration.

Migration:

- `photos.0002_sprint17_photo_fixups`: applied successfully to the live SQLite DB.

Static/runtime:

- `npm run build`: passed.
- `.venv\Scripts\python.exe manage.py collectstatic --noinput`: passed.
- Collectstatic result: 7 files copied, 155 unmodified, 425 post-processed.
- `Magpie` NSSM service restarted by Administrator action after migration and collectstatic.

Health:

- `Get-Service Magpie`: Running, Automatic.
- `netstat`: `0.0.0.0:8000` listening.
- `GET http://localhost:8000/api/health/`: 200, `{"status":"ok"}`.
- `GET http://192.168.1.86:8000/api/health/`: 200, `{"status":"ok"}`.

Live DB after evidence staging:

- items: 8
- photos: 2
- derivatives: 1
- pending derivatives: 1
- approved derivatives: 0
- pending photos: 1

The one live derivative was staged for before/after evidence only. It remains pending review. No live photo was approved, so no display image was changed.

## Backup / Restore

Post-migration encrypted backup:

- `magpie-backup-20260616-110343.tar.gz.enc`
- Size: 401174 bytes.

Restore spot-check target:

- `.tmp\sprint17-restore-spot`

Restore command completed successfully.

Restored Sprint 17 checks:

- `photos_photoderivative` rows: 1
- pending derivative rows: 1
- photo assets with `pending_review`: 1
- restored fixed media file exists: yes
- restored thumb media file exists: yes
- fixed path prefix: `fixups`
- thumb path prefix: `fixup-thumbs`

## Test Results

Backend:

- `$env:DATABASE_URL='sqlite:///test_sprint17.sqlite3'; .venv\Scripts\python.exe -m pytest apps\photos\tests\test_sprint17.py -q`: 4 passed.
- `$env:DATABASE_URL='sqlite:///test_sprint17.sqlite3'; .venv\Scripts\python.exe -m pytest -q`: 138 passed, 1 skipped.

Frontend:

- `npm run test`: 25 files passed, 78 tests passed.
- `npm run typecheck`: passed.
- `npm run build`: passed.

Build note:

- Vite still reports the existing chunk-size warning. This is not a Sprint 17 runtime blocker.

## Browser / Screenshot Evidence

Captured against the running `Magpie` service at `http://localhost:8000` using a short-lived authenticated Django session created by `.tmp\sprint17-browser-evidence.mjs` and deleted by the harness afterward.

Screenshots:

- Desktop before/after: `docs\evidence\sprint17-photo-fixup-desktop.png`
- Phone before/after: `docs\evidence\sprint17-photo-fixup-phone.png`

Browser assertions from `.tmp\sprint17-browser-evidence-result.json`:

- Desktop item detail has no horizontal overflow.
- Phone item detail has no horizontal overflow at 390px.
- Before/after comparison visible on desktop and phone.
- Condition guard visible on desktop and phone.
- Approve / Tweak / Reject visible on desktop and phone.
- No request-failed or unable-to-load broken panel text.
- Evidence item: `STM-00002`.
- Evidence derivative status: pending review.
- Evidence derivative background mode: `local_threshold_fallback`.

## Manual Condition-Integrity Check

The captured before/after screenshots were visually inspected.

Result:

- The generated image improves framing and the white-background presentation.
- The source item shape and visible markings remain present.
- No scratch/wear removal, smoothing, gloss boosting, beautification, or condition-altering retouch was observed.
- The output remains pending review and has not become the display image.

## GitHub Validation

Dual-lane GitHub `Validation` passed on pushed branch-tip commit `8c3ea05`.

- Run ID: `27613154373`
- Workflow: `Validation`
- sqlite job: success
- postgres job: success
- Run URL: `https://github.com/GoldDiggerTriangle/magpie/actions/runs/27613154373`
