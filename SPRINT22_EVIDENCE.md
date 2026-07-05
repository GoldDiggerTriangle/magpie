# Sprint 22 Evidence - Channel Copy Packs and Listing Truth

Status: live deployment complete; awaiting final remote GitHub Validation after this evidence commit/push.

## Scope Implemented

- Channel copy packs for eBay, Facebook Marketplace, Gumtree, and plain/generic copy.
- Copy-pack templates live as data in `backend/apps/listing/copy_pack_templates.json`.
- Copy sections render title, description, price line, and postage/pickup line with per-section copy controls and a whole-ad copy control.
- Missing fields render as visible bracketed gaps, for example `[postage or pickup not set]`.
- Price line source is restricted to an item asking/listed price or a human-picked evidence figure.
- One-tap item photo zip export uses approved Sprint 17 derivatives first and originals as fallback.
- `ChannelListing` tracks local listing truth for eBay, Facebook Marketplace, Gumtree, in-person, and other channels.
- Listings board groups active listings by channel and supports manual add / mark-ended.
- eBay seeding reads existing local `ListingDraft` publish records only; no eBay API calls are made.
- eBay seeding is idempotent and ambiguous local state seeds nothing.
- Sold-out take-down checklist appears on item detail, listings board, and dashboard summary.
- Partial quantity rule is preserved: checklist raises only when `quantity_remaining == 0`.
- Sprint 20 cash-lock semantics now use active `ChannelListing` rows first, with old listing-draft fallback only if no channel-listing rows exist.

## Migration

- Added migration: `backend/apps/listing/migrations/0003_channellisting.py`.
- Live migration applied:
  - `python manage.py migrate listing 0003`
  - Result: `Applying listing.0003_channellisting... OK`.
- Live migration marker verified with `showmigrations listing`: `0003_channellisting` checked.
- Live schema spot-check verified `listing_channellisting` columns:
  - `id`, `created_at`, `updated_at`, `channel`, `listed_at`, `ended_at`, `url`, `note`, `item_id`, `source_listing_draft_id`.

## Safety

- No auto-posting.
- No Facebook/Gumtree automation.
- No scraping, fetching, warehousing, or marketplace API calls.
- No new eBay API usage.
- No generated prices.
- No AI paths.
- Own photos only for photo zip export.
- Checklist is derived from active `ChannelListing` rows and only clears when rows are manually marked ended.

## Validation

- Backend focused Sprint 22 tests:
  - `python -m pytest apps/listing/tests/test_sprint22.py -q`
  - Result: `9 passed`.
- Related backend suites:
  - `python -m pytest apps/listing/tests/test_sprint22.py apps/profit/tests/test_sprint20.py apps/profit/tests/test_sprint21.py -q`
  - Result: `23 passed`.
- Full backend suite:
  - `python -m pytest -q`
  - Result: `185 passed, 1 skipped`.
- Frontend focused tests:
  - `npm run test -- CopyPackPanel ChannelListingsPage --run`
  - Result: `4 passed`.
- Full frontend tests:
  - `npm run test -- --run`
  - Result: `97 passed`.
- Typecheck:
  - `npm run typecheck`
  - Result: passed.
- Build:
  - `npm run build`
  - Result: passed.
- collectstatic:
  - `python manage.py collectstatic --noinput`
  - Result: `7 static files copied`, `155 unmodified`, `425 post-processed`.
- Built asset hardcoded-localhost check:
  - `rg "localhost:8000|127\.0\.0\.1:8000|http://localhost|https://localhost" frontend/dist backend/staticfiles`
  - Result: no matches.

## Backup and Restore

- Pre-migration encrypted backup created before applying the live migration:
  - `backend/backups/magpie-backup-20260705-203718.tar.gz.enc`.
- Post-migration encrypted backup created after migration and local eBay seed:
  - `backend/backups/magpie-backup-20260705-205128.tar.gz.enc`.
- Restore spot-check performed against the post-migration backup.
- Restore output included live counts:
  - `items=8`, `photos=2`, `comparables=4`, `valuations=5`, `drafts=2`, `sales=4`, `ebay_staging=4`, `ebay_duplicates=0`, `field_suggestions=2`, `ai_credentials=1`, `ai_research_calls=1`, `ai_search_terms=4`, `ai_reference_links=8`, `credential=1`.
- Restored database spot-check:
  - `listing_channellisting` table present.
  - `restored_channel_listing_count=1`.
  - `restored_migration_marker=1`.

## Live Deployment

- Magpie service was stopped by Administrator before migration.
- Live migration applied while the service was stopped.
- Local eBay seed helper ran without marketplace calls:
  - First run: `seeded=1`, `existing=0`, `skipped_ambiguous=0`, `skipped_missing_date=0`, `channel_listing_count=1`.
  - Second run: `seeded=0`, `existing=1`, `skipped_ambiguous=0`, `skipped_missing_date=0`, `channel_listing_count=1`.
- Magpie service was restarted by Administrator.
- Service health verified:
  - `sc.exe queryex Magpie`: `RUNNING` with non-zero PID.
  - `GET http://localhost:8000/api/health/`: `200 {"status":"ok"}`.
  - `GET http://localhost:8000/listings`: `200`, served the SPA.
  - Built asset served from `/static/assets/index-CAgNoMOX.js` and contains the listings board code.

## Live UI Evidence

- Phone screenshot, take-down checklist raised on the live listings board:
  - `evidence/sprint22/phone-listings-board-takedown-viewport.png`.
  - The live board showed `STM-00002 is sold out` under `Manual take-down required`.
- Phone screenshot, copy pack panel on item detail:
  - `evidence/sprint22/phone-copy-pack-viewport.png`.
- Phone screenshot, rendered copy sections and copy buttons:
  - `evidence/sprint22/phone-copy-pack-rendered-sections.png`.
  - Shows price source from item listed price and a visible missing-field gap for postage/pickup.

## Remote Validation

- GitHub dual-lane `Validation`: pending until this evidence commit is pushed.
