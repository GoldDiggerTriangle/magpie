# Sprint 15 Evidence - Cloud AI Deep-Dive + Reference Lookup

Date: 2026-06-15
Runtime checkout: `C:\Users\Regan\Documents\Codex\2026-06-13\reasoning-extra-high-i-approve-sprint-2`

## Provider Selection

Selected first real provider adapter: OpenAI, via a provider-agnostic `AiResearchAdapter` boundary.

Default model: `gpt-4.1-mini`, configurable per credential record.

Why:

- Multimodal/image support: OpenAI documentation supports image inputs, including base64 image data URLs and Responses API `input_image` content.
- Structured output: OpenAI documentation supports strict JSON-schema structured output, which fits Magpie's staged suggestion contract.
- Expected cost: OpenAI publishes API pricing and image-token pricing guidance. Magpie records per-call token usage and estimated cost, with a configurable monthly cap.
- Terms/data posture: OpenAI's API Platform documentation states API inputs/outputs are not used for training by default unless the organization opts in.
- Swap safety: the database stores provider/model metadata, while the app calls a provider-neutral port. The UI and `FieldSuggestion` model do not depend on OpenAI-specific response shapes.

Sources checked:

- https://developers.openai.com/api/docs/guides/images-vision
- https://developers.openai.com/api/docs/guides/structured-outputs
- https://openai.com/api/pricing/
- https://help.openai.com/en/articles/5722486-how-your-data-is-used-to-improve-model-performance

## Implementation Summary

- Added encrypted `AICredential` using the existing Fernet encrypted field pattern.
- Added `AIResearchCall`, `AIResearchSearchTerm`, and `AIReferenceLink`.
- Added provider-agnostic adapter types, deterministic fake adapter, and OpenAI adapter.
- Added no-key/disabled status endpoint and credential setup/disconnect endpoints.
- Added item-level `Identify & fill` and `Price-assist` API endpoints.
- Added EXIF-stripping send path for item photos before adapter calls.
- Mapped AI output into staged `FieldSuggestion(source=ai)` rows only.
- Reused Sprint 13 Approve/Edit/Reject review; candidate AI fields are review-only and do not write live data.
- Price-assist stores safe search terms only and feeds Sprint 14 pricing source links.
- Reference lookup stores view-only search links only; no third-party images are copied, cached, stored, embedded, or downloaded.
- Added visible usage/cap state in the UI.
- Extended backup row-count coverage for the new AI tables.

## Hard Prohibitions Checked

- No AI-produced price numbers are stored or displayed as prices.
- No AI-produced value bands, valuations, acquisition cost, profit, authoritative grade, or authoritative catalogue ID are written.
- No suggestion writes item data without explicit Approve/Edit.
- Candidate catalogue/grade leads remain review-only.
- No bulk/background AI run exists.
- No marketplace scraping/fetching/caching was added.
- Reference lookup stores only URLs.

## Local Validation

Backend:

- `python manage.py check` with SQLite: passed.
- `python manage.py makemigrations --check --dry-run --noinput`: passed.
- `python -m pytest apps/intelligence/tests/test_sprint15.py`: 10 passed.
- Full backend suite: 134 passed, 1 skipped.

Frontend:

- `npm run test -- AIResearchPanel.test.tsx`: 3 passed.
- `npm run typecheck`: passed.
- Full frontend suite: 72 passed.
- `npm run build`: passed.
- `collectstatic --noinput`: passed after frontend build.

Remote Validation:

- GitHub Actions Validation run `27524380329`: passed.
- SQLite job: passed.
- Postgres job: passed.

Warnings:

- Vite chunk-size warning remains present from the existing app build profile.
- Pytest reported a cache-write warning for `.pytest_cache`; tests still passed.

## Live Deployment State

Pre-migration encrypted backup:

- `backend\backups\magpie-backup-20260615-031718.tar.gz.enc`

Live migration:

- Applied `intelligence.0002_aicredential_alter_fieldsuggestion_source_and_more`.

Post-migration encrypted backup:

- `backend\backups\magpie-backup-20260615-032110.tar.gz.enc`

Restore spot-check:

- Restored `magpie-backup-20260615-032110.tar.gz.enc` to `.tmp\sprint15-restore-check`.
- Restored DB includes the new AI tables:
  - `intelligence_aicredential`
  - `intelligence_airesearchcall`
  - `intelligence_airesearchsearchterm`
  - `intelligence_aireferencelink`

Live data counts after migration:

- items=8
- photos=2
- valuations=5
- drafts=2
- credential=1
- comparables=4
- sales=4
- ebay_staging=4
- ai_credentials=0
- ai_research_calls=0
- ai_search_terms=0
- ai_reference_links=0

## Service Status

Post-restart service state:

- `Magpie` service reports `Running`.
- Service start type is `Automatic`.
- Port `0.0.0.0:8000` is listening, owned by PID 2916 at verification time.
- `GET http://localhost:8000/api/health/` returns 200.
- `GET http://localhost:8000/` returns 200.
- `GET http://localhost:8000/api/ai/status/` returns 403 when unauthenticated, proving the Sprint 15 route is live behind DRF authentication.
- Authenticated browser evidence against the running service returns `GET /api/ai/status/` 200 with `enabled=false`, provider `openai`, and a disabled reason present.
- `GET http://192.168.1.86:8000/api/health/` returns 200.
- `GET http://localhost:8000/` serves the built SPA with `Gold, Stamps & Phonetech` and built `/assets/index-*` references.

## Browser Evidence

Captured with a short-lived authenticated Django session created only for screenshot evidence and deleted by the harness afterward.

- Desktop screenshot: `docs\evidence\sprint15-ai-deep-dive-desktop.png`
- Phone screenshot: `docs\evidence\sprint15-ai-deep-dive-phone.png`

Browser assertions:

- Item detail shows the Cloud AI deep-dive panel.
- No-key state is graceful: disabled status is visible and the one-item-at-a-time setup copy is present.
- `Identify & fill` and `Price-assist search terms` buttons are present and disabled while no provider key is configured.
- Provider setup form is visible with provider/model/monthly-cap/API-key fields; the key field is password typed.
- Sharpened search terms and reference lookup areas are present and empty-state correctly.
- Existing human review panel remains present.
- No `Unable to load`, request-failed, or `NaN` text was present.

## Real Provider Validation

Completed on 2026-06-16 after Regan configured an OpenAI API key through Settings.

Live item:

- SKU: `STM-00003`
- Photos sent: 1
- EXIF stripping: true
- Provider: `openai`
- Model: `gpt-5.4-mini` (Sprint 16 updated the user-settable default before live validation)

Live call result:

- Identify call status: success.
- Suggestions created: 2.
- Search terms created: 4.
- Reference links created: 8.
- Estimated cost recorded: `0.001566`.
- Monthly usage changed from `0.000000` to `0.001566`.
- Remaining budget changed from `5.000000` to `4.998434`.

Human review proof:

- One staged AI suggestion was rejected through the API review path.
- Rejected suggestion source: `ai`.
- Rejected suggestion field: `ai_candidate.topic_theme`.
- Item data remained unchanged after rejection.
- Pending AI suggestions remaining for `STM-00003`: 1.

Audit / secret safety:

- Latest audit action: `ai.research.identify.completed`.
- Audit payload keys: `call_id`, `estimated_cost_usd`, `image_count`, `model_id`, `provider`, `reference_links_created`, `search_terms_created`, `suggestions_created`.
- Audit payload remained secret-free.
- `/api/ai/status/` remained configured/enabled and did not return the API key.
