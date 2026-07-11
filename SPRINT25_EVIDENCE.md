# Sprint 25 Evidence - Quick Publish to eBay

Status: implementation complete and locally validated in this checkout. Formal live closure remains pending the owner-present real eBay publish proof required by the Sprint 25 spec.

## Prerequisites

Confirmed by Regan before implementation:

- eBay Australia Pro Basic subscription is active.
- eBay production client secret and exposed local secrets were rotated.
- New credential values were entered locally.
- Magpie was restarted.
- eBay connection health was verified.
- No secret values were printed or committed.

## Scope Implemented

- Added a `Post to eBay` quick-publish panel in the item `Listings / channels` section, adjacent to copy packs and the existing listing draft workflow.
- Tap 1 opens a preview sheet showing the listing content before anything is posted live:
  - title
  - photo count
  - price and source label
  - postage / pickup text
  - condition
  - category mapping
  - description rendered from the eBay copy-pack template
- Tap 2 posts live through the existing listing draft pipeline:
  - `createItemListingDraft` when no local draft exists
  - `updateListingDraft`
  - `stageListingDraft`
  - `publishListingDraft`
- Successful publish now creates or updates a durable `ChannelListing` row after eBay returns a listing ID.
- Failed publish does not create a `ChannelListing` row.
- The live listing URL is shown after publish.
- The copy-pack `Photo zip` button now stays as a single no-wrap phone tap target.

## Safety and Scope Controls

- No schema changes.
- No migrations.
- No new eBay API endpoints.
- No new backend quick-publish endpoint.
- No zero-tap, batch, scheduled, or background posting path.
- The quick publish UI can only call publish from the explicit preview confirmation button.
- Price source is restricted for quick publish:
  - item asking price (`target_price`)
  - manually edited listing draft price without generated price metadata
  - human-picked evidence price typed by the user in the preview
- Valuation-generated draft prices are ignored by the quick-publish gate and shown as missing until the user supplies an allowed price source.
- Human evidence price typed in the preview is used only for the publish draft update; it is not saved as evidence.
- The quick path reuses the existing eBay draft/stage/publish functions.
- Existing draft path remains available as the fallback for detailed eBay setup or API failures.
- No credentials, tokens, `.env` values, OAuth codes, rclone config, backup passphrase, or encryption keys were printed or committed.

## Backend Behaviour

- `apps.ebay.publishing.publish_draft` now writes `ChannelListing(channel=ebay)` only inside the successful publish branch after `publish_offer` returns a listing ID.
- The `ChannelListing` row is keyed by `source_listing_draft` and updated idempotently for the draft.
- The listing URL uses the returned listing ID:
  - `https://www.ebay.com.au/itm/<listing_id>`
- Publish failures keep the draft in `publish_failed` state and record the existing audit failure without creating listing truth.

## Validation

- Focused backend publish tests:
  - Command: `backend\.venv\Scripts\python.exe -m pytest apps/ebay/tests/test_sprint7.py -q`
  - Result: `16 passed`.
- Full backend suite:
  - Command: `backend\.venv\Scripts\python.exe -m pytest -q`
  - Result: `210 passed, 1 skipped`.
- Focused frontend tests:
  - Command: `npm run test -- QuickPublishPanel.test.tsx CopyPackPanel.test.tsx`
  - Result: `7 passed`.
- Full frontend suite:
  - Command: `npm run test`
  - Result: `121 passed`.
- Typecheck:
  - Command: `npm run typecheck`
  - Result: passed.
- Migration check:
  - Command: `python manage.py makemigrations --check --dry-run`
  - Result: `No changes detected`.
- Build:
  - Command: `npm run build`
  - Result: passed; existing Vite large chunk warning only.
- collectstatic:
  - Command: `python manage.py collectstatic --noinput`
  - Result: `7 static files copied`, `155 unmodified`, `425 post-processed`.
- Built asset hardcoded-localhost check:
  - Command: `rg "localhost:8000|127\\.0\\.0\\.1:8000|http://localhost|http://127\\.0\\.0\\.1" frontend/dist backend/staticfiles`
  - Result: no matches.
- NSSM restart attempt from this non-Administrator shell:
  - Command: `nssm restart Magpie`
  - Result: blocked by Windows with `OpenService(): Access is denied.`
- Existing service health before Administrator restart:
  - Command: `Invoke-WebRequest http://127.0.0.1:8000/api/health/`
  - Result: `200`.
  - Note: this proves the old running service is healthy, not that Sprint 25 is loaded by port `8000`.

## Automated Acceptance Coverage

- Ready preview:
  - Renders title, photo count, price, source label, category mapping, and eBay copy-pack description.
  - Does not call publish when the preview opens.
  - Calls the existing `updateListingDraft`, `stageListingDraft`, and `publishListingDraft` functions only after `Post live to eBay`.
- Gate coverage:
  - Missing price source blocks live post.
  - Missing photo blocks live post.
  - Missing postage/pickup blocks live post.
  - Missing condition blocks live post.
  - Missing eBay connection blocks live post.
- D-129 price-source guard:
  - Generated draft price is ignored.
  - Human-picked evidence price is accepted and labelled.
  - Item asking price is accepted and labelled.
- Backend publish truth:
  - Failed publish creates no `ChannelListing`.
  - Successful publish creates `ChannelListing(channel=ebay)` with returned URL.
  - Second publish is refused and does not duplicate or call eBay again.
- Photo zip mobile wrap:
  - The copy-pack `Photo zip` button includes `whitespace-nowrap` and `shrink-0`.

## Live Closure Gates

Open until Regan is present for the real publish:

- Real owner-approved eBay publish from the preview sheet.
- Returned live listing URL verified in the UI.
- Live `ChannelListing` row verified after publish.
- Phone screenshot of quick-publish preview with blockers clear.
- Phone screenshot of successful publish URL / ChannelListing proof.
- Phone screenshot showing the no-wrap `Photo zip` button at approximately 390px width.
- Magpie NSSM service restarted after the collected static build.
- Live `/api/health/` verified after restart.
- Dual-lane GitHub `Validation` verified green after push.

## Notes

- The implementation is intentionally preview-gated and does not create any live listing without the second explicit confirmation click.
- The existing detailed listing draft workflow remains the operational fallback for category, policy, aspect, or eBay account errors.
- No backup/restore proof was required because Sprint 25 introduced no migration and no schema changes.
