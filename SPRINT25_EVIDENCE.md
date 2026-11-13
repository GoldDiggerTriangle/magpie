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
- Marketplace URL-only confinement guard:
  - First remote Validation run `29167656530` failed in the SQLite lane at `Assert marketplace URL-only confinement`.
  - Cause: Sprint 25 introduced legitimate view-only eBay listing URLs in the quick-publish UI and backend ChannelListing URL path, but the CI guard had not yet allow-listed those URL-only files.
  - Fix: moved backend public eBay item URLs into `backend/apps/listing/public_urls.py` and added only that helper plus `frontend/src/components/QuickPublishPanel.tsx` to the URL-only allow-list.
  - Local rerun of the guard after the fix: `Marketplace URL-only confinement passed.`
- Remote dual-lane GitHub Validation after the guard fix:
  - Head: `e559cfae3b010ecbd69d6ad0d039e76f9471974e`.
  - Run: `29167780890`.
  - SQLite: success.
  - Postgres: success.
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

## Live UI Defect Fix - eBay Category Mapping

Regan reported that the quick eBay preview blocked on `[Category mapping not set]`, but the item `Listings / channels` section did not expose a visible way to set the eBay category mapping.

Fix implemented:

- Added a clearly labelled `eBay category mapping` control directly inside `Listings / channels`, adjacent to the quick publish panel.
- Reused the existing Phase-4 category suggestion and `ListingDraft.channel_data` mapping path:
  - `category_id`
  - `category_tree_id`
  - `category_name`
- Category selection remains human-confirmed:
  - Magpie searches suggestions.
  - The user explicitly selects a leaf eBay category.
  - Magpie does not silently auto-apply a category.
- The quick preview now treats missing eBay category as a hard blocker.
- The blocker includes a `Set eBay category` action that closes the preview and focuses the category mapping control.
- Saving a selected mapping updates the draft immediately; reopening preview shows the selected category and clears the category blocker.
- Audited the other blockers:
  - Price: visible human evidence price field in the preview, with `Enter evidence price` action.
  - Postage / pickup: visible `eBay postage / pickup` control in `Listings / channels`, with `Set postage / pickup` action.
  - Condition: blocker links to the existing `Core details` section.
  - Photos: blocker links to the existing `Photos` section.

Validation for this defect fix:

- Focused frontend test:
  - Command: `npm run test -- QuickPublishPanel.test.tsx`
  - Result: `6 passed`.
- Full frontend suite:
  - Command: `npm run test`
  - Result: `123 passed`.
- Typecheck:
  - Command: `npm run typecheck`
  - Result: passed.
- Build:
  - Command: `npm run build`
  - Result: passed; existing Vite large chunk warning only.
- collectstatic:
  - Command: `python manage.py collectstatic --noinput`
  - Result: `7 static files copied`, `155 unmodified`, `425 post-processed`.

Regression coverage added:

- Missing category shows the `eBay category required` blocker.
- The `Set eBay category` action reaches and focuses the category mapping control.
- A selected category mapping persists through `updateListingDraft`.
- The preview displays the selected category as `Australian Stamps (105848)`.
- `Post live to eBay` remains disabled while required blockers are incomplete.

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

## Gate 0: OPEN - 13 November 2026 (AEDT)

This is an append-only prerequisite/rotation update, not Sprint 25 closure. Earlier sections are retained unchanged. No Phase 0 staging, publishing or UI restoration was performed. Event timestamps below are UTC unless marked AEDT.

### Owner Decisions And D-139

- Regan confirmed that both B and the former .env passphrase A are saved in his password manager before rotation work proceeded. No values were requested or recorded.
- D-139: B, the Windows user-level MAGPIE_BACKUP_PASSPHRASE, remains the only configured backup passphrase. It was not changed. The MAGPIE_BACKUP_PASSPHRASE assignment was removed from the live .env file.
- Direct comparison confirmed that the verification processes inherited B. python-dotenv uses override=False; scripts/backup.ps1 does not explicitly replace the inherited passphrase.
- Regan subsequently chose to retain EBAY_CLIENT_SECRET. It was not changed by Codex. A newly rotated Production Cert ID is therefore not claimed. Matching a retired checkout alone does not establish that a value is invalid or compromised.
- Regan explicitly authorised clearing the cached eBay app token as well as the eBay connection and AI credential.

### 12 November Readiness Summary

- Live checkout and NSSM application directory were confirmed as D:\Magpie\app and D:\Magpie\app\backend; actual port 8000 health returned 200.
- The earlier successful reconnect completed at 2026-11-12 10:56:03. The account-policy refresh at 10:58:01 returned 2 payment, 9 fulfilment and 5 return policies.
- The earlier readiness archive magpie-backup-20261112-120837.tar.gz.enc restored successfully with 46 tables and 64 media files. The historical July archive had also restored during that earlier check, but that run did not independently establish its A/B/C label.
- The earlier check did not prove actual automatic token renewal or every granted API permission. It did not prove the cause of historic publishing failures.
- During the current corrective preservation check, the 12 November readiness archive was independently restored with B: 46 tables, 702 rows, 64 media files. All media bytes matched the current live media tree.

### Passphrase Map

The full owner-supplied A/B/C map has not yet been pasted and remains OPEN. The following limited results are directly verified; they must not be presented as a complete local/cloud archive map.

| Archive | Location / Retention State | Verified Candidate | Evidence |
| --- | --- | --- | --- |
| magpie-backup-20260613-105908.tar.gz.enc | Oldest cloud archive; temporary download deleted | B | Restored: 30 tables, 339 rows, 6 media files |
| magpie-backup-20260713-112557.tar.gz.enc | Historical July archive in retired checkout scratch | OPEN | Earlier restore succeeded; candidate label not independently established in this run |
| magpie-backup-20261112-120837.tar.gz.enc | Retained in backend/backups/gate0-rotation-20261113 | B | Restored: 46 tables, 702 rows, 64 media files |
| magpie-backup-20261112-133800.tar.gz.enc | Original step 4 check copy no longer retained | B | Restore passed before rotation: 46 tables, 702 rows, 64 media files |
| magpie-backup-20261112-140828.tar.gz.enc | Original step 10 check copy no longer retained | B | Restore passed: 46 tables, 707 rows, 64 media files |
| magpie-backup-20261112-141311.tar.gz.enc | Retained in backend/backups/gate0-rotation-20261113 | B | Corrective checkpoint restored: 46 tables, 707 rows, 64 media files |

### Steps 2 To 8

- Step 2 PASS: execution identity was Regan; HEAD was afe9b351bd084c42aa6cd5a98be37352b9d7bfe0; initial git status contained only untracked CLAUDE_STRUCTURAL_AUDIT.md; NSSM AppDirectory was the live backend; health was 200; the process passphrase matched B without revealing values.
- Step 3a PASS: startup does not require the backup passphrase. Only backup/restore operations read it; other references are secret-free manifest names and marker lists.
- Step 3b PASS: the complete token-key-encrypted field inventory is EbayCredential.refresh_token, EbayCredential.access_token, EbayAppToken.access_token and AICredential.api_key.
- Existing clearing paths were used: apps.ebay.services.disconnect; the registered EbayAppTokenAdmin delete_queryset path, with the secret field deferred; and apps.intelligence.ai_research.disconnect_ai_credential. No API call is made by those clearing paths.
- Step 3c PARTIAL: no application business data was found encrypted with SECRET_KEY, but Django session data/signatures and authenticated-session hashes do depend on it. Session invalidation and re-login are expected; the literal claim that nothing stored depends on SECRET_KEY would be incorrect.
- Step 4 restore PASS: before local rotation, magpie-backup-20261112-133800.tar.gz.enc was created with B and restored in isolation. Result: 46 tables, 702 rows, 64 media files. The restored copy and plaintext archive were deleted. Retention of that exact encrypted copy later failed as described below.
- Step 5 OPEN by owner decision: the Production Cert ID was retained, not newly rotated by Codex.
- Step 6 PASS: SECRET_KEY and MAGPIE_TOKEN_ENCRYPTION_KEY were generated locally and written only into the existing live .env file at 2026-11-12 13:44:02.631522. Its backup-passphrase line was removed. No temporary secret copy was created. All other setting values were verified unchanged.
- Required names remained present: SECRET_KEY, MAGPIE_TOKEN_ENCRYPTION_KEY, DATABASE_URL, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, EBAY_ENV, EBAY_CLIENT_ID, EBAY_CLIENT_SECRET and EBAY_RU_NAME. B remained available separately through the inherited user environment.
- Step 7 PASS: clearing completed at 13:44:02.644516. eBay connection, cached app token and AI credential counts each changed from 1 to 0. All other table contents, excluding the expected audit additions, were compared in memory and remained unchanged. No network request was attempted.
- Step 8 PARTIAL: Regan reported restart/reconnection, and replacement credential rows appeared. However, the process actually serving port 8000 still predates the rotation and has not loaded the new encryption key; see the blocker below.

### Steps 9 And 10

- Health returned 200 after the owner's reported restart.
- The production eBay credential row was created at 2026-11-12 13:56:15.170248, later than rotation. The active AI credential was created at 14:04:42.411353. Metadata only was reported; no OpenAI request was made.
- These creation timestamps alone are insufficient to pass new-key usability: the replacement encrypted fields cannot be decrypted with the current .env key.
- Fresh post-rotation backup/restore with B passed: 46 tables, 707 rows, 64 media files. Every table count and all media bytes matched the live source at that point.
- In one child process only, MAGPIE_BACKUP_PASSPHRASE was removed from the environment. The unchanged backup command refused with exit code 1 and created zero archives. The user-level variable was untouched.
- The required oldest cloud archive was downloaded using the existing rclone configuration, without displaying that configuration. Restore with B passed: 30 tables, 339 rows, 6 media files. The download and restored copy were deleted immediately after the check.
- Live database counts and live media were unchanged by the backup/restore checks. No restore targeted the live database.

### Step 11: OPEN - Local Key Mismatch Before Any HTTP Call

- Check began at 2026-11-12 14:09:27.767323.
- The only forced credential-field update was access_token_expires_at, set to 14:04:28.875825, five minutes before the check's current time. No token value was manually modified.
- The existing get_access_token path failed locally with InvalidToken before an OAuth request or Account API read could be sent.
- Observed HTTP requests: 0. Refresh HTTP status: not obtained. Account-read HTTP status: not obtained. Payment-policy record count: not obtained. Refresh-success audit count since the check: 0.
- Configured refresh scope names are sell.inventory, sell.account.readonly, sell.fulfillment.readonly and sell.finances. No refresh request containing these scopes was sent, so eBay acceptance remains OPEN. The locally stored scope list is not independent proof of grants.

| Expiry Metadata | Before Check | After Local Failure |
| --- | --- | --- |
| access_token_expires_at | 2026-11-12 15:56:15.147272 | 2026-11-12 14:04:28.875825, deliberately expired |
| refresh_token_expires_at | 2028-05-13 01:56:15.147272 | Unchanged |
| last_refresh_at | Not set | Not set |
| credential updated_at | 2026-11-12 13:56:15.170286 | Unchanged |

- Read-only diagnosis found NSSM wrapper PID 4392 still running. Port 8000 was owned by python PID 5808, parent PID 5432, created on 12 November at 12:05:05 AEDT, before local rotation at 13 November 00:44:02 AEDT.
- Current .env local keys differ from the retired checkout's keys. No process/user/machine variable override for SECRET_KEY, MAGPIE_TOKEN_ENCRYPTION_KEY or EBAY_CLIENT_SECRET was found; NSSM had no AppEnvironment or AppEnvironmentExtra names configured.
- The newly entered eBay access/refresh tokens and AI key each decrypted with the retired key but not the current .env key. Only per-field counts and pass/fail comparisons were output. This confirms that re-entry occurred against the old-key serving process.
- No conclusion about eBay plan permissions or the validity of the retained client secret follows from this local failure.
- Required recovery: actually stop the Magpie service and verify that port 8000 is free, reset the old-key credential rows through the agreed application paths, start the service with the new .env configuration, then perform owner-led login/reconnection/key re-entry before retrying verification. No additional reset or restart was performed in this check.

### Backup Housekeeping Incident And Corrective Preservation

- The unchanged backup command retains one daily archive per output folder. Reusing the step 4 scratch output folder for step 10 caused its retention policy to prune the earlier same-day check archive.
- A subsequent preservation check failed because the expected pair of archives was no longer present. Scratch deletion was incorrectly allowed to continue after that failure, deleting the remaining step 10 check copy. This was an agent orchestration error. Neither exact check copy is claimed retained.
- Existing nightly backups, cloud backups and the earlier readiness archive were not deleted or modified by that incident.
- Corrective preservation used an isolated checkpoint folder, verified encrypted copies before cleanup, and retained two restore-tested archives in D:\Magpie\app\backend\backups\gate0-rotation-20261113: magpie-backup-20261112-120837.tar.gz.enc and magpie-backup-20261112-141311.tar.gz.enc.
- The earlier retained readiness archive restored with B to 46 tables, 702 rows and 64 media files. This is an available pre-rotation recovery point, not a claim to recover the deleted step 4 archive.
- The corrective current checkpoint restored with B to 46 tables, 707 rows and 64 media files. All live table counts and media bytes matched. Retained encrypted copies were verified byte-for-byte in memory before final cleanup.
- Step 12 PASS on corrective rerun: the resolved scratch path was checked, unexpected files/reparse points were refused, and D:\Magpie\scratch was deleted. No restored plaintext database, plaintext archive, media tree or cloud download remains there.

### Gate 0 Checklist

The exact updated spec section 1 checklist has not been supplied in this checkout; that verbatim comparison remains OPEN. These statuses map to the controlling owner instructions and do not invent a spec closure gate.

| Item | Status | Evidence |
| --- | --- | --- |
| Password-manager preservation of A and B | PASS | Owner confirmation before work |
| Regan identity, expected HEAD/status, live path and health | PASS | Step 2 checks |
| B unchanged and sole configured backup passphrase, D-139 | PASS | Direct equality checks; .env assignment absent |
| Startup independent of backup passphrase | PASS | Code audit and continuing live health |
| Complete encrypted-field/SECRET_KEY dependency audit | PARTIAL | Four encrypted fields identified; signed sessions explicitly depend on SECRET_KEY |
| Pre-rotation backup and isolated restore | PARTIAL | Restore passed; exact step 4 check archive was not retained; earlier recovery point preserved |
| New Production Cert ID installed | OPEN | Owner chose to retain the existing value |
| Local SECRET_KEY and token-key rotation | PASS | Name-only rotation at 13:44:02 UTC |
| Original credential/cache clearing | PASS | Counts 1 to 0 through existing application paths |
| Live service loaded the new keys | OPEN | Port 8000 process predates rotation; replacement rows use the old key |
| New credential rows created after rotation | PARTIAL | Timestamps pass, current-key decryptability fails |
| Post-rotation B restore and missing-B refusal | PASS | Table/media checks; zero-archive refusal |
| Oldest cloud archive restore with B | PASS | 30 tables, 339 rows, 6 media files |
| Automatic renewal and accepted requested scopes | OPEN | Local InvalidToken; zero HTTP requests |
| One read-only EBAY_AU Account policy read | OPEN | Not reached |
| Scratch cleanup and retained recovery points | PASS | Corrective guarded cleanup; two verified encrypted archives retained |
| Full passphrase map and exact spec section 1 reconciliation | OPEN | Awaiting owner's secret-free map/checklist |
| No secret disclosure, code/migration/dependency changes, Phase 0 or publishing | PASS | No secret values output; no source edits or publish/staging calls |

Only this evidence document was changed as a tracked repository file. CLAUDE_STRUCTURAL_AUDIT.md was left untracked and untouched. No test-suite/CI result, commit or push is claimed for this operational check. Gate 0 remains OPEN.

## Gate 0: OPEN - Verified Service Recovery And Owner Map, 13 November 2026

This follow-up appends new evidence without rewriting the earlier failure record. The serving-process/key mismatch is now resolved. Automatic renewal and the permitted Account API read passed. Gate 0 is not formally closed: the owner chose to retain the eBay client secret, whereas the supplied amended section 1 includes its rotation. No Phase 0 or UI work is authorised by this entry.

### Controlling Section 1 And Amendments Received

Regan supplied the Gate 0 wording from SPRINT_25_SPEC_v3.md, header v3.2, stating that v3.3 did not change section 1, plus MASTER_HANDOFF_UPDATE_2026-11-13. These owner-supplied requirements supersede the earlier note that the exact checklist was unavailable:

1. Complete this task's rotation of SECRET_KEY, MAGPIE_TOKEN_ENCRYPTION_KEY and the eBay Cert ID, remove A from .env, then reconnect through Settings under Pro Basic.
2. Prove post-reconnect token issuance, automatic refresh after local force-expiry, complete granted scopes, and a refreshed policy snapshot with fetched_at recorded, without revealing token values.
3. D-139 replaces passphrase rotation: B remains the only configured backup passphrase and is not changed. Evidence is historical B recovery, a new backup restoring with B, and refusal to back up without B.
4. The 12 November policy snapshot at 10:58:01 UTC with 2 payment, 9 fulfilment and 5 return policies satisfies the snapshot requirement unless the owner refreshes it again.
5. Gate 0 and Phase 0 must be reported before UI work starts.

No decision to retain EBAY_CLIENT_SECRET is silently represented as a completed rotation or a waiver of the amended gate. The owner's choice is preserved; that criterion stays OPEN.

### Actual Stop, Credential Reset And New Process

- Regan stopped the Windows service. Verification showed STOPPED, PID 0, with no listener on port 8000. The earlier concatenated PowerShell command had not performed the stop; entering the word stopped at the prompt was not an application operation.
- With the service stopped, the already-agreed application clearing paths were repeated at 2026-11-12 23:24:19.208446 UTC, or 13 November 10:24:19 AEDT. Connection/app-token/AI-credential counts changed from 1/0/1 to 0/0/0. Other table contents were unchanged except expected audit additions. No network request was attempted.
- After Regan started the service, NSSM was RUNNING with wrapper PID 12368. Port 8000 was served by python PID 7804, parent 24008, created at 13 November 2026 10:26:03.709040 AEDT, after the rotation. The live checkout/backend paths remained correct and health returned 200.
- Regan then logged in, reconnected eBay and saved the AI key through Settings. The new eBay credential was created at 2026-11-12 23:29:33.442130 UTC; the AI credential at 23:33:22.541450 UTC. Both are later than the verified fresh service start.
- The new eBay access token, refresh token and AI key each decrypted successfully with the current .env encryption key. Only populated/decryptable counts were reported. No OpenAI call was made.
- B remained equal to the process's inherited passphrase, and the live .env backup-passphrase assignment remained absent. B was not modified.

### Corrected-State Backup And Refusal Check

- At 2026-11-12 23:36 UTC, the unchanged backup command created magpie-backup-20261112-233630.tar.gz.enc in its own scratch output folder, with no upload. This avoided applying daily retention to an earlier check archive.
- Restore with B passed: 46 tables, 713 rows and 64 media files. Every table count and all media bytes matched the live source. All 3 restored populated credential fields also decrypted with the current token-encryption key.
- The encrypted archive, 27,953,462 bytes, was copied into backend/backups/gate0-rotation-20261113 and verified byte-for-byte before scratch deletion. No existing archive was overwritten or pruned.
- The one-child-process test without MAGPIE_BACKUP_PASSPHRASE was repeated. Backup refused with exit code 1 and wrote zero archives. User-level B was untouched.
- The earlier oldest-cloud restore with B remains valid evidence: magpie-backup-20260613-105908.tar.gz.enc restored to 30 tables, 339 rows and 6 media files. Its download and restored copy were deleted; it was not fetched again for this follow-up.
- Scratch paths were resolved and checked for unexpected files and reparse points. All restored plaintext copies were removed; D:\Magpie\scratch was then deleted. The three retained encrypted recovery points are 20261112-120837, 20261112-141311 and 20261112-233630 in backend/backups/gate0-rotation-20261113.
- The earlier housekeeping incident remains recorded above. The two lost check copies are not claimed recovered; these are separately identified retained recovery points.

### Automatic Renewal And One Read-Only Account Call: PASS

The existing production HttpEbayAuthAdapter, services.get_access_token and HttpEbayAccountAdapter.list_policies(kind=payment) were used unchanged. A process-local observer captured only HTTP statuses and allowed scope names; it did not log request headers, credentials, token bodies or raw provider payloads. No persistent code change was made.

| Operation | HTTP Status | Result |
| --- | --- | --- |
| OAuth access-token refresh | 200 | Refresh accepted the complete configured four-scope request |
| getPaymentPolicies, EBAY_AU | 200 | 2 payment-policy records returned |

- The run started at 2026-11-12 23:37:11.912677 UTC and completed at 23:37:14.967175 UTC, or 13 November 10:37 AEDT.
- Only access_token_expires_at was manually set, to current time minus five minutes. No token value or other credential field was manually changed to force renewal.
- Exactly one refresh and one Account API read occurred. No staging, inventory write, offer creation, publishing, identity lookup or additional Account API operation was performed.
- Requested scope names: sell.inventory, sell.account.readonly, sell.fulfillment.readonly and sell.finances. The request matched all four configured scopes, with none omitted, and eBay returned 200.
- The token response did not include a scope field. Therefore this proves successful acceptance of the complete requested set, not an independently returned granted-scope manifest or operational testing of inventory, fulfilment and finances endpoints. The saved scope list is generated locally by complete_connect and is not represented as authoritative provider output.
- One ebay.token.refresh.completed audit row was recorded. Its payload field-name set was exactly environment; no credential payload was recorded.
- Other table contents were compared in memory and unchanged by the renewal check. Expected credential updates and the secret-free refresh audit were the only database changes.

| Metadata, UTC | Before | Forced Expiry | After Successful Renewal |
| --- | --- | --- | --- |
| access_token_expires_at | 2026-11-13 01:29:33.441103 | 2026-11-12 23:32:13.085878 | 2026-11-13 01:37:13.738035 |
| refresh_token_expires_at | 2028-05-13 11:29:33.441103 | Not manually changed | Unchanged |
| last_refresh_at | Not set | Not manually changed | 2026-11-12 23:37:13.738058 |
| credential updated_at | 2026-11-12 23:29:33.442147 | Not manually changed | 2026-11-12 23:37:13.738231 |

The policy snapshot remains fetched_at 2026-11-12 10:58:01.274750 UTC, with 2 payment, 9 fulfilment and 5 return policies. This is the snapshot explicitly accepted by the owner amendment. The single permitted live read was not silently expanded into a full snapshot refresh.

### Owner-Supplied Passphrase Map

Provenance: Regan reports running magpie-passphrase-map.ps1 as himself on 13 November 2026 at 00:13 AEDT, restoring each tested archive into D:\Magpie\scratch and deleting restored data immediately. No secret values were shown. This is owner-supplied evidence, distinguished from the limited independent verification above.

- A means the historical passphrase formerly in D:\Magpie\app\backend\.env, now removed from active configuration and retained offline by Regan.
- B means the unchanged Windows user-level MAGPIE_BACKUP_PASSPHRASE.
- C refers to the 06-11 checkout .env. Regan reports that it has no backup-passphrase assignment, so C was not tested.
- Owner totals: 29 archives classified as real, with 1 restoring using A and 28 using B; 40 additional archives failed the restore command with both candidates. Cloud inventory was 71 archives. Oldest/newest and first-of-month selections covered June, July, September, October and November; no August cloud archive was reported.
- The original 12 November readiness archive was outside the owner's searched locations. It has since been independently restored with B as recorded above.
- Archive names below use the owner's supplied stems. D: nightly denotes D:\Magpie\app\backend\backups; C: denotes the retired C: checkout. Locations are owner-reported unless explicitly corroborated below. Dates embedded in archive names are not substituted for the owner's local calendar-month classification.

| Archive Stem | Owner-Reported Location | Restores With |
| --- | --- | --- |
| magpie-backup-20260613-105908 | Cloud, oldest | B |
| magpie-backup-20260613-205446 | C: folder | A |
| magpie-backup-20260613-232008 | C: folder | B |
| magpie-backup-20260614-031153 | C: folder | B |
| magpie-backup-20260614-041510 | C: folder | B |
| magpie-backup-20260630-160005 | Cloud | B |
| magpie-backup-20260713-112557 | C: .tmp/sprint25v2-backups | B |
| magpie-backup-20260903-160006 | Cloud | B |
| magpie-backup-20260907-160006 | C: folder | B |
| magpie-backup-20260917-160006 | C: folder | B |
| magpie-backup-20260927-160010 | C: folder | B |
| magpie-backup-20260930-160006 | Cloud | B |
| magpie-backup-20261004-160007 | C: folder | B |
| magpie-backup-20261011-160009 | D: nightly | B |
| magpie-backup-20261017-160006 | C: folder | B |
| magpie-backup-20261018-160008 | D: nightly | B |
| magpie-backup-20261019-160006 | C: folder | B |
| magpie-backup-20261020-160008 | C: folder | B |
| magpie-backup-20261024-160008 | C: folder | B |
| magpie-backup-20261025-160009 | D: nightly | B |
| magpie-backup-20261031-181146 | Cloud | B |
| magpie-backup-20261101-160018 | D: nightly | B |
| magpie-backup-20261105-160019 | D: nightly | B |
| magpie-backup-20261106-160016 | D: nightly | B |
| magpie-backup-20261107-160013 | D: nightly | B |
| magpie-backup-20261108-160015 | D: nightly | B |
| magpie-backup-20261109-160016 | D: nightly | B |
| magpie-backup-20261110-160013 | D: nightly | B |
| magpie-backup-20261111-160019 | D: nightly and cloud, newest in owner map | B |

For the following 40 owner-reported failures, the outcome is CommandError on restore using both A and B. That generic error does not independently establish whether decryption failed, the archive was malformed, or required restore contents were absent. No additional passphrase guesses or tests were performed against them.

| Failed Stem, As Supplied | Owner Location | Classification Evidence |
| --- | --- | --- |
| source | C: folder | Matching source.tar.gz.enc name occurs in encryption/tamper test code; full file location not independently confirmed |
| tampered | C: folder | Matching tampered.tar.gz.enc name occurs in encryption/tamper test code; full file location not independently confirmed |
| magpie-backup-20260604-020000 | C: folder | Not independently classified |
| magpie-backup-20260612-020000 | C: folder | Not independently classified |
| magpie-backup-20260613-020000 | C: folder | Not independently classified |
| magpie-backup-20260613-120439 | C: folder | Not independently classified |
| magpie-backup-20260613-120440 | C: folder | Not independently classified |
| magpie-backup-20260613-120441 | C: folder | Not independently classified |
| magpie-backup-20260613-120442 | C: folder | Not independently classified |
| magpie-backup-20260613-120743 | C: .tmp/sprint9-backups | Documented operational backup invocation; not proven disposable |
| magpie-backup-20260613-124003 | C: folder | Not independently classified |
| magpie-backup-20260613-124004 | C: folder | Not independently classified |
| magpie-backup-20260613-124005 | C: folder | Not independently classified |
| magpie-backup-20260613-124006 | C: folder | Not independently classified |
| magpie-backup-20260614-023226 | C: folder | Not independently classified |
| magpie-backup-20260614-024203 | C: folder | Not independently classified |
| magpie-backup-20260614-024204 | C: folder | Not independently classified |
| magpie-backup-20260614-024205 | C: folder | Not independently classified |
| magpie-backup-20260614-024206 | C: folder | Not independently classified |
| magpie-backup-20260614-024622 | C: folder | Not independently classified |
| magpie-backup-20260614-024623 | C: folder | Not independently classified |
| magpie-backup-20260614-024624 | C: folder | Not independently classified |
| magpie-backup-20260614-024625 | C: folder | Not independently classified |
| magpie-backup-20260614-024626 | C: folder | Not independently classified |
| magpie-backup-20260614-031037 | C: folder | Not independently classified |
| magpie-backup-20260614-031038 | C: folder | Not independently classified |
| magpie-backup-20260614-031039 | C: folder | Not independently classified |
| magpie-backup-20260614-072732 | C: folder | Not independently classified |
| magpie-backup-20260614-072733 | C: folder | Not independently classified |
| magpie-backup-20260614-072734 | C: folder | Not independently classified |
| magpie-backup-20260614-072735 | C: folder | Not independently classified |
| magpie-backup-20260614-072736 | C: folder | Not independently classified |
| magpie-backup-20260614-072737 | C: folder | Not independently classified |
| magpie-backup-20260614-072959 | C: folder | Not independently classified |
| magpie-backup-20260614-073111 | C: folder | Not independently classified |
| magpie-backup-20260614-073112 | C: folder | Not independently classified |
| magpie-backup-20260614-073113 | C: folder | Not independently classified |
| magpie-backup-20260614-073114 | C: folder | Not independently classified |
| magpie-backup-20260614-073115 | C: folder | Not independently classified |
| magpie-backup-20260614-073116 | C: folder | Not independently classified |

### Independent Location Check: Not All Failures Can Be Dismissed

- A read-only listing corroborated the C: operational backup directories data-reconcile-backups, sprint10-live-pre-backup, sprint10-live-post-backup, sprint25v2-backups, sprint9-service-backups, and dated backend/backups entries.
- The failed 20260613-120743 file exists at C:\Users\Regan\Documents\Codex\2026-06-13\reasoning-extra-high-i-approve-sprint-2\.tmp\sprint9-backups\magpie-backup-20260613-120743.tar.gz.enc, size 25,663 bytes.
- ROBUSTNESS_EVIDENCE.md line 24 explicitly records a manage.py backup invocation producing that file. Its .tmp location and small size do not prove that it is a disposable unit-test fixture or establish its business-data significance.
- Source analysis found source.tar.gz.enc and tampered.tar.gz.enc in backend/apps/core/tests/test_sprint8.py, test_encrypt_decrypt_round_trip_and_tamper_detection. This supports fixture-shaped naming for those two, without claiming access to their exact archive locations.
- Eight pytest-oriented directories in the retired checkout refused access during the read-only listing. No ACL, ownership or Windows configuration was changed to bypass that restriction.
- Therefore the blanket assessment that all 40 failed files are disposable test artefacts is NOT confirmed. Keep the unclassified files. No failed archive was modified or deleted, and no further secret was requested.

### Amended Gate 0 Status

| Controlling Item | Status | Current Evidence |
| --- | --- | --- |
| Item 1: local SECRET_KEY and token-encryption-key rotation; remove A | PASS | Names/time-only rotation record; current-key credential decryption passes; B unchanged |
| Item 1: Production eBay Cert ID rotation | OPEN | Owner explicitly retained existing EBAY_CLIENT_SECRET; no waiver inferred |
| Item 1: reconnect after actual new-key service start | PASS | Fresh process at 10:26 AEDT, eBay connection at 10:29 AEDT, current-key decryption passes |
| Item 2: access token minted after reconnect | PASS | Fresh code exchange, new credential/expiry metadata and subsequent successful renewal/read |
| Item 2: automatic refresh after force-expiry | PASS | Exactly one refresh, HTTP 200, new expiry/last_refresh_at and one secret-free audit |
| Item 2: complete configured scopes requested and accepted | PASS | All four configured scopes sent; eBay refresh HTTP 200 |
| Item 2: independently returned complete granted-scope manifest | PARTIAL | Response had no scope field; stored list is generated locally; no additional endpoint exercise claimed |
| Item 2: read-only Account policy call | PASS | Exactly one EBAY_AU payment-policy GET, HTTP 200, 2 records |
| Item 2: refreshed policy snapshot | PASS | Owner-approved fetched_at 2026-11-12 10:58:01.274750 UTC; counts 2/9/5 |
| Item 3 / D-139: B historical recovery evidence | PASS | Owner-supplied cross-history map plus independently restored oldest cloud and readiness archives; historical A exception retained offline |
| Item 3 / D-139: corrected-state backup restores with B | PASS | 46 tables, 713 rows, 64 media files; all 3 current-key encrypted credential fields verified |
| Item 3 / D-139: missing-B refusal | PASS | Repeated child-only omission, exit 1, zero archives; Windows B unchanged |
| Owner passphrase-map filing | PASS | Full 29 plus 40 reported-outcome map appended, provenance and limitations explicit |
| All failed archives proven disposable | OPEN | At least one documented operational backup and inaccessible pytest paths; no deletion authorised |
| Recovery points retained and plaintext/scratch cleaned | PASS | Three verified encrypted archives retained; scratch absent |
| No Phase 0, staging, publishing, UI/code/migration/dependency changes | PASS | No such actions; only permitted refresh/read and owned-backup operations |

The stale-service/key mismatch is resolved and the permitted functional verification is successful. This does not silently waive Cert ID rotation, create independent granted-scope evidence, or classify unrecovered archives as disposable. Gate 0 remains OPEN. No commit, push, CI run, OpenAI call or live listing action was performed.

## Gate 0: CLOSED - D-140 Close-Out, 13 November 2026

This is the current Gate 0 disposition. Earlier OPEN entries remain unchanged as historical evidence. Only Gate 0 is closed: Phase 0 has not been run or reported, Sprint 25 is not live-closed, and no staging, publishing or UI restoration is authorised by this entry.

### D-140: Item 1 PASS (D-140)

Regan's decision dated 13 November 2026, supplied as recorded in MASTER_HANDOFF_UPDATE_2026-11-13, explicitly keeps the eBay Cert ID, accepts the risk and changes the Gate 0 rotation criterion. Item 1 now counts as complete because SECRET_KEY and MAGPIE_TOKEN_ENCRYPTION_KEY were rotated, the backup passphrase was settled under D-139, and the Cert ID was retained under D-140.

Status: PASS (D-140). This does not claim that EBAY_CLIENT_SECRET was reset. No secret value was displayed, compared in the report or changed during these close-out checks. B and all application settings were left unchanged.

### Remaining Scope GET Checks: PASS

Exactly one read-only GET was made for each remaining scope through Magpie's existing shared apps.ebay.adapters._request_json HTTP client, using the configured production inventory/order/finances adapters' environment and timeout settings. Each request explicitly used limit=1. The automatically paginating limit-100 convenience methods were not invoked, so no hidden extra pages were requested. No source code or dependency was changed.

The existing access token was current and reused; no OAuth POST or token refresh occurred during this close-out run. A process-local request observer refused non-GETs, unexpected endpoints and repeated operations. The live SQLite connection was query-only, and all table contents were compared in memory before and after: unchanged.

| Scope | Read Operation | Host | HTTP Status | Returned Record Count | Proof Time, AEDT |
| --- | --- | --- | --- | ---: | --- |
| sell.account.readonly | getPaymentPolicies, EBAY_AU | api.ebay.com | 200 | 2 | 13 November 10:37, earlier recorded check |
| sell.inventory | getInventoryLocations, limit 1 | api.ebay.com | 200 | 1 | 13 November 10:59 |
| sell.fulfillment.readonly | getOrders, limit 1 | api.ebay.com | 200 | 0 | 13 November 10:59 |
| sell.finances | getTransactions, limit 1 | apiz.ebay.com | 200 | 1 | 13 November 10:59 |

- The three new GETs ran from 2026-11-12 23:59:11.515243 to 23:59:15.471645 UTC. No 403 occurred. No response contents, buyer/order details, transaction details, request headers or credentials were printed or persisted.
- The finances request used apiz.ebay.com, as required by F-16, and Magpie's existing marketplace header convention.
- The order result was honestly empty: HTTP 200 with zero returned records. It is permission evidence, not a claim about all historical sales.
- Together with the already-recorded account-policy read and successful automatic renewal, these operational 200 responses meet the owner's requested proof that the grant covers all four scopes Magpie uses. No separate provider-returned scope manifest is claimed or required by this close-out method.
- Successful reads are not proof that any particular staging or publish operation will succeed, and do not establish the cause of historic publishing failures. Those questions remain for the separately authorised Phase 0.

### Unrecoverable Operational Backup: Supersession Confirmed

File: magpie-backup-20260613-120743.tar.gz.enc, 25,663 bytes, in the retired checkout's .tmp/sprint9-backups directory. The owner map records unsuccessful restore with both known candidates A and B. No passphrase recovery, new guesses or new decryption attempt against that file was performed.

The operational purpose is documented in ROBUSTNESS_EVIDENCE.md:

- Line 24, under Local Validation Summary: the Sprint 8 backup check records `manage.py backup --output-dir ..\.tmp\sprint9-backups --no-upload` producing `magpie-backup-20260613-120743.tar.gz.enc`.
- Line 28 records the earlier runtime restore counts: items=6, photos=0, valuations=5, drafts=1, credential=0. The Data Checkout Reconciliation table at lines 78-81 confirms that pre-promotion runtime state, including zero media files, and contrasts it with the authoritative live source.
- The reconciliation records the replacement, not an inferred merge. Line 87 states: "Copied the live Sprint 8 `db.sqlite3` and `media_files` into the Sprint 9 runtime backend."
- Lines 92-94 document the post-promotion runtime as items=8, photos=2, valuations=5, drafts=2, credential=1, media files=6.
- Lines 105-106 identify the post-promotion encrypted backup magpie-backup-20260613-232008.tar.gz.enc in .tmp/data-reconcile-backups and record its successful restore with those replacement counts.

Independent close-out verification restored that later archive with B using the unchanged restore command. The temporary target was under D:\Magpie\scratch, not the live database. Result:

| Replacement Dataset | Items | Photos | Valuations | Drafts | Credential | Media Files |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Documented post-reconciliation runtime | 8 | 2 | 5 | 2 | 1 | 6 |
| Independently restored B archive 20260613-232008 | 8 | 2 | 5 | 2 | 1 | 6 |

The check completed at 2026-11-12 23:59:48.461807 UTC. SQLite integrity passed. The encrypted source archive was verified unchanged; the restored plaintext copy was deleted immediately and the checked scratch directory was deleted afterward.

Disposition: UNRECOVERABLE WITH THE KNOWN CANDIDATES AND SUPERSEDED. The supersession basis is the explicitly documented replacement of the earlier runtime dataset and the verified, later B-readable backup of the replacement state. It is not a claim that the old and new archives are byte-identical or that every old demo/runtime row was merged into the replacement. Generic CommandError does not independently prove an encryption-key failure.

The old file remains untouched. This classification is not permission to delete it or the other failed archives. The earlier caution against treating every failed file as a proven disposable pytest artefact remains valid and is not a Gate 0 deletion requirement.

### Current Controlling Gate 0 Checklist

All required items below are PASS. This current checklist supersedes the historical OPEN/PARTIAL statuses above without rewriting those observations.

| Controlling Item | Status | Evidence |
| --- | --- | --- |
| Item 1: rotation/reconnection prerequisite as amended | PASS (D-140) | Local keys rotated; A removed; B settled by D-139; retained Cert ID/risk explicitly accepted by D-140 |
| Item 1: reconnect after the actual new-key service start | PASS | Fresh service at 10:26 AEDT, connection at 10:29, current-key decryption verified |
| Item 2: fresh access token from owner reconnect | PASS | Fresh exchange/credential metadata after the new process; later successful renewal and reads |
| Item 2: automatic refresh after local force-expiry | PASS | Earlier single refresh HTTP 200; updated access expiry and last_refresh_at; secret-free audit |
| Item 2: scope coverage for every scope used by Magpie | PASS | Account, inventory, fulfilment and finances read operations each returned 200, with returned counts recorded |
| Item 2: policy snapshot and fetched_at | PASS | Owner-approved 2026-11-12 10:58:01.274750 UTC snapshot, counts 2 payment / 9 fulfilment / 5 return |
| Item 3 / D-139: historical recovery evidence | PASS | Owner cross-history map, independent oldest-cloud/readiness recovery, A retained offline, and documented resolution of the known unopened operational backup |
| Item 3 / D-139: corrected-state backup restores with B | PASS | Retained 20261112-233630 archive: 46 tables, 713 rows, 64 media files and 3 current-key credential fields verified |
| Item 3 / D-139: missing-B backup refusal | PASS | Child-only omission refused with exit 1 and zero archives; user-level B unchanged |
| Close-out step 2: unopened operational backup disposition | PASS | Known-candidate recovery failure recorded; replacement reconciliation and B-readable 20260613-232008 verified |
| Plaintext isolation, cleanup and retained recovery points | PASS | All restores isolated under checked scratch; scratch absent; three verified encrypted recovery points retained |
| Secret discipline and operational limits | PASS | No secret values output, no settings/source/migration/dependency changes in close-out, no staging/publishing/UI work, no commit or push |
| Append-only evidence filing | PASS | D-140, GET results, counts, backup quotes/reconciliation and current checklist appended; earlier sections preserved |

Gate 0 is CLOSED under D-139, D-140 and the owner-specified operational scope-proof method. The remaining sprint and Phase 0 are not closed or begun by this result. HEAD remains afe9b351bd084c42aa6cd5a98be37352b9d7bfe0; no commit or push was performed. CLAUDE_STRUCTURAL_AUDIT.md remains untracked and untouched.

## Gate 0: CLOSED - Rechecked And Filed, 13 November 2026

This append-only entry records the owner's renewed close-out request and authorisation to commit/push the accumulated Gate 0 evidence. The earlier failure, recovery and close-out entries above remain intact. Task-start HEAD: f8145acdea51a93205971b9648f8a5da0d60a63d. The canonical handoff and Sprint 25 spec v3.3 were read before checking; no Phase 0, staging, publishing or UI work was performed.

### 1. Fresh Scope Checks: PASS

The unchanged Magpie shared HTTP client, `apps.ebay.adapters._request_json`, made exactly one production GET for each remaining scope, using the existing adapter environment/timeout configuration and `limit=1`. The paginating convenience methods were not called. A process-local network guard refused non-GET requests, unexpected endpoints and repeated requests. The valid existing access token was reused through `services.get_access_token`; no OAuth POST, forced expiry or refresh occurred in this repeat check.

| Scope | Operation | Host | HTTP Status | Returned Records | Checked At, UTC |
| --- | --- | --- | --- | ---: | --- |
| sell.inventory | getInventoryLocations, limit 1 | api.ebay.com | 200 | 1 | 2026-11-13 01:19:33.638909 |
| sell.fulfillment.readonly | getOrders, limit 1 | api.ebay.com | 200 | 0 | 2026-11-13 01:19:33.992659 |
| sell.finances | getTransactions, limit 1 | apiz.ebay.com | 200 | 1 | 2026-11-13 01:19:34.790037 |
| sell.account.readonly | getPaymentPolicies, EBAY_AU; earlier recorded check, not repeated | api.ebay.com | 200 | 2 | 2026-11-12 23:37:14.967175, earlier run completion |

The three fresh GETs ran from 01:19:33.176231 to 01:19:34.801831 UTC (12:19 AEDT, 13 November). No 403 occurred. Finances used apiz.ebay.com and the existing EBAY_AU marketplace-header convention (F-16). Record counts describe the returned page only; the empty orders page is permission evidence, not a historical-sales total.

The process used SQLite query-only mode. An in-memory comparison of every live table's contents before and after the requests found no changes. Request headers, credentials, token values, response bodies and buyer/transaction details were neither printed nor persisted. Only allowed status/count metadata is recorded here.

Current read-only metadata reconfirmed:

- Credential connected_at: 2026-11-12 23:29:33.524222 UTC, after the actual new-key service start recorded above.
- Last automatic refresh: 2026-11-12 23:37:13.738058 UTC; access expiry: 2026-11-13 01:37:13.738035 UTC. The prior forced-expiry/refresh proof above remains the renewal evidence; this repeat run did not refresh.
- Accepted policy snapshot fetched_at: 2026-11-12 10:58:01.274750 UTC; 2 payment, 9 fulfilment and 5 return policies. This is the snapshot accepted by the owner's amendment; no extra policy-refresh calls were added.

Together with the earlier Account API read and accepted four-scope refresh, these operational 200s establish coverage of every scope Magpie uses under the owner's requested method. They do not claim a provider-returned scope manifest, successful staging/publishing, or a cause for historic publish failures.

### 2. Unopened Operational Backup: Unrecoverable With Known Candidates And Superseded

The operational archive among the 40 unopened files is `magpie-backup-20260613-120743.tar.gz.enc` (25,663 bytes):

`C:\Users\Regan\Documents\Codex\2026-06-13\reasoning-extra-high-i-approve-sprint-2\.tmp\sprint9-backups\magpie-backup-20260613-120743.tar.gz.enc`

Its purpose and supersession are documented in [ROBUSTNESS_EVIDENCE.md](ROBUSTNESS_EVIDENCE.md):

- Line 24, Local Validation Summary: "`manage.py backup --output-dir ..\.tmp\sprint9-backups --no-upload` produced `magpie-backup-20260613-120743.tar.gz.enc`." It was the Sprint 8 backup check within Sprint 9 validation, not an assumed disposable fixture.
- Line 80 records the pre-promotion runtime: 6 items, 0 photos, 5 valuations, 1 draft, 0 credentials and 0 media files.
- Line 87 explicitly records the replacement: "Copied the live Sprint 8 `db.sqlite3` and `media_files` into the Sprint 9 runtime backend."
- Line 94 records the replacement runtime: 8 items, 2 photos, 5 valuations, 2 drafts, 1 credential and 6 media files.
- Lines 105-106 name `magpie-backup-20260613-232008.tar.gz.enc` in `.tmp\data-reconcile-backups` and document its restore with those replacement counts.

The later archive was independently restore-tested again with B, read directly from the unchanged Windows user variable, using Magpie's existing restore command unchanged. Its source is the retired checkout's `.tmp\data-reconcile-backups\magpie-backup-20260613-232008.tar.gz.enc`.

| Check | Result |
| --- | --- |
| Restore with candidate B | PASS |
| Completed at | 2026-11-13 01:21:13.427471 UTC (12:21 AEDT) |
| User tables / total rows | 30 / 339 |
| Items / photos / valuations / drafts / credential | 8 / 2 / 5 / 2 / 1 |
| Media files | 6 |
| SQLite integrity_check | PASS |
| Original encrypted archives unchanged | PASS; in-memory before/after comparisons |
| Scratch-only restore and cleanup | PASS; all decrypted/extracted data was under the checked `D:\Magpie\scratch` path and deleted; scratch root absent afterward |

One initial repeat-verifier assertion incorrectly assumed that the current restore counter returned only the five historical counters. The restore command itself succeeded; its scratch data was removed in the finally-cleanup path. The verifier was corrected only in memory to compare the five named counters within the larger counter set, and the complete repeat check above passed. No application code changed.

The owner map records failure to restore the old 120743 archive with A and B; no new attempt against that file, passphrase recovery or guessing was performed. Its status is **UNRECOVERABLE WITH THE KNOWN CANDIDATES AND SUPERSEDED**, based on the explicit replacement reconciliation and the independently B-readable replacement archive. This is not a claim that the two datasets were identical or every old row was merged. The old encrypted file remains untouched; no deletion of it or the other unopened archives is authorised.

### 3. D-140 And Current Gate 0 Checklist

**Item 1: PASS (D-140).** Regan's 2026-11-13 decision keeps the eBay Cert ID, not resets it. The accepted prerequisite is the completed SECRET_KEY and MAGPIE_TOKEN_ENCRYPTION_KEY rotation, the backup passphrase settled under D-139 (B only, not rotated), and the Cert ID retained with owner-accepted risk under D-140. Nothing in this entry claims an eBay client-secret reset.

The following current checklist supersedes earlier OPEN/PARTIAL dispositions without erasing their evidence:

| Gate 0 Item | Status | Evidence |
| --- | --- | --- |
| 1. Rotation prerequisite as amended | PASS (D-140) | Local-key rotation and A removal verified in the earlier recovery entry; B unchanged under D-139; Cert ID deliberately retained under D-140 |
| 1. Owner reconnect after the new-key service start | PASS | Earlier service/reconnect proof; connected_at reconfirmed as 2026-11-12 23:29:33.524222 UTC |
| 2. Fresh post-reconnect access token | PASS | Earlier exchange/current-key proof, subsequent automatic refresh and successful authenticated reads |
| 2. Automatic refresh after forced expiry | PASS | Earlier single refresh HTTP 200, accepted four-scope request, advanced expiry/last_refresh_at and secret-free audit |
| 2. Every used scope is operational | PASS | Three fresh GETs above plus the earlier Account policy GET: all 200; counts 1 / 0 / 1 / 2 |
| 2. Policy snapshot with fetched_at | PASS | Owner-accepted snapshot reconfirmed: 2026-11-12 10:58:01.274750 UTC; counts 2 / 9 / 5 |
| 3. Historical recoverability under D-139 | PASS | Owner map and earlier independent oldest-cloud/readiness tests; A retained offline; known unopened operational backup resolved by documented supersession and fresh B restore |
| 3. Post-rotation backup restores with B | PASS | Earlier retained 20261112-233630 test: 46 tables, 713 rows, 64 media files and current-key credential fields verified |
| 3. Missing-B backup refuses safely | PASS | Earlier child-only omission: exit 1, zero archives; Windows user B unchanged |
| Operational backup disposition | PASS | 120743 known-candidate failure retained honestly; reconciliation and 232008 B-readable replacement verified |
| Secret discipline and plaintext cleanup | PASS | GET-only checks; no credential output; query-only live DB; scratch plaintext deleted; whole-file secret scan required before commit |
| Evidence filing | PASS | Accumulated evidence preserved and this dated close-out appended; only these evidence and handoff documentation files are authorised for the requested commit/push |

**Gate 0: CLOSED.** Every required item is PASS under D-139, D-140 and the owner's operational scope-proof method. Phase 0 is neither executed nor closed, Sprint 25 is not live-closed, and no staging, publishing or UI work is authorised by this result. No application code, settings, environment file, Windows variable, schema or service configuration was changed or restarted in this task.

### 4. Filing And Scope Of Changes

The entire accumulated `SPRINT25_EVIDENCE.md` and the handoff change are checked for locally known secret values and credential patterns before staging. The only handoff edit is one section 9 session-log line; its header, snapshot, locked decisions, decision log and all other text remain unchanged, as explicitly requested. The current Gate 0 disposition is this evidence entry and that new session-log line; older OPEN snapshot wording is historical and was not silently rewritten.

The requested commit message is `Sprint 25 Gate 0 close-out evidence`. Only `SPRINT25_EVIDENCE.md` and `docs/MASTER_HANDOFF.md` are included. `CLAUDE_STRUCTURAL_AUDIT.md` remains untracked and untouched. Git publication is verified separately after the commit; this entry does not embed a self-referential commit hash or claim a new CI/test-suite run.
