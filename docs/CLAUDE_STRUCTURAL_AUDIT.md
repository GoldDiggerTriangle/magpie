# Magpie Structural Audit for Claude

Generated: 2026-09-24 (Australia/Sydney)  
Checkout: `C:\Users\Regan\Documents\Codex\2026-06-13\reasoning-extra-high-i-approve-sprint-2`  
Current branch/head at audit time: `main` / `afe9b351bd084c42aa6cd5a98be37352b9d7bfe0`  
Purpose: give Claude a practical map of where Magpie currently is before structural changes.

This is a repo and live-runtime inventory. It intentionally excludes secret values, `.env` values, tokens, OAuth codes, rclone config, backup passphrases, and encryption keys.

## 1. Current High-Level State

Magpie is a Windows + SQLite + Django/DRF + React/Vite single-operator LAN app.

Runtime shape:

- Django runs under Waitress through `backend/serve.py`.
- Static files and the built React SPA are served by WhiteNoise from the same Django process.
- One LAN port serves the SPA, `/api/`, `/admin/`, and media/static routes.
- NSSM service name is `Magpie`.
- Service is configured as `AUTO_START`.
- Current service query during this audit showed `Magpie` running.
- Port `8000` was listening, but the NSSM wrapper PID and listener PID differ because NSSM manages the child Python process.

Important runtime files:

- `backend/serve.py` loads `backend/.env`, sets `DJANGO_SETTINGS_MODULE=config.settings.prod`, and starts Waitress.
- `backend/config/settings/base.py` defines apps, DRF session auth, WhiteNoise/static config, media root, REST defaults, eBay/env settings, and logging.
- `backend/config/settings/prod.py` sets `DEBUG=False` and refuses the insecure default secret key.
- `backend/config/urls.py` routes `admin/` and `api/` before the SPA fallback. The SPA fallback excludes `api/`, `admin/`, `media/`, `static/`, and dotted asset paths.
- `.github/workflows/postgresql-validation.yml` is named historically, but the workflow display name is `Validation` and it has SQLite and PostgreSQL jobs.

## 2. Current Live Data Snapshot

Read-only row counts from the current SQLite DB:

| Area | Count |
|---|---:|
| Categories | 9 |
| Locations | 5 |
| Items | 10 |
| Photos | 12 |
| Photo derivatives | 14 |
| Comparables | 4 |
| Valuation reports | 6 |
| Valuation comparables | 4 |
| Listing drafts | 8 |
| Channel listings | 1 |
| Sales | 4 |
| Audit log rows | 120 |
| eBay credential rows | 1 |
| eBay account snapshots | 1 |
| eBay staged orders | 4 |
| eBay duplicate candidates | 0 |
| Field suggestions | 30 |
| AI research calls | 9 |
| AI search terms | 31 |
| AI reference links | 60 |
| Image fingerprints | 10 |
| Profit settings | 0 (defaults are created/read through service code) |
| Sources | 0 |
| Lots | 0 |

Current categories:

- Banknotes, `NOTE`, profile `banknotes`
- Bulk Lots, `LOT`
- Coins, `COIN`, profile `coins`
- Collectibles, `COL`
- Gold, `GOLD`, profile `gold`
- Phones & Electronics, `PH`, profile `phones`
- Stamps, `STM`, profile `stamps`
- Tools, `TOOL`
- Unknown, `UNK`

Current item highlights:

- `GOLD-00002`: `Australian Gold Nugget 1.4g Grams`, category Gold, status `captured`, condition `ungraded`, quantity `1/1`, six photos.
- `GSP-00001`: Canada $1 banknote, category Banknotes, status `ready_to_list`, condition `acceptable`, quantity `1/1`.
- `STM-00002`: sold stamp, quantity total `3`, sold `3`, remaining `0`.
- `STM-00003`: listed stamp, active eBay channel listing and published local draft.

## 3. Current Sprint/Open-Work State

### Sprint 24

`SPRINT24_EVIDENCE.md` says Sprint 24 Round 2 fixes were implemented and locally validated, but the file still says formal Round 2 live closure was pending owner proof that a full AI-approved/edited title saves and re-renders correctly.

Later owner chat context indicated the title fill path worked, but the repo evidence file may still need updating if Claude needs evidence to match reality.

Key Sprint 24 structural changes currently present:

- Item detail is split into collapsible sections.
- AI research and suggestion review now live adjacent to each other.
- `Approve all shown` exists in the suggestion review panel.
- Structured suggestion payloads render human-readable text, with raw JSON only behind a details toggle.
- AI call UUID is split into quiet metadata instead of user-facing rationale prose.
- Safe-area CSS work exists for mobile item detail.

### Sprint 25

`SPRINT25_EVIDENCE.md` says the original quick-publish implementation is complete and locally validated, but formal live closure remains pending owner-present real eBay publish proof.

Then Sprint 25 v2 clarified the locked order:

1. Secret rotation.
2. OAuth reconnect.
3. Phase 0 diagnostic publish/stage report.
4. Phase 1 git-history audit.
5. Restoration.
6. Preview-gated quick publish.
7. Errors/health.
8. Multi-quantity.

Important unresolved Sprint 25 v2 point:

- UI restoration must not begin before Phase 0 diagnostic evidence.
- The API plan-gating explanation remains a hypothesis until a real diagnostic captures status/error/operation.
- Current local metadata does not prove a recent completed eBay OAuth reconnect after the later rotation discussion.
- Current eBay access token timestamp is old/expired, while the refresh token expiry is present. Do not treat this as a successful current reconnect without confirming in the live app.

## 4. Backend App Map

### `apps.core`

Purpose:

- Shared timestamp/UUID base models.
- SKU sequence.
- Backup/restore tooling.
- Management commands: `backup`, `restore`, `seed`, `export_items`.

Important files:

- `backend/apps/core/models.py`
- `backend/apps/core/backup_ops.py`
- `backend/apps/core/management/commands/backup.py`
- `backend/apps/core/management/commands/restore.py`
- `backend/apps/core/tests/test_sprint8.py`
- `backend/apps/core/tests/test_admin_routing.py`

Notes:

- Backup format is encrypted and restore is clean-target oriented.
- Admin routing has regression coverage because `/admin/` must not be swallowed by the SPA fallback.

### `apps.catalog`

Purpose:

- Product categories and category-specific schema/profile system.
- Banknotes, coins, stamps, gold, phones, etc.
- Per-category/per-field choice lists.

Important files:

- `backend/apps/catalog/models.py`
- `backend/apps/catalog/profiles.py`
- `backend/apps/catalog/field_choices.py`
- `backend/apps/catalog/field_choices.json`
- `backend/apps/catalog/views.py`
- `backend/apps/catalog/tests/test_sprint23.py`

Notes:

- `field_choices.json` is the data/config registry for picker values such as country and denomination.
- Banknotes are a real category with a profile schema.
- Catalogue references remain candidate-only in the suggestion/AI paths.

### `apps.inventory`

Purpose:

- Central item record and lifecycle.
- Quantity support: `quantity_total`; sold and remaining quantities are derived from active sales.
- Status, condition, cost fields, lot/source/disposition fields.

Important files:

- `backend/apps/inventory/models.py`
- `backend/apps/inventory/serializers.py`
- `backend/apps/inventory/views.py`
- `backend/apps/inventory/tests/test_sprint1.py`

Core model:

- `InventoryItem`
  - SKU/title/category/status/condition.
  - Quantity total.
  - Location/acquisition/lot/source/disposition.
  - Acquisition/refurb/inbound/outbound/packaging cost fields.
  - Estimated/min/target price.
  - JSON `attributes`.
  - Derived quantity methods.

### `apps.photos`

Purpose:

- Photo upload and processing.
- EXIF stripping.
- Photo derivatives/fix-up pipeline.
- Local non-destructive photo fix-up from Sprint 17.

Important files:

- `backend/apps/photos/models.py`
- `backend/apps/photos/services.py`
- `backend/apps/photos/fixup.py`
- `backend/apps/photos/views.py`
- `backend/apps/photos/tests/test_sprint1.py`
- `backend/apps/photos/tests/test_sprint17.py`

Core models:

- `PhotoAsset`
- `PhotoDerivative`

Endpoints/actions:

- Upload/list photos through router.
- `fixup`
- `fixup/approve`
- `fixup/reject`
- `fixup/tweak`
- `fixup/revert`

### `apps.research`

Purpose:

- Comparables and research records.
- Pricing evidence view.
- Descriptor-based evidence lookup.
- Fast comparable capture from link/screenshot/text.
- URL-only source link registry.

Important files:

- `backend/apps/research/models.py`
- `backend/apps/research/pricing_evidence.py`
- `backend/apps/research/descriptor_lookup.py`
- `backend/apps/research/comparable_capture.py`
- `backend/apps/research/pricing_sources.py`
- `backend/apps/research/links.py`
- `backend/apps/research/views.py`
- `backend/apps/research/tests/test_sprint14.py`
- `backend/apps/research/tests/test_comparable_capture.py`

Core models:

- `Comparable`
- `ResearchRecord`

Important rule:

- Marketplace result pages are not fetched or warehoused. Links are view-only; user-captured comparable records are the evidence.

### `apps.valuation`

Purpose:

- Valuation reports and fee schedules.
- Commodity/gold spot cache.
- Earlier valuation/profit projections.

Important files:

- `backend/apps/valuation/models.py`
- `backend/apps/valuation/services.py`
- `backend/apps/valuation/strategies.py`
- `backend/apps/valuation/views.py`
- `backend/apps/valuation/tests/test_sprint2.py`
- `backend/apps/valuation/tests/test_sprint3.py`

Core models:

- `FeeSchedule`
- `ValuationReport`
- `ValuationComparable`
- `MetalSpotCache`

Note:

- Sprint 18+ introduced more specific fee/profit handling under `apps.profit`; watch for duplicate fee concepts between `valuation.FeeSchedule` and `profit.ProfitSetting/services`.

### `apps.listing`

Purpose:

- Listing drafts, boilerplates, copy packs, channel listings, readiness, and eBay draft stage/publish entrypoints.

Important files:

- `backend/apps/listing/models.py`
- `backend/apps/listing/views.py`
- `backend/apps/listing/serializers.py`
- `backend/apps/listing/readiness.py`
- `backend/apps/listing/generators.py`
- `backend/apps/listing/specifics.py`
- `backend/apps/listing/copy_packs.py`
- `backend/apps/listing/copy_pack_templates.json`
- `backend/apps/listing/channel_listings.py`
- `backend/apps/listing/public_urls.py`
- `backend/apps/listing/tests/test_sprint5.py`
- `backend/apps/listing/tests/test_sprint22.py`

Core models:

- `ListingBoilerplate`
- `ListingDraft`
- `ChannelListing`

Listing draft fields:

- `status`, `channel`, `channel_data`
- title/subtitle/description
- fixed/auction format
- price/currency/quantity
- shipping note
- item specifics
- selected photo IDs/order
- generated metadata

Listing draft actions:

- generate fields
- readiness
- export
- stage
- withdraw
- aspects check
- staged review
- publish

Structural warning:

- There are currently multiple `GOLD-00002` drafts, mostly incomplete. Any structural changes should decide whether duplicate drafts are expected, selectable, or should be consolidated.

### `apps.sales`

Purpose:

- Source-of-record sales.
- Partial quantity sale support.
- Corrections/superseded rows.
- Valuation and fee snapshots at sale time.
- Item status recomputation after sale creation/correction.

Important files:

- `backend/apps/sales/models.py`
- `backend/apps/sales/services.py`
- `backend/apps/sales/serializers.py`
- `backend/apps/sales/views.py`
- `backend/apps/sales/tests/test_sprint10.py`

Core model:

- `SaleRecord`

Important rule:

- Active/non-superseded sales drive quantity sold/remaining and P&L; corrections do not double-count.

### `apps.ebay`

Purpose:

- eBay auth/OAuth, account policy snapshots, category/aspect calls, merchant location, order sync, staging, duplicate candidates, publish/stage adapters.

Important files:

- `backend/apps/ebay/models.py`
- `backend/apps/ebay/services.py`
- `backend/apps/ebay/adapters.py`
- `backend/apps/ebay/staging.py`
- `backend/apps/ebay/publishing.py`
- `backend/apps/ebay/aspects.py`
- `backend/apps/ebay/order_sync.py`
- `backend/apps/ebay/views.py`
- `backend/apps/ebay/constants.py`
- `backend/apps/ebay/tests/test_sprint6.py`
- `backend/apps/ebay/tests/test_sprint7.py`
- `backend/apps/ebay/tests/test_sprint11.py`

Core models:

- `EbayCredential`
- `EbayAppToken`
- `MerchantLocation`
- `OAuthState`
- `EbayAccountSnapshot`
- `EbayOrderSyncState`
- `EbayOrderStaging`
- `EbayOrderDuplicateCandidate`

HTTP confinement:

- Real eBay HTTP is expected to be confined to `backend/apps/ebay/adapters.py`.
- CI has a guard for marketplace/eBay host usage.

Current cached account state:

- eBay environment: production.
- Connected row exists.
- Missing scopes: none.
- Policy snapshot counts: payment `2`, fulfilment `9`, return `4`.
- Merchant location: `MARYBOROUGH-AU`, Maryborough VIC 3465.
- Current access-token timestamp in DB is old/expired. Reconnect/refresh status should be proven live before any publish diagnostic.

### `apps.dashboard`

Purpose:

- Command-centre dashboard live analytics and persisted KPI preferences.

Important files:

- `backend/apps/dashboard/models.py`
- `backend/apps/dashboard/analytics.py`
- `backend/apps/dashboard/views.py`
- `backend/apps/dashboard/serializers.py`
- `backend/apps/dashboard/tests/test_sprint12.py`

Core model:

- `DashboardPreference`

Endpoints:

- Summary, P&L, by category, estimate-vs-actual, aging, listing opportunities, preferences.

### `apps.intelligence`

Purpose:

- Field suggestions and human review.
- OCR-assisted entry.
- Duplicate image detection.
- Sold-search links.
- AI credentials, identify/price-assist, AI search terms/reference links.

Important files:

- `backend/apps/intelligence/models.py`
- `backend/apps/intelligence/suggestions.py`
- `backend/apps/intelligence/ocr.py`
- `backend/apps/intelligence/images.py`
- `backend/apps/intelligence/sold_search.py`
- `backend/apps/intelligence/identify_scope.py`
- `backend/apps/intelligence/identify_scope.json`
- `backend/apps/intelligence/ai_research.py`
- `backend/apps/intelligence/ai_adapters.py`
- `backend/apps/intelligence/reference_sources.py`
- `backend/apps/intelligence/views.py`
- `backend/apps/intelligence/tests/test_sprint13.py`
- `backend/apps/intelligence/tests/test_sprint15.py`
- `backend/apps/intelligence/tests/test_sprint24.py`

Core models:

- `FieldSuggestion`
- `ImageFingerprint`
- `AICredential`
- `AIResearchCall`
- `AIResearchSearchTerm`
- `AIReferenceLink`

Important rules:

- Nothing suggested by OCR/duplicate/AI becomes live item data without explicit Approve/Edit or Approve-all click.
- AI is for identification/search-term help, not pricing numbers.
- Reference links are view-only; no third-party images are stored.

### `apps.profit`

Purpose:

- Sprint 18+ profit engine, buy calculator, ledger, cash-lock, lots/sources, source ranking.

Important files:

- `backend/apps/profit/models.py`
- `backend/apps/profit/services.py`
- `backend/apps/profit/ledger.py`
- `backend/apps/profit/lots.py`
- `backend/apps/profit/views.py`
- `backend/apps/profit/serializers.py`
- `backend/apps/profit/tests/test_sprint18.py`
- `backend/apps/profit/tests/test_sprint19.py`
- `backend/apps/profit/tests/test_sprint20.py`
- `backend/apps/profit/tests/test_sprint21.py`

Core models:

- `ProfitSetting`
- `Source`
- `Lot`

Important warning:

- Sprint 25 v2 explicitly said not to assume one Pro Basic FVF percentage covers every category. Current `ProfitSetting` still has `pro_other_final_value_pct`, so category-specific/default-with-overrides fee support likely needs structural work before Pro Basic is trusted broadly.

## 5. API Surface Map

Root API prefix: `/api/`

Router resources:

- `/api/items/`
- `/api/photos/`
- `/api/categories/`
- `/api/locations/`
- `/api/acquisitions/`
- `/api/comparables/`
- `/api/research-records/`
- `/api/fee-schedules/`
- `/api/listing-drafts/`
- `/api/channel-listings/`
- `/api/listing-boilerplates/`
- `/api/sales/`
- `/api/field-suggestions/`
- `/api/ebay/order-staging/`
- `/api/ebay/order-duplicates/`
- `/api/audit-log/`
- `/api/sources/`
- `/api/lots/`

Selected custom endpoints:

- `/api/health/`
- `/api/items/<item_id>/valuation-reports/`
- `/api/items/<item_id>/listing-drafts/`
- `/api/items/<item_id>/copy-pack/`
- `/api/items/<item_id>/sales/`
- `/api/items/<item_id>/sold-searches/`
- `/api/items/<item_id>/ocr/`
- `/api/items/<item_id>/duplicate-scan/`
- `/api/items/<item_id>/ai/identify/`
- `/api/items/<item_id>/ai/price-assist/`
- `/api/items/<item_id>/ai/references/`
- `/api/ai/status/`
- `/api/ai/credential/`
- `/api/items/<item_id>/research-links/`
- `/api/items/<item_id>/pricing-evidence/`
- `/api/items/<item_id>/pricing-evidence/capture-draft/`
- `/api/metals/spot/`
- `/api/profit/settings/`
- `/api/profit/ledger/`
- `/api/profit/ledger.csv`
- `/api/profit/fees/preview/`
- `/api/buy-calculator/evidence/`
- `/api/buy-calculator/calculate/`
- `/api/buy-calculator/bought-it/`
- `/api/evidence/lookup/`
- `/api/evidence/capture/`
- `/api/ebay/connect/start/`
- `/api/ebay/connect/complete/`
- `/api/ebay/disconnect/`
- `/api/ebay/status/`
- `/api/ebay/orders/sync/`
- `/api/ebay/refresh-policies/`
- `/api/ebay/category-suggestions/`
- `/api/ebay/category-aspects/`
- `/api/ebay/merchant-location/`
- `/api/items/export.csv`
- `/api/dashboard/summary/`
- `/api/dashboard/preferences/`
- `/api/analytics/summary/`
- `/api/analytics/pnl/`
- `/api/analytics/by-category/`
- `/api/analytics/estimate-vs-actual/`
- `/api/analytics/aging/`
- `/api/analytics/listing-opportunities/`

Authentication:

- DRF uses Django `SessionAuthentication`.
- Default permission is `IsAuthenticated`.
- SPA unauthenticated states should point to a working `/admin/login/` route.

## 6. Frontend Map

Stack:

- React 18
- Vite
- TypeScript
- React Router
- TanStack Query
- Recharts
- Lucide icons
- Tailwind plus substantial custom CSS in `frontend/src/styles/index.css`

Top-level routes in `frontend/src/routes.tsx`:

- `/` and `/dashboard` -> `Dashboard`
- `/inventory` -> `InventoryGrid`
- `/inventory/:id` -> `ItemDetail`
- `/sales` -> `SalesList`
- `/profit` -> `ProfitPage`
- `/listings` -> `ChannelListingsPage`
- `/lots` -> `LotsPage`
- `/lots/:id` -> `LotDetail`
- `/buy-calculator` -> `BuyCalculator`
- `/ebay/orders` -> `EbayOrders`
- `/add` -> `AddItem`
- `/settings/ebay` -> `EbaySettings`
- `/admin/*` -> `AdminRouteRecovery`

Navigation:

- `frontend/src/components/AppShell.tsx`
- Desktop sidebar and mobile bottom nav share the same item list.
- Mobile nav has 10 items but renders in a 5-column grid, so it spans two rows.

Item detail structure:

- `frontend/src/features/inventory/ItemDetail.tsx`
- Collapsible sections:
  - Photos
  - Core details
  - Category specifics
  - AI research
  - Pricing evidence & comps
  - Listings / channels
  - Sales & valuations
- Imported panels/components:
  - `PhotoFixupPanel`
  - `AIResearchPanel`
  - `SuggestionReviewPanel`
  - `DescriptorEvidencePanel`
  - `PricingEvidencePanel`
  - `SoldSearchPanel`
  - `ResearchLinks`
  - `ComparableList`
  - `TakeDownChecklist`
  - `CopyPackPanel`
  - `QuickPublishPanel`
  - `ListingPanel`
  - `ValuationPanel`
  - `ProfitBreakdown`
  - `SalesPanel`

Listing UI split:

- `QuickPublishPanel` is the Sprint 25 preview-gated quick path.
- `ListingPanel` is the fuller draft editor.
- `PublishPanel` is nested inside `ListingPanel` and exposes deeper eBay stage/review/publish controls.

This split is now a key structural seam. If Claude reorganises listing UX, decide whether these become one unified editor/preview flow or remain separate quick/full paths.

## 7. eBay Listing/Publish State

Current local publish-related state:

- `STM-00003` has a published local draft with category `Postage Stamps` / ID `105848`, condition ID `3000`, policies set, merchant location `MARYBOROUGH-AU`, and listing ID `127919720667`.
- One active `ChannelListing` exists for `STM-00003` on eBay.
- `GOLD-00002` has five local drafts:
  - Four have no eBay category/policy/condition/location mapping.
  - One has cached category `Nugget` / ID `139965`, tree `15`, but still has no condition, policies, merchant location, or price.
- `GSP-00001` has one draft with price `8.00` and four photos, but no eBay category/policy/condition/location mapping.
- `PH-00001` has a draft with price `199.00`, but no photos or eBay mapping.

Cached eBay account options:

- Payment policies: 2
- Fulfilment/postage policies: 9
- Return policies: 4
- Merchant location: `MARYBOROUGH-AU`, Maryborough VIC 3465

Sprint 25 v2 important constraints:

- Category alternatives and valid condition options should be fetched after reconnect from live eBay taxonomy.
- Business policies should be refreshed after reconnect and selectable as dropdowns.
- Price, format, duration, quantity, policies, merchant location, photos/order, category, condition, and item specifics should all be user-selectable before preview/post.
- Do not silently choose category, policy, condition, price, duration, or quantity.
- Do not call `publishOffer` until owner explicitly approves exact item, SKU, price, postage, final preview.

## 8. CI, Tests, and Evidence

Workflow:

- `.github/workflows/postgresql-validation.yml`
- Display name: `Validation`
- Jobs:
  - `sqlite`
  - `postgres`

SQLite job currently does:

- Django check
- Migrate
- Migration check
- Seed
- Marketplace URL-only confinement guard
- Backend tests
- Encrypted backup creation
- Restore spot-check
- Frontend install/test/typecheck/build
- collectstatic
- deploy check
- Waitress/WhiteNoise smoke

PostgreSQL job currently does:

- Django check
- PostgreSQL migrate
- Migration check
- Seed
- eBay schema/fake adapter assertion
- Backend tests

Evidence files exist from Sprints 10 through 25, plus Sprint 6 production connect and Sprint 9 robustness evidence.

Important evidence location patterns:

- Root: `SPRINT*_EVIDENCE.md`
- Screenshots: `docs/evidence/`, `evidence/`, `evidence/screenshots/`

Tests were not rerun for this audit. This document is a structural read-only audit, not validation proof.

## 9. Current Structural Risk Areas

### Listing/eBay UX is fragmented

Listing-related user paths are spread across:

- `QuickPublishPanel`
- `ListingPanel`
- `PublishPanel`
- `CopyPackPanel`
- `ChannelListingsPage`
- `EbaySettings`
- backend `apps.listing`
- backend `apps.ebay`

Sprint 25 v2 likely needs a deliberate unification:

- Full editable listing draft editor.
- Explicit policy/category/condition dropdowns.
- Preview with hard gates.
- Stage diagnostic.
- Publish only after exact final confirmation.

### Multiple listing drafts per item

`GOLD-00002` currently has five drafts. Structural changes should define:

- Which draft is canonical.
- Whether duplicate drafts are allowed.
- Whether stale/incomplete drafts should be hidden, archived, or merged.
- How quick publish chooses a draft.

### Fee model is under-specified for Pro Basic

Current profit setting has a default `pro_other_final_value_pct`. Sprint 25 v2 says not to assume one Pro Basic FVF percentage across every category.

Needed structural direction:

- Category-specific Pro fee schedule, or
- Default Pro rate plus explicit category/listing overrides.
- Unconfigured categories must show “fee rate not configured.”
- Do not silently use an unrelated percentage.

### eBay reconnect status is not proven current

Current eBay DB row exists, but the access token expiry shown in metadata is old. Treat reconnect/refresh as an operational gate before any live diagnostic.

### Evidence file drift

Sprint 24 and Sprint 25 evidence files may not reflect all later owner confirmations in chat. If Claude relies on evidence files, update them deliberately instead of assuming chat state.

### UI visual language has mixed eras

Some older panels still use dark/slate styling (`ValuationPanel`, parts of `ListingPanel`) while later sprints moved to bright high-contrast mobile-first tokens. Structural UI changes should decide whether to fully migrate old panels to the Sprint 16+ visual system.

### Session auth and admin route

The app uses Django session auth. `/admin/login/` must remain reachable and not be swallowed by React/PWA fallback. There are regression tests for this; preserve them.

## 10. Suggested Refactor Boundaries for Claude

If Claude is planning structural changes, the safest boundaries are:

1. Keep backend domain apps distinct:
   - Inventory/items
   - Listing drafts/channels
   - eBay integration
   - Profit/ledger/calculator
   - Intelligence/suggestions
   - Research/comparables
   - Photos

2. Consider a frontend feature-shell refactor:
   - Item detail is now the largest composition point.
   - Listing/channel/eBay panels could become one feature module.
   - Pricing evidence/capture/comparables could become one feature module.
   - AI/suggestions could become one feature module.

3. For Sprint 25, do not refactor everything first:
   - First complete rotation/reconnect/diagnostic evidence.
   - Then audit the old Phase-4 feature list.
   - Then restore full listing workflow.
   - Then integrate quick publish on top of the restored draft editor.

4. Preserve hard project rules:
   - No secrets in output or commits.
   - No scraping or marketplace fetching outside approved eBay APIs.
   - No AI prices.
   - Human approval before item data or live publish.
   - SQLite runtime; PostgreSQL CI only.
   - Windows/NSSM/Waitress runtime.

## 11. Useful Commands

Non-secret runtime checks:

```powershell
git status --short
git rev-parse HEAD
sc.exe queryex Magpie
sc.exe qc Magpie
netstat -ano | findstr :8000
Invoke-WebRequest http://127.0.0.1:8000/api/health/ -UseBasicParsing
```

Backend local checks:

```powershell
cd backend
python manage.py check
python manage.py makemigrations --check --dry-run
python -m pytest -q
```

Frontend local checks:

```powershell
cd frontend
npm run test
npm run typecheck
npm run build
```

Production build/restart sequence, when approved:

```powershell
cd frontend
npm run build
cd ..\backend
python manage.py collectstatic --noinput
```

NSSM restart usually requires Administrator elevation.

## 12. Bottom Line

Magpie is no longer a small prototype. It is now a mature local business tool with:

- Inventory/photo management.
- Category schemas and banknotes support.
- OCR/AI staged suggestions with human approval.
- Comparable/evidence capture.
- Manual and synced sales.
- Profit ledger, buy calculator, lots, source ranking.
- Listing drafts, copy packs, channel board, and eBay integration.
- Windows production runtime through NSSM/Waitress/WhiteNoise.

The main structural pressure is the listing/eBay area: Sprint 25 v2 requires the old full publish capability, the new quick preview flow, policy/category/condition selection, stage diagnostics, and live publish confirmation to become one coherent and safe workflow.
