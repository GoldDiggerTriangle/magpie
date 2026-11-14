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

## Phase 0: Diagnostic Staging Passed - 13 November 2026

**Disposition: staging passed; live publishing remains unproven.** This is the spec section 2 stop-and-report point. Gate 0 remains CLOSED. Phase 1, UI restoration and live publishing have not been started or authorised by this diagnostic result.

Task-start HEAD: `24e06cb4ddfe4fa842c43b67c8f9311a12993de8`. The canonical handoff v4.64, controlling Sprint 25 spec v3.3 and kickoff were read. Backend fixes were committed separately before the successful rerun: `f91f5b89f190a1aa919367b94715274e5bf28fe1` (`fix: unblock verified eBay staging preflight`).

### Item Identification And Existing Draft Selection

The initial read-only inventory check found:

| SKU | Item Title | Photos | Item Asking/Target Price, AUD | Source | eBay Drafts | Recorded Staged Offer |
| --- | --- | ---: | --- | --- | ---: | --- |
| GOLD-00001 | Small gold jewellery parcel | 0 | 334.69 | Existing item target_price; not a diagnostic price selection | 0 | None |
| GOLD-00002 | Australian Gold Nugget 1.4g Grams | 6 | Not set | No figure selected initially | 5 | None |

Regan explicitly selected `GOLD-00002`. Item ID: `4ab42c61-d9cb-428c-81bc-92278ad30f83`. No equivalence with GSP-00001 was assumed.

Existing draft `af013dd9-0611-431c-be4a-223c44ec4e06` was the most complete under the section 4 score: title, existing category mapping and photos were present (3/10 before refreshing required-aspect metadata). Each other draft had title and photos only (2/10). The required-aspects point was conservatively withheld until metadata was known; the live response later confirmed zero required aspects, without changing which draft ranked first. No draft was created, archived or deleted. All five lacked offer IDs and listing IDs before the diagnostic. The other four drafts remain untouched.

### Live Metadata And Regan's Explicit Picks

Business policies were refreshed through the existing account-snapshot service at `2026-11-13 04:35:00.954996 UTC`: 2 payment, 9 fulfilment and 5 return policies; business-policy opt-in confirmed. Merchant location and taxonomy were read live. Magpie's ordinary OAuth access-token refresh and application-token acquisition each returned HTTP 200 during metadata preparation; neither changed listings. Request headers, credentials and token responses were not output.

The live gold-nugget category candidate was `139965 - Nugget`, tree `15`, a leaf category. Other returned search hits were unrelated categories and were not silently selected. Category-specific metadata, fetched at `2026-11-13 04:36:00.300885 UTC`, returned:

- No required or recommended aspects. Eight optional aspects: Region of Origin, Country of Origin, Certification, Fineness, Brand/Mint, Composition, Era and Total Precious Metal Content.
- `itemConditionRequired=false`, with no condition choices. No New/Used value was invented and no authoritative grade was supplied.
- Fixed-price duration `GTC`; auction category durations 3, 5, 7 and 10 days. No auction was selected or attempted.

The live IDs, human policy names, postage charges, location and format/duration choices were presented before any draft edit. Regan replied:

> p1 f4 r5 $360 fixed price category:gold nugget location maryborough remove 24ct

| Field | Approved Value / ID | Human Name / Basis |
| --- | --- | --- |
| Item | GOLD-00002 | Australian Gold Nugget 1.4g Grams |
| Draft | af013dd9-0611-431c-be4a-223c44ec4e06 | Most complete existing draft |
| Price | AUD 360.00 | Regan's own figure; no estimate, valuation or AI price used |
| Quantity | 1 | Explicit task limit |
| Category | 139965; tree 15 | Nugget; owner confirmed gold-nugget category |
| Condition | Omitted | Live category metadata says not required and returns no choices |
| Payment | 82010246020 | PayPal:Money Transfer Accepted (P1) |
| Postage | 186497669020 | express 1 day reg inter. (F4) |
| F4 services | Existing policy, unchanged | 1-day handling; free domestic AU_Express; international AU_StandardInternational AUD 15.00 |
| Returns | 272504343020 | No Return Accepted (272504343020) (R5) |
| Merchant location | MARYBOROUGH-AU | Maryborough AU; enabled; Maryborough VIC 3465, AU |
| Format / duration | FIXED_PRICE / GTC | Owner selected fixed price; GTC is its returned duration |
| Listing title | 1.4g gold nugget | Existing title with the 24ct claim removed as directed |
| Photos | Six existing selected item photos | Own photos only; source files verified GPS-free before upload |

These picks were saved to the selected draft at `2026-11-13 05:15:21.893261 UTC`. Price provenance explicitly records Regan's own figure. The 24ct claim was removed from the draft title, description and item specifics. No new optional claims were added. The inventory item's existing attributes were not rewritten, no valuation/comparable/evidence-price row was created, and other drafts were not regenerated.

### Initial Failures And Separately Tested Backend Fix

1. The original `stage_draft` readiness guard failed locally: `Missing eBay staging field(s): condition_id.` HTTP status and eBay error ID: not applicable; zero network requests. This contradicted the live category metadata, rather than proving an eBay plan/permission failure.
2. A read-only `getOffers` preflight at `2026-11-13 05:19:57.048652 UTC` returned HTTP 404, eBay error `25713`, message `This Offer is not available.` for this new SKU/format. The existing client treated that exact no-offer response as fatal before creation.

The separate backend-only fix commit above:

- Adds the condition-policy read to the existing taxonomy adapter boundary and deterministic fake. A missing condition ID is allowed only when current metadata matches the exact category/marketplace, explicitly marks condition not required and provides no choices. Missing, mismatched, malformed or contrary metadata fails closed. No category ID is hardcoded as a production exemption.
- Omits the inventory `condition` field for that proven no-choice case; an unknown item grade is not converted into a made-up condition.
- Preserves typed HTTP status/error IDs and treats only HTTP 404 with the exact error-ID tuple `(25713,)` from `getOffers` as no offers. A 403 and other 404s still raise.
- Carries the explicitly selected `listing_duration=GTC` into the offer payload; no price, policy or category defaults were invented.

Tests cover the real-shaped optional-condition response both with an empty condition array and with the array omitted, required/mismatched/malformed-policy failures, no inferred condition, GTC transmission, no publish, and precise no-offer handling including permission/other-404 refusal.

Validation: the initial focused suite passed 29 tests. An initial full-suite harness globally disabled logging and caused only the logging-rotation test to fail (222 passed, 1 failed, 1 skipped); that harness-only setting was removed. The final full backend suite, including the added no-offer cases, passed **226 tests, 1 skipped**, 14 warnings, in 133.58 seconds. Tests used an isolated in-memory database, isolated credential settings and a socket-level no-network guard. No unrelated logging code was changed. Temporary test data under the checked `D:\Magpie\scratch\phase0-tests` path was deleted.

### Successful Rerun: Exact Operations And Results

The successful run used the freshly loaded backend at fix commit `f91f5b89f190a1aa919367b94715274e5bf28fe1`, from `2026-11-13 05:25:11.887969` to `05:25:22.955701 UTC` (16:25 AEDT). The existing `stage_draft`, HTTP media/inventory adapters and `staged_review` were used. Fee lookup used the same shared HTTP client and the official `getListingFees` request shape: one offer under `offers`, not a new publishing path.

| Order | Operation | Method / Host | HTTP | eBay Error ID | Message / Result |
| ---: | --- | --- | ---: | --- | --- |
| 1 | getOffers preflight | GET api.ebay.com | 404 | 25713 | This Offer is not available.; interpreted narrowly as no existing offer |
| 2 | getItemConditionPolicies | GET api.ebay.com | 200 | None | Exact category 139965, condition not required, no choices |
| 3 | getDefaultCategoryTreeId | GET api.ebay.com | 200 | None | EBAY_AU tree 15 |
| 4 | getItemAspectsForCategory | GET api.ebay.com | 200 | None | No required aspects missing |
| 5 | createImageFromFile, photo 1 | POST apim.ebay.com | 201 | None | EPS image created |
| 6 | createImageFromFile, photo 2 | POST apim.ebay.com | 201 | None | EPS image created |
| 7 | createImageFromFile, photo 3 | POST apim.ebay.com | 201 | None | EPS image created |
| 8 | createImageFromFile, photo 4 | POST apim.ebay.com | 201 | None | EPS image created |
| 9 | createImageFromFile, photo 5 | POST apim.ebay.com | 201 | None | EPS image created |
| 10 | createImageFromFile, photo 6 | POST apim.ebay.com | 201 | None | EPS image created |
| 11 | createOrReplaceInventoryItem | PUT api.ebay.com | 204 | None | GOLD-00002 inventory record accepted; no response body |
| 12 | getOffers recovery check | GET api.ebay.com | 404 | 25713 | This Offer is not available.; no offer to recover or update |
| 13 | createOffer | POST api.ebay.com | 201 | None | Unpublished offer 356038014011 created |
| 14 | getOffer / staged_review | GET api.ebay.com | 200 | None | UNPUBLISHED; no listing ID; AUD 360.00; quantity 1; FIXED_PRICE; GTC |
| 15 | getListingFees | POST api.ebay.com | 200 | None | Fee summary returned for EBAY_AU; no warnings |

No success response supplied an error message; `None` above means no returned eBay error, not an invented message. The two expected no-offer reads remain visibly recorded as HTTP 404/error 25713, not rewritten as HTTP 200.

### Offer And Fee Breakdown

**Offer ID: `356038014011`. Status: `UNPUBLISHED`. Listing ID: none.** The selected local draft is `staged`. Read-back confirmed price `360.0` AUD (the approved AUD 360.00), fixed price, GTC and quantity 1.

eBay's `getListingFees` returned these fields for the single requested offer's EBAY_AU summary:

| Fee Type | AUD |
| --- | ---: |
| ListingFee | 0.06 |
| InsertionFee | 0.06 |
| FeaturedGalleryFee | 0.00 |
| PrivateListingFee | 0.00 |
| BoldFee | 0.00 |
| ProPackPlusBundleFee | 0.00 |
| ListingDesignerFee | 0.00 |
| FixedPriceDurationFee | 0.00 |
| SubtitleFee | 0.00 |
| FeaturedFee | 0.00 |
| GalleryPlusFee | 0.00 |
| GiftIconFee | 0.00 |
| PhotoDisplayFee | 0.00 |
| HighLightFee | 0.00 |
| InternationalInsertionFee | 0.00 |
| ProPackBundleFee | 0.00 |
| CategoryFeaturedFee | 0.00 |
| AuctionLengthFee | 0.00 |
| BorderFee | 0.00 |
| ValuePackBundleFee | 0.00 |
| BasicUpgradePackBundleFee | 0.00 |
| GalleryFee | 0.00 |
| PhotoFee | 0.00 |
| ReserveFee | 0.00 |
| SchedulingFee | 0.00 |
| BuyItNowFee | 0.00 |
| MotorsGermanySearchFee | 0.00 |

ListingFee is the listing-fee total and InsertionFee is its component here, not a second charge to add: the returned listing total is **AUD 0.06**, not AUD 0.12. These are expected listing fees, not actual charged sale fees or a final-value-fee/profit calculation. No sale occurred and no final-value fee was inferred. References: [Inventory API specification, getListingFees](https://developer.ebay.com/api-docs/master/sell/inventory/openapi/3/sell_inventory_v1_oas3.json), [eBay fee-name definitions](https://developer.ebay.com/Devzone/XML/docs/Reference/eBay/types/ListingFeesType.html).

**F-12 reminder:** eBay purges uploaded pictures not used in a listing within 30 days. These six EPS uploads do not make an item live; later publishing must check picture availability rather than assume indefinite retention.

### Operational Limits And Stop Point

- Process-local request guards allowed only the specific metadata/read operations, six EPS uploads, the selected SKU inventory PUT, a single createOffer and the fee lookup. Payload assertions enforced the human's SKU, price, quantity, category, policies, location, GTC and absence of the removed 24ct claim.
- `publishOffer`: **0**. Withdraw: **0**. Delete: **0**. Offer update: **0**. No real marketplace listing was ended or made live.
- In-memory before/after comparisons confirmed the inventory item, other four drafts and all ChannelListing rows were unchanged. No auto-listing status or take-down row was fabricated.
- No migration, schema change, UI/layout change, service restart, bulk operation or AI call occurred. The running NSSM service was not claimed to have reloaded the backend fix; the diagnostic used a fresh backend process in the live checkout.
- No key, token, passphrase, .env value, request header, raw token response or credential payload was printed or included in evidence. Whole-file secret checks are performed before the documentation commit.
- Git publication covers the separate backend fix and this evidence/session-log filing only. No frontend/build/collectstatic or GitHub Validation result is claimed here unless separately recorded.

**Stop and report:** Phase 0 is complete with staging passed; live publishing remains unproven. Do not proceed to Phase 1 or call publishOffer without Regan's next instruction. A later live-publish gate must present and obtain approval for this exact item, price, SKU, postage and final preview.

### Phase 0 Validation Repair - 13 November 2026

**Scope:** repair the red Validation run before Phase 1. No eBay calls, UI changes, staging, publishing or Phase 1 audit were performed in this task. Backend fix commit: `08b6ae2325aeba66934dbe49a30903211101a78f`.

#### Failed Run And Last Green Comparison

Failed [Validation run 43372420422](https://github.com/GoldDiggerTriangle/magpie/actions/runs/43372420422) tested evidence commit `6bd6cae9f33f321e12aad83fd59991507054c856`, including Phase 0 fix `f91f5b89f190a1aa919367b94715274e5bf28fe1`.

| Lane | Failed Backend Job | Result |
| --- | --- | --- |
| SQLite | 131711045326 | 5 failed, 221 passed, 1 skipped; 94 warnings; 31.67 seconds |
| PostgreSQL | 131711045565 | 5 failed, 209 passed, 13 skipped; 92 warnings; 35.20 seconds |

Both lane logs were retrieved through GitHub's API using existing Git authentication, with credentials kept in memory. The same five pre-existing tests failed in both lanes:

- `apps/catalog/tests/test_sprint4.py::test_bullion_coin_uses_existing_commodity_valuation_strategies`
- `apps/valuation/tests/test_sprint2.py::test_valuation_api_create_set_current_research_links_profit_and_validation`
- `apps/valuation/tests/test_sprint3.py::test_commodity_live_report_snapshots_provenance`
- `apps/valuation/tests/test_sprint3.py::test_live_report_missing_inputs_422_and_unconfigured_fallback`
- `apps/valuation/tests/test_sprint3.py::test_live_override_with_reason_still_wins`

Nested valuation creation returned HTTP 400 with `item: This field is required.` instead of HTTP 201. The missing-input test likewise returned 400 before reaching its expected 422 validation path.

The last successful [Validation run 29173344886](https://github.com/GoldDiggerTriangle/magpie/actions/runs/29173344886) was created at `2026-07-12 00:12:17 UTC` for `afe9b351bd084c42aa6cd5a98be37352b9d7bfe0`; both jobs succeeded (PostgreSQL 86597988461; SQLite 86597988464). Its retained logs now return HTTP 410, so the exact July package versions are not claimed.

Git blob comparisons confirmed these eight paths were byte-identical at that last green commit, Phase 0 fix `f91f5b89` and failed-run tip `6bd6cae9`:

- `backend/requirements.txt`
- `backend/apps/valuation/models.py`
- `backend/apps/valuation/serializers.py`
- `backend/apps/valuation/views.py`
- `backend/apps/valuation/tests/test_sprint2.py`
- `backend/apps/valuation/tests/test_sprint3.py`
- `backend/apps/catalog/tests/test_sprint4.py`
- `.github/workflows/postgresql-validation.yml`

The affected valuation binding and unbounded DRF requirement therefore predate the Phase 0 change; this was dependency drift exposing an older compatibility gap, not an eBay Phase 0 test depending on this PC's credentials or paths.

#### Dependency Comparison And Controlled Reproduction

The live venv's `pip freeze --all` was compared with the fresh CI installation and CI's Python version. Selected differences:

| Component | Live Windows Venv | Failed CI, Both Lanes |
| --- | --- | --- |
| Python | 3.13.4 | 3.12.16 |
| Django | 5.2.15 | 5.2.19 |
| Django REST framework | 3.17.1 | 3.18.3 |
| django-filter | 25.2 | 26.2 |
| Pillow | 12.2.0 | 13.0.0 |
| cryptography | 49.0.0 | 50.0.2 |
| pytest | 9.0.3 | 9.2.0 |
| pytest-django | 4.12.0 | 4.14.0 |

The former `djangorestframework>=3.15` requirement allowed CI to select a newer DRF than the live venv. Installing only DRF 3.18.3 into `D:\Magpie\scratch\ci-drf-3183` and prepending that isolated path reproduced all five failures without any other package change: **5 failed in 9.49 seconds**, still using Python 3.13.4 and Django 5.2.15. Tests used an isolated in-memory SQLite database, process-local synthetic settings and a socket-level network prohibition. No real credential or Windows user-variable dependency was required. The live venv was not modified.

Cause: `ValuationReport` has a conditional `UniqueConstraint` over `item` when `is_current=True`. DRF 3.18.3 generates a uniqueness validator for this single-field conditional constraint; DRF 3.17.1 did not. The nested endpoint previously supplied the URL-owned item only during serializer creation/save, after `is_valid()`. The new validator therefore rejected a valid nested request before that late binding.

#### Smallest Fix And Regression Coverage

- Pin `djangorestframework==3.18.3` for repeatable installs rather than leaving this dependency unbounded.
- Copy the submitted data and bind `item` from the URL before serializer validation in `ItemValuationReportListCreateView.create`. A conflicting body-supplied item cannot override the URL.
- Add two parametrized regression cases: item absent from the body, and a different item explicitly supplied in the body. Each must create exactly the URL item's current report, return its ID and create no report for the other item.
- Preserve uniqueness validation, database constraints and existing test expectations. No test was weakened, skipped or removed. No other dependency was pinned or upgraded in this change.

Keeping the current DRF version also retains intervening security fixes instead of rolling back to 3.17.1; see the [official DRF release notes](https://github.com/encode/django-rest-framework/blob/main/docs/community/release-notes.md).

The five original failures plus the two new cases passed: **7 passed in 10.37 seconds**. The full local backend suite with the same isolated DRF 3.18.3 overlay and network prohibition then passed: **228 passed, 1 skipped, 14 warnings in 136.81 seconds**. Existing skips were unchanged. Both checked scratch directories (`ci-drf-3183` and `ci-drf-tests`) were deleted after testing, including synthetic test databases, media and backup fixtures.

#### Green Validation Proof

[Validation run 43375267166](https://github.com/GoldDiggerTriangle/magpie/actions/runs/43375267166) completed **successfully on both lanes** for fix commit `08b6ae2325aeba66934dbe49a30903211101a78f`.

| Lane | Job | Backend Result | Lane Conclusion |
| --- | --- | --- | --- |
| SQLite | 131720163381 | 228 passed, 1 skipped; 96 warnings; 31.03 seconds | success |
| PostgreSQL | 131720163071 | 216 passed, 13 skipped; 94 warnings; 36.76 seconds | success |

Both jobs used CI Python 3.12.16, Django 5.2.19 and the pinned DRF 3.18.3. SQLite also passed the marketplace URL-only guard, encrypted backup/restore, frontend tests, typecheck, build, collectstatic, deploy check and Waitress/WhiteNoise production smoke. PostgreSQL passed its migrations, committed-migration check, seed/schema/fake-adapter checks and full backend suite. No additional skips were introduced by the repair.

No live database, service, .env, Windows user variable, stored credential, inventory draft or staged offer was changed. The live venv remains on its prior versions; no live deployment/restart is claimed. Only the three-file backend/test/dependency fix and this evidence/session-log filing were committed. Whole-file secret checks precede publication; no credential values or raw authenticated logs are included.

**Stop and report:** the red Validation defect is resolved. Phase 0 remains staging-only; live publishing remains unproven. Phase 1 was not started.

## Sprint 25 Phase 1: Reachability Audit - 13 November 2026

**Written audit complete; stop and report before restoration.** Audited checkout: `D:\Magpie\app`, `main` at `abf682730df9b71c0ea2f0f9aefa899e6bacde29`. Controlling artifacts read: `docs/MASTER_HANDOFF.md` v4.64, `docs/specs/SPRINT_25_SPEC.md` v3.3, the v3.3 kickoff, and the existing untracked `CLAUDE_STRUCTURAL_AUDIT.md`. The latter remains unchanged and untracked. Its September inventory is historical context, not a fresh database/connection-health claim. The newer Phase 0 staging and Validation evidence above takes precedence over its old connection warning.

### Entry Gate: Latest Main Validation

GitHub's workflow API confirmed the newest `Validation` run on `main` was [43375662553](https://github.com/GoldDiggerTriangle/magpie/actions/runs/43375662553), created `2026-11-13 06:00:10 UTC`, **completed/success**:

| Lane | Job ID | Status | Conclusion |
| --- | ---: | --- | --- |
| PostgreSQL | 131721455273 | completed | success |
| SQLite | 131721455654 | completed | success |

That run tested `a36ce4b2236a99acd5e6bb46abd8a663af44ace0`, an ancestor of the audited HEAD. The intervening `abf6827` commit adds only the live-venv preparation handoff entry. There was no newer red/pending main Validation run when this gate was checked. This audit makes no new local test/build/deployment claim.

### Layout History: What Actually Changed

The three comparison points are:

| Point | Commit | Observed Layout / Publish Surface |
| --- | --- | --- |
| Phase 4 implementation | `fdbab2ac1d3f97c6232c903069d5af855a104b34`, 13 June 2026 | Photos plus a single item form, then a flat panel stack. `ListingPanel` contains `DraftEditor`, which renders `PublishPanel`: category, policies/location, stage, review, withdraw and exact-SKU confirmation. |
| Phase 4 safety checkpoint | `befa502151ea779d9d4a6a5e290f3e6c2400a47a`, 13 June 2026 | Same layout; hides staging/review/publish/withdraw for an already published status or listing ID. Includes the earlier category-leaf safety and persisted category-selection fixes. |
| Last commit before the first reorganisation | `b3aa7ca06e1db707ad69621a8876a79ed8ba8967`, 6 July 2026 | Still photos plus one form and a flat lower stack; includes the later AI/evidence/photo-fixup/sales/lot/copy-pack features. This is the exact parent of `5447a66`, not merely the last commit that edited ItemDetail. |
| Audited HEAD | `abf682730df9b71c0ea2f0f9aefa899e6bacde29`, 13 November 2026 | Seven collapsible sections, with a desktop section index; Quick Publish additionally sits between copy packs and the original Listing panel. |

Git history establishes:

1. `5447a66ecc54b7ba5da73d7c466ab1bf4811510e` (6 July, Sprint 24 Round 1) is the **first accordion reorganisation**. It replaces the flat page with Photos, Core details, Category specifics, AI research, Pricing evidence & comps, Listings / channels, and Sales & valuations. Photos/Core default open; the other five default closed. It adds Expand all/Collapse all, per-item localStorage state, section anchors and the desktop index. It relocates the existing panels rather than removing their JSX calls.
2. `6f1fa35159b697d171b59a716068fd47f61346b7` (6 July, Sprint 24 Round 2) retains those same seven sections and their order. It scopes the two form save payloads and adds the item-page safe-area frame; it is **not a second tabs/layout migration**. Structured suggestion rendering and quieter audit metadata also change in this round.
3. `b80eb4d1f5585bdd651264ed5b8af7ab477ad9ab` (12 July, Sprint 25 v1) retains the accordion structure and inserts `QuickPublishPanel` immediately before `ListingPanel`, after `CopyPackPanel`. Its copy-pack change is the Photo zip button fit fix. It does not restore or replace the old editor.
4. All **16 committed ItemDetail revisions** returned by `git log --all --follow` were checked. Three contain the accordion implementation; none contains an item-page tabs implementation, tablist/tabpanel roles or active/selected-tab navigation state. Earlier versions use the flat form/panel stack. **No shipped-in-git item-page tab variant was found.** This does not rule out an uncommitted/temporary build that is absent from git. The owner-reported live accordion is consistent with Sprint 24's committed screenshots and evidence; this task did not open the browser or attest the current served bundle.
5. `ListingPanel.tsx` is byte-identical at **all four checkpoints** (`fdbab2a`, `befa502`, pre-reorganisation, HEAD). `PublishPanel.tsx` is byte-identical at `befa502`, pre-reorganisation and HEAD. Its changes between the two Sprint 7 checkpoints are the category/error/published guards, not a later layout removal. `git diff afe9b351 HEAD -- frontend` is empty: November's Gate 0/Phase 0/CI/venv tasks made no frontend changes.

The correct diagnosis is therefore **loss of prominence plus fragmented state/paths**, not deletion of the Phase 4 editor or an orphaned import. Valid-condition/policy dropdowns and a duration selector were **already absent** at the Phase 4 and pre-reorganisation checkpoints; they must not be described as controls the accordion deleted.

### Reading The Restoration Checklist

**Rule: nothing fewer than before the reorganisation, and nothing fewer than Phase 4 on the eBay side.** The unchecked rows below are the checklist for later restoration/integrated verification; an unchecked row does not mean its feature is currently absent. Do not tick a row merely because an import exists.

- `P4` means the two Sprint 7 checkpoints above; `Pre` means `b3aa7ca`.
- `I` = mobile **Items** (desktop **Inventory**) -> select the item -> `/inventory/<id>`.
- `L` = `I` -> expand **Listings / channels** -> scroll past any take-down notice, **Ready-to-paste ad copy**, and **Post to eBay** -> **Listing** -> click the desired draft's title/status row (or **Create draft** if none exists).
- `P` = `L` -> scroll below the draft fields, Photos, Readiness and Export -> **eBay Publish**. It is nested in the selected draft editor, not a separate route.
- `Q` = `I` -> expand **Listings / channels** -> **Post to eBay** quick-publish card; its **Post to eBay** button opens the preview sheet.
- `S` = **Settings** -> `/settings/ebay`; `B` = mobile **List** / desktop **Listings** -> `/listings`; `O` = mobile **eBay** / desktop **eBay Orders** -> `/ebay/orders`.
- **reachable**: an explicit code-backed path exists after the stated section is opened. **only conditionally rendered**: requires the stated data/state/viewport; disabled gates are noted separately. **hidden**: no working path for that particular control/step, with the reason given; this can be an original omission rather than a removal. No required named surface was found **imported but never rendered**, and no pre-existing panel was found **removed** by the reorganisation.
- Collapsed ItemSection bodies use `hidden`, but keep their children mounted. Closed is a visibility state, not a guarantee that child queries cannot run. This is another reason this audit used git/source only, not live page navigation.

#### A. Whole Item Page

| Feature / Control / Step | Reachable Before (P4 / Pre) | Reachable At HEAD: Exact Path | Status | Commit That Changed It |
| --- | --- | --- | --- | --- |
| [ ] A01 Title/status/SKU header; delete item with confirmation | P4/Pre: page header and Delete dialog | `I` -> header; **Delete** -> confirm dialog | reachable | No reorganisation loss; `5447a66` retains header/dialog |
| [ ] A02 Session/login recovery | P4: passive admin-session message; Pre: full-page admin login link | `I` on item-load failure -> **Open admin login** -> `/admin/login/?next=...` | only conditionally rendered: item query error; current phone/PWA destination not exercised | `9a63251` adds auth state; `d67c42e` adds stale-worker/admin-route recovery |
| [ ] A03 Seven sections; Expand all/Collapse all; remembered state | P4/Pre: one unfolded page, no section controls | `I` -> section header, **Expand all** or **Collapse all**; reload retains per-item state | reachable; five sections start hidden by default | `5447a66` introduces grouping/state |
| [ ] A04 Desktop section index and deep links | P4/Pre: no item section index | `I` -> left index -> named section; `/inventory/<id>#ai-review` and the seven named section hashes open their section | only conditionally rendered: index at >=1024px; anchors exist on phone too | `5447a66`; `6f1fa35` adjusts safe-area frame |
| [ ] A05 Display gallery; main photo; order; delete photo | P4/Pre: top gallery | `I` -> **Photos** -> **Set main**, **Move earlier/later**, **Delete photo** -> confirmation | only conditionally rendered: photos exist; edge movement disabled | Container moves in `5447a66`; original gallery controls retained |
| [ ] A06 Camera/library upload and multi-selection | P4: single photo input; Pre: split camera/library chooser | `I` -> **Photos** -> **Take photo** or **Choose from library** -> **Upload selected** | reachable; upload disabled until a file is selected | `a79177c` splits inputs; `5447a66` moves container |
| [ ] A07 Local photo fix-up, single and batch generation | P4: absent; Pre: directly below gallery | `I` -> **Photos** -> **Local photo fix-up** -> **Generate review** or **Fix up all photos** | only conditionally rendered: own photos; no-photo empty state otherwise | `8c3ea05` adds fix-up; `5447a66` groups it |
| [ ] A08 Before/after; Tweak/Approve/Reject; revert | P4: absent; Pre: photo-fixup rows | Same fix-up row -> Rotate/Exposure/Contrast -> **Tweak**, **Approve**, **Reject**; approved row -> **Revert to original** | only conditionally rendered: pending derivative or approved version respectively | `8c3ea05`; container `5447a66` |
| [ ] A09 Core title/status/global condition/category/location/stock quantity and Save | P4: one item form (no partial-stock fields yet); Pre: same form plus quantity totals | `I` -> **Core details** -> edit fields -> **Save**; sold/remaining count is shown | reachable; quantity minimum respects recorded sold quantity | `707d5c7` adds stock semantics; `5447a66` splits form; `6f1fa35` scopes core save |
| [ ] A10 Category schema, Country/Denomination custom pickers, catalogue-ref repeater | P4: category schema in item form; Pre: Banknotes and real choice-list pickers included | `I` -> **Category specifics** -> named field/picker -> **Other / custom...** if needed; Catalogue refs -> **Add** -> section **Save** | only conditionally rendered: selected category/schema; catalogue candidates remain human-adjudicated | `a79177c`/`fab6a52`/`b3aa7ca` predate grouping; `5447a66` moves form |
| [ ] A11 Acquisition/refurb/inbound/outbound/packaging costs, estimated value, notes | P4/Pre: single item form | `I` -> **Category specifics** -> cost/Estimated value/Notes inputs -> that section's **Save** | reachable | `5447a66` relocates; `6f1fa35` prevents this save from sending stale title/core fields |
| [ ] A12 Lot/source/disposition/scrap date | P4: absent; Pre: item form | `I` -> **Category specifics** -> Lot/Source/Disposition/Scrapped date -> **Save** | reachable; Source disabled for lot members and inherited source displayed; backend locks remain authoritative | `b5a593d` adds lot fields; container `5447a66` |
| [ ] A13 AI status, provider/model/usage/cap; connect/disconnect | P4: absent; Pre: standalone AI panel | `I` -> **AI research** -> status card; no-key state -> **Connect provider** form; configured state -> **Disconnect AI provider** | only conditionally rendered: credential/configuration state | `c8df9e4`; grouping `5447a66`; sub-cent formatting also `5447a66` |
| [ ] A14 Identify & fill; Price-assist search terms; reference links | P4: absent; Pre: flat AI panel | `I` -> **AI research** -> **Identify & fill** or **Price-assist search terms**; search terms/reference links below | reachable; calls disabled unless configured/enabled and not busy; links require results | `c8df9e4`; container `5447a66`; no new call made in audit |
| [ ] A15 Completion banner -> suggestion review | P4: absent; Pre: result text, no review-navigation action | `I` -> **AI research** -> completed run -> **Review N staged suggestions ->** -> `#ai-review` | only conditionally rendered: run result with suggestions; header/section expands via parent callback | `5447a66` adds action and adjacent review |
| [ ] A16 OCR and duplicate-image staging | P4: absent; Pre: separate flat Suggested fields panel | `I` -> **AI research** -> **Suggested fields** -> **Run OCR** / **Scan duplicates** | reachable; unavailable-OCR message retained; no automatic item write | `da72d81`; moved next to AI in `5447a66` |
| [ ] A17 Per-field Approve/Edit/Reject and separate leads | P4: absent; Pre: Suggested fields below sold search | `I` -> **AI research** -> **Suggested fields** -> row -> **Approve**, edit input + **Edit**, or **Reject**; candidate-only row -> **Mark reviewed** | only conditionally rendered: pending rows/field permissions; low/candidate rows remain separate | `da72d81`/`c8df9e4`; `5447a66` adjacent placement; `fb43a7a` scoped editable-field normalisation |
| [ ] A18 Approve all shown | P4/Pre: absent | `I` -> **AI research** -> **Suggested fields** -> **Approve all shown** | reachable; disabled until query success, nonempty rendered pending set and not busy; explicit click only | `5447a66` |
| [ ] A19 Structured suggestion text, raw payload and audit metadata | P4: absent; Pre: generic suggestion values/rationale | Same review row -> readable value; **Raw payload** details toggle; quiet audit metadata line | only conditionally rendered: relevant structured payload/metadata | `6f1fa35` improves rendering/metadata; no candidate adjudication removed |
| [ ] A20 eBay sold angles, other pricing sources, assisted research/checklists | P4: Assisted research links; Pre: additional sold/multi-source links | `I` -> **Pricing evidence & comps** -> **Own sales first** source strip, **Search eBay sold**, then **Assisted research** links/checklist | reachable; links/results depend on local API data/category; open-only discipline retained | `da72d81`/`1f50572`; all moved under `5447a66` |
| [ ] A21 Descriptor evidence, known-basis stats, freshness/strength, capture | P4: absent; Pre: flat descriptor panel (internally folded on phone) | `I` -> **Pricing evidence & comps** -> tap **Item descriptor evidence** -> rows/stats -> **Fast capture comp** -> **Save approved comp** (refreshes lookup) | reachable; nested phone disclosure must also be opened; unknown-basis rows remain labelled | `cc291e8`; extra outer disclosure `5447a66` |
| [ ] A22 Use this evidence price from item detail | P4: absent; Pre: ItemDetail supplied no onUsePrice callback | No item-detail **Use this** button: `DescriptorEvidencePanel` only renders it when onUsePrice exists. Working callback belongs to **Buy** -> calculator -> evidence lookup | hidden on item detail; pre-existing omission, not removed by accordion | Item integration `cc291e8` omits callback; unchanged by `5447a66` |
| [ ] A23 Captured comps, price basis, edit/delete; pricing grids | P4: Comparables CRUD; Pre: also source-tagged capture and four grids | `I` -> **Pricing evidence & comps** -> **Capture verified comp** / **Comparables**; row Edit/Delete; grids by condition/grade, format, recency, source | reachable; row actions require records; fields default basis unknown | `1f50572`/Sprint 18 basis work; wrapper `5447a66` |
| [ ] A24 Link/screenshot/Live Text capture helper | P4/Pre: absent | `I` -> **Pricing evidence & comps** -> **Own sales first** -> **Fill capture form from screenshot or link** -> **Fill capture form** -> review Capture verified comp -> save | only conditionally rendered: pricing data available; local OCR availability disclosed; URL never fetched | `32429d1` adds helper after reorganisation; `3610e31` adds copied-text fallback |
| [ ] A25 Research note CRUD and links | P4/Pre: flat Research log | `I` -> **Pricing evidence & comps** -> **Research log** -> Source/Link label/Link URL/Note -> save; row **Edit research note** / **Delete research note** | reachable; row actions require notes | Existing Phase 2 panel; container `5447a66` |
| [ ] A26 Valuation strategies, overrides, confidence inputs, report history/current selection | P4/Pre: flat Valuation panel | `I` -> **Sales & valuations** -> **Valuation** -> Strategy/Fee schedule/comps or commodity inputs; Confidence/Confidence reason, Fast sale/Suggested/Patient/Minimum, Manual override/reason -> **Create valuation report**; history -> **Make current** | reachable; strategy-specific inputs/override reason/current action are conditional; legacy controls are not AI prices | Original Phase 2/3 surface; container `5447a66` |
| [ ] A27 Profit breakdown and manual-price calculation | P4/Pre: flat Profit breakdown | `I` -> **Sales & valuations** -> **Profit breakdown** -> edit costs -> **Save costs**; current report -> Manual price -> **Calculate** | only conditionally rendered: projection/manual calculation needs current valuation; cost inputs always exist | Existing Phase 2 panel; container `5447a66` |
| [ ] A28 Sales, partial quantity, realised results and correction history | P4: absent; Pre: bottom Sales panel | `I` -> **Sales & valuations** -> **Sales** -> date/quantity/price/channel/fees/shipping/listing/cost override/notes -> **Record sale**; active row -> **Correct** | reachable; remaining-quantity limits and superseded-row correction guards retained; phone cards replace desktop table | `707d5c7`; container `5447a66` |

#### B. Full Phase 4 Draft And Nested Publish Path

For B01-B22, `L`/`P` above expands the full path from Inventory; the editor requires a draft. The controls are **not** supplied by copy packs or the quick preview. No UI eBay operation was exercised during this audit.

| Feature / Control / Step | Reachable Before (P4 / Pre) | Reachable At HEAD: Exact Path | Status | Commit That Changed It |
| --- | --- | --- | --- | --- |
| [ ] B01 Draft creation and selection | P4/Pre: flat **Listing** -> **Create draft** or draft row | `L` -> **Create draft** / click a draft title/status row; newly created draft selected | reachable; no first-class item-header listing entry; full panel is below copy/quick cards | `f2e692c` editor, `fdbab2a` publish; hidden-default wrapper `5447a66`, quick card inserted `b80eb4d` |
| [ ] B02 Save/resume and delete confirmation | P4/Pre: draft toolbar **Save** / **Delete** | `L` -> toolbar **Save**; reload -> reselect required draft row; **Delete** -> confirm | only conditionally rendered: selected draft; selection is component state, not a persisted canonical choice; no autosave | Control byte-identical since P4; `5447a66` changes outer access only |
| [ ] B03 Draft title/subtitle, 80-char counter, regeneration | P4/Pre: DraftEditor Title/Subtitle and Regenerate title | `L` -> Title/Subtitle; **Regenerate title** -> edited-text overwrite confirmation if applicable -> **Save** | only conditionally rendered: selected draft | P4 control unchanged; wrapper `5447a66` |
| [ ] B04 Description HTML/edit-preview, regeneration, boilerplate, SKU footer | P4/Pre: DraftEditor description and boilerplate controls | `L` -> **Description** -> **Preview/Edit**, **Regenerate description**, Boilerplate selection, SKU footer -> **Save** | only conditionally rendered: selected draft; edited copy overwrite requires confirmation | P4 control unchanged; wrapper `5447a66` |
| [ ] B05 Fixed-price / auction format | P4/Pre: Format select in editor | `L` -> **Format** -> Fixed price/Auction -> **Save** | only conditionally rendered: selected draft; eBay acceptance is not proven by selector presence | P4 control unchanged; wrapper `5447a66` |
| [ ] B06 Price/currency and price regeneration | P4/Pre: Price/Currency and **Regenerate price** | `L` -> **Price**, **Currency** -> **Save**; legacy **Regenerate price** remains separate | only conditionally rendered: selected draft; regeneration can source a valuation, so it is not proof of D-129 provenance | P4 control unchanged; Quick's generated-source rejection added `b80eb4d` |
| [ ] B07 Listing quantity | P4/Pre: editor Quantity input | `L` -> **Quantity** -> **Save** | only conditionally rendered: selected draft; not automatically bound to remaining stock | P4 control unchanged; remaining-stock integration still a later Sprint 25 phase |
| [ ] B08 Listing photo selection and ordering | P4/Pre: Photos checkboxes and Move up/down | `L` -> **Photos** -> select own photos -> **Move up/down** on selected rows -> **Save** | only conditionally rendered: draft plus photos; item gallery ordering is a separate control | P4 control unchanged; wrapper `5447a66` |
| [ ] B09 Item specifics, add/edit/remove/regenerate | P4/Pre: Item specifics rows | `L` -> **Item specifics** -> **Add row**, Specific name/value, Remove row, **Regenerate specifics** -> **Save** | only conditionally rendered: selected draft | P4 control unchanged; wrapper `5447a66` |
| [ ] B10 Postage/pickup wording | P4/Pre: Shipping note in draft | `L` -> **Shipping note** -> **Save**; actual postage policy ID is B15, not this note | only conditionally rendered: selected draft | P4 control unchanged; separate quick note added `b80eb4d` |
| [ ] B11 Readiness fails/warnings/passes and refresh | P4/Pre: DraftEditor Readiness | `L` -> **Readiness** -> **Refresh** -> Fails/Warnings/Passes | only conditionally rendered: selected draft/data; no per-check jump-to-field actions | P4 control unchanged; wrapper `5447a66` |
| [ ] B12 Clipboard and draft zip export | P4/Pre: Export area | `L` -> **Export** -> **Copy title/description/specifics/boilerplate** or **Download zip** | only conditionally rendered: selected draft; unready-export label retained; browser clipboard/download permission unverified | P4 control unchanged; wrapper `5447a66` |
| [ ] B13 eBay category mapping, search, leaf selection, manual fallback | P4: eBay Publish Category search, later persisted leaf-safe choices; Pre: same | `P` -> **Category search** -> **Search** -> leaf result; or Manual category ID/Tree ID/Category name -> draft toolbar **Save** | only conditionally rendered: selected draft/results; leaf selection persists channel_data immediately | `fdbab2a`, safety `7f5f7d9`, persistence `e7fd8d7`; wrapper `5447a66` |
| [ ] B14 eBay condition ID | P4/Pre: manual Condition ID next to category mapping | `P` -> **Condition ID** -> draft **Save** | only conditionally rendered: selected draft; distinct from Core details global Condition | P4 control unchanged; `f91f5b8` changes backend optional-condition handling, not this UI |
| [ ] B15 Payment/fulfilment/return policy IDs | P4/Pre: three plain ID inputs | `P` -> **Payment policy ID**, **Fulfillment policy ID**, **Return policy ID** -> draft **Save** | only conditionally rendered: selected draft; IDs have no account-name dropdown | P4 control unchanged; wrapper `5447a66` |
| [ ] B16 Merchant location use/create/manual key | P4/Pre: Merchant location block | `P` -> **Merchant location** -> **Use <existing key>** or Draft location key -> **Save**; create form -> **Create location** | only conditionally rendered: Use button needs returned local location; create requires key/name | P4 control unchanged; wrapper `5447a66` |
| [ ] B17 Required aspects/preflight, refresh and reasoned override | P4/Pre: Aspects pre-flight and required-field override | `P` -> **Aspects pre-flight** -> **Refresh**; missing required -> **Override and stage anyway** -> Override reason | only conditionally rendered: category enables check; override appears only when fields missing; hard preflight error blocks stage | `fdbab2a` plus Sprint 7 safety fixes; wrapper `5447a66` |
| [ ] B18 Stage / Re-stage offer | P4/Pre: eBay Publish action area | `P` -> **Stage offer** / **Re-stage offer** | only conditionally rendered: unpublished; disabled if disconnected/aspects error/unresolved required aspects/busy; persists draft first | P4 path retained; `befa502` published guard; Phase 0 backend fix `f91f5b8` |
| [ ] B19 Staged review/read-back | P4/Pre: **Review & publish** -> staged review | `P` -> **Review & publish** -> read-back of offer/SKU/title/category/condition/price/quantity/format/policies/location/photo count/aspect warnings | only conditionally rendered: staged status + offer ID + not published; initial button disabled otherwise | `fdbab2a`; published guard `befa502`; wrapper `5447a66` |
| [ ] B20 Withdraw unpublished offer | P4/Pre: Unpublished offer card | `P` -> **Unpublished offer <id>** -> **Withdraw** | only conditionally rendered: offer ID present, not published, no listing ID | `fdbab2a`; hide-after-publication guard `befa502`; wrapper `5447a66` |
| [ ] B21 Explicit live-publish confirmation | P4/Pre: staged review **Publish** -> type SKU -> final Publish | `P` -> **Review & publish** -> **Publish** -> **SKU confirmation** exact input -> final **Publish** | only conditionally rendered: review data exists; final button disabled until exact SKU and not busy; not clicked in audit | `fdbab2a`; `befa502` published guard; wrapper `5447a66` |
| [ ] B22 Published link / no second stage-publish-withdraw | P4: hardened by befa502; Pre: same | `P` -> **Published listing <id>** -> **Open listing**; old stage/review/withdraw/dialog hidden | only conditionally rendered: published status/listing ID; this guard does not make every DraftEditor input immutable | `befa502`, retained byte-for-byte |
| [ ] B23 Listing duration selector | P4/Pre: no duration UI | No duration input in ListingPanel, PublishPanel or QuickPublishPanel; Phase 0's GTC exists only in channel_data/backend payload | hidden: absent at every comparison point, not a reorganisation removal | No UI introduction found; backend transmission added `f91f5b8` |
| [ ] B24 Category-valid eBay condition choices | P4/Pre: typed ID only, not a condition-choice picker | No category-valid condition dropdown; Core global Condition and B14 raw ID are not equivalent | hidden: original gap, not deleted by accordion | No UI introduction found; metadata dropdown belongs to later Sprint 25 build |
| [ ] B25 Account policy-name dropdowns | P4/Pre: typed IDs and Settings policy counts only | No account payment/postage/return picker. Existing edit path is B15; Settings S03 shows counts, not choices | hidden: original gap, not deleted by accordion | No UI introduction found |
| [ ] B26 Expected listing fees/validation displayed before publish | P4/Pre: no fee-review UI | No getListingFees display in either frontend path; Phase 0 fee breakdown is in evidence only | hidden: not an orphaned component or restored UI | Phase 0 diagnostic records fees; no frontend introduction found |

#### C. QuickPublishPanel: Added Path, Not The Full Editor

| Feature / Control / Step | Reachable Before (P4 / Pre) | Reachable At HEAD: Exact Path | Status | Commit That Changed It |
| --- | --- | --- | --- | --- |
| [ ] Q01 Quick entry and preview sheet | P4/Pre: absent | `Q` -> **Post to eBay** -> **eBay live listing preview**; **Close** returns to card | reachable but below copy packs inside default-closed Listings / channels; no item-header entry | `b80eb4d` |
| [ ] Q02 Quick category mapping and blocker fix action | P4/Pre: full editor mapping only | `Q` -> **eBay category mapping** -> **eBay category** -> **Search** -> human-selected leaf; preview **Set eBay category** closes sheet and focuses `quick-ebay-category-search` | reachable; search result list conditional; save/select is explicit; not executed during audit | `b80eb4d` |
| [ ] Q03 Human price and source label | P4/Pre: manual draft price; no quick preview | `Q` -> preview -> **Evidence price** / **Source label**; full draft price edit exists through B06, but stale generated-price metadata can still block that route | reachable via explicit evidence input; generated-source drafts ignored. Item target_price can prefill, but ItemDetail has no direct asking/target-price field | `b80eb4d`; missing direct item target-price input predates it |
| [ ] Q04 Quick postage/pickup note and fix action | P4/Pre: draft Shipping note only | `Q` -> **Postage / pickup note** -> **Save postage / pickup**; preview blocker -> **Set postage / pickup** returns/focuses input | reachable; note is not the fulfilment business policy; fallback can use existing postage/packaging estimates | `b80eb4d` |
| [ ] Q05 Condition/photo blocker edit links | P4/Pre: full form/gallery, no quick blockers | Quick preview -> **Set condition** -> `#core-details`; **Add photos** -> `#photos` | reachable in code; actual browser hash expansion/scroll/focus needs phone verification; focus target is the section, not the Condition input | `b80eb4d` using anchors introduced `5447a66` |
| [ ] Q06 Disconnected quick-preview reconnect action | P4/Pre: Settings nav worked; no quick reconnect | Preview -> **Reconnect eBay** currently points at `/settings`; router exposes only `/settings/ebay` | hidden: broken destination for this action; Settings nav remains working | Introduced `b80eb4d`; not fixed by backend Phase 0 work |
| [ ] Q07 Same draft/selection/cache across quick and full paths | P4/Pre: one ListingPanel selection mechanism (duplicates still possible) | Quick uses first API result or private previewDraft; full Listing uses independently selected draft row. No quick draft selector/shared canonical resolver | hidden: no unified path. Query keys differ: `item-listing-drafts` versus `listing-drafts`; mutations do not consistently invalidate both | Fragmentation introduced `b80eb4d`; duplicate creation predates it |
| [ ] Q08 Quick confirmation versus full staged review | P4/Pre: full typed-SKU path B19-B21 only | Quick preview -> **Post live to eBay** patches draft, stages, then publishes with item.sku supplied programmatically; errors/live link in sheet | only conditionally rendered: preview open; Post disabled by its six blocker classes. No typed SKU, separate staged read-back, policy/aspect readiness or duration editor in quick sheet | `b80eb4d`; full B19-B21 path still exists and must survive unification |

#### D. CopyPackPanel And ChannelListing Surfaces

| Feature / Control / Step | Reachable Before (P4 / Pre) | Reachable At HEAD: Exact Path | Status | Commit That Changed It |
| --- | --- | --- | --- | --- |
| [ ] D01 Channel copy templates and human price source | P4: draft exports only; Pre: first flat lower-page CopyPackPanel | `I` -> **Listings / channels** -> **Ready-to-paste ad copy** -> Channel eBay/Facebook Marketplace/Gumtree/Plain copy; Human evidence price/Evidence label | reachable; template data returned by local API; no generated asking price added | `c900978`; wrapper `5447a66` |
| [ ] D02 Copy sections/whole ad and approved-display photo zip | P4: B12 draft export; Pre: separate copy-pack/own-photo zip | Same copy panel -> section **Copy**, **Copy whole ad**, **Photo zip** | reachable; copy sections require pack data; actual clipboard/download behaviour is browser-dependent and untested here | `c900978`; Photo zip fit change `b80eb4d` |
| [ ] D03 Manual channel add, including eBay | P4: absent; Pre: `/listings` board | `B` -> **Add a channel listing** -> Item/Channel/Listed at/URL/Note -> **Add listing** | reachable; local tracking only; no direct item-panel add form or board link | `c900978`; board unchanged by accordion |
| [ ] D04 Local eBay seed | P4: absent; Pre: board seed action | `B` -> **Seed local eBay rows** -> seeded/existing/ambiguous counts | reachable; local records only; no button used in audit | `c900978`; unchanged |
| [ ] D05 Active board, days listed and manual end | P4: published link in PublishPanel; Pre: channel groups | `B` -> **Items with active listings** -> channel group -> item link / days listed / **Mark ended** | only conditionally rendered: active rows; empty state otherwise; marking ended tracks truth, not an eBay end call | `c900978`; unchanged |
| [ ] D06 Sold-out take-down checklist and partial-quantity notice | P4: absent; Pre: item notice at top of flat lower panel stack plus board/dashboard | `I` -> **Listings / channels** -> checklist -> **Mark <channel> ended**; also `B` -> **Sold-out items still listed**, and **Home** -> **Open listings board** | only conditionally rendered: active rows + zero remaining; partial sale instead says listings still valid. Item alert is now hidden when section closed | `c900978` adds guard; `5447a66` hides item placement by default; board/dashboard retained |

#### E. EbaySettings, Orders And Global Navigation

| Feature / Control / Step | Reachable Before (P4 / Pre) | Reachable At HEAD: Exact Path | Status | Commit That Changed It |
| --- | --- | --- | --- | --- |
| [ ] S01 eBay connect/paste-back/complete/disconnect | P4/Pre: Settings -> Connect, Open, Redirected URL, Complete; Disconnect confirmation | `S` -> **Connect** -> **Open** -> paste Redirected URL -> **Complete**; **Disconnect** -> confirmation | reachable; consent link conditional on starting connect; disconnect disabled when not connected; no credential interaction in audit | `b6dbf3f`; controls retained through later Settings additions |
| [ ] S02 Account/token-expiry/scopes/environment/error status | P4/Pre: Settings sidebar Status | `S` -> **Status** card (below main stack on phone): Connected/Account/Access expires/Refresh expires/Scopes/refresh error | reachable; values/error/scopes conditional on status response; not the full future health/history panel | `b6dbf3f`; no removal by item reorganisation |
| [ ] S03 Policy readiness/refresh/snapshot age | P4/Pre: Settings Policy Readiness | `S` -> **Policy Readiness** -> counts/Opted in/Fetched -> **Refresh** | reachable; refresh disabled while disconnected; policy IDs/names are not selectable here | `b6dbf3f`; unchanged purpose |
| [ ] S04 Audit log/filter/read-only rows | P4/Pre: Settings Audit Log | `S` -> **Audit Log** -> **Action prefix** -> read Time/Action/Actor/Target in table or phone cards | reachable; rows conditional on API results; no row-expansion control | `b6dbf3f`; retained |
| [ ] S05 Settings order sync and local resolution | P4: absent; Pre: Settings Order Sync | `S` -> **Order Sync** -> **Sync eBay Orders**; pending row -> Item ID/Quick title/Cost basis -> **Link**, **Quick-create**, **Mark external**; duplicate -> Link/Dismiss | reachable; resolve controls need pending rows; sync disabled when disconnected; no action executed | `9aa676f`; retained beside newer dedicated Orders page |
| [ ] S06 Dedicated eBay Orders page and item picker | P4: absent; Pre: mobile eBay / desktop eBay Orders nav | `O` -> **Sync eBay orders**, **Search inventory for linking**, Unmatched Orders row actions; Duplicate Candidates -> Link/Dismiss; resolved-sale link -> Sales | reachable; rows require staged/duplicate data; this nav destination is orders, not a listing hub | `41310c1`, later auth wording `9a63251`; unchanged by accordion |
| [ ] S07 AI credential and Profit Engine sections sharing Settings | P4: absent; Pre: present beside eBay settings | `S` -> **AI Provider** (provider/model/usage/cap/remaining, save/replace/disconnect); **Profit Engine** (seller mode/rates/targets/ROI basis) | reachable; stored AI key never returned; preservation requirement, not an AI/provider change in this audit | `74a35a7`/`df54de0`; `5447a66` sub-cent display correction |
| [ ] S08 Global draft/live-listing eBay hub | P4/Pre: no combined hub | No `/ebay` hub route or draft/live-listing list in Settings. Mobile **eBay** opens Orders; **List** opens manual channel tracking; draft selection remains item-scoped through `L` | hidden: original/new-spec gap, not a component removed by accordion | Orders nav `41310c1`, channel board `c900978`; hub not yet implemented |

### Source Anchors And Findings To Carry Into Restoration

Code line references below are for audited HEAD and are not a live-browser claim:

- [ItemDetail](https://github.com/GoldDiggerTriangle/magpie/blob/abf682730df9b71c0ea2f0f9aefa899e6bacde29/frontend/src/features/inventory/ItemDetail.tsx#L63): defaults/hashes at 63-94, section save payloads at 249-275, full rendered composition at 317-503, body `hidden` at 553, persisted state at 560-575.
- [ListingPanel](https://github.com/GoldDiggerTriangle/magpie/blob/abf682730df9b71c0ea2f0f9aefa899e6bacde29/frontend/src/components/ListingPanel.tsx#L41): draft selection/create at 41-123, editor at 150-314, nested PublishPanel at 304, specifics/photo/readiness/export controls at 333-483.
- [PublishPanel](https://github.com/GoldDiggerTriangle/magpie/blob/abf682730df9b71c0ea2f0f9aefa899e6bacde29/frontend/src/components/PublishPanel.tsx#L46): queries/state and category persistence at 46-165, guards/actions at 167-318, typed condition/policy controls at 399-435, merchant location at 459-500, staged review at 590-623, exact-SKU dialog at 636-680.
- [QuickPublishPanel](https://github.com/GoldDiggerTriangle/magpie/blob/abf682730df9b71c0ea2f0f9aefa899e6bacde29/frontend/src/components/QuickPublishPanel.tsx#L28): separate query/private draft at 28-48; patch/stage/publish at 99-138; fix actions at 179-202; category/postage controls at 222-253; bad `/settings` link at 304; six blocker classes at 379-436; anchor/focus helpers at 606-615.
- [CopyPackPanel](https://github.com/GoldDiggerTriangle/magpie/blob/abf682730df9b71c0ea2f0f9aefa899e6bacde29/frontend/src/components/CopyPackPanel.tsx#L16), [ChannelListingsPage](https://github.com/GoldDiggerTriangle/magpie/blob/abf682730df9b71c0ea2f0f9aefa899e6bacde29/frontend/src/features/listings/ChannelListingsPage.tsx#L21), and [TakeDownChecklist](https://github.com/GoldDiggerTriangle/magpie/blob/abf682730df9b71c0ea2f0f9aefa899e6bacde29/frontend/src/components/TakeDownChecklist.tsx#L7) establish D01-D06.
- [EbaySettings](https://github.com/GoldDiggerTriangle/magpie/blob/abf682730df9b71c0ea2f0f9aefa899e6bacde29/frontend/src/features/settings/EbaySettings.tsx#L176), [EbayOrders](https://github.com/GoldDiggerTriangle/magpie/blob/abf682730df9b71c0ea2f0f9aefa899e6bacde29/frontend/src/features/ebay/EbayOrders.tsx#L116), [AppShell](https://github.com/GoldDiggerTriangle/magpie/blob/abf682730df9b71c0ea2f0f9aefa899e6bacde29/frontend/src/components/AppShell.tsx#L4), and [routes](https://github.com/GoldDiggerTriangle/magpie/blob/abf682730df9b71c0ea2f0f9aefa899e6bacde29/frontend/src/routes.tsx#L17) establish the global paths and the missing `/settings` destination.
- [DescriptorEvidencePanel](https://github.com/GoldDiggerTriangle/magpie/blob/abf682730df9b71c0ea2f0f9aefa899e6bacde29/frontend/src/components/DescriptorEvidencePanel.tsx#L22) requires onUsePrice for its button (187-198); ItemDetail supplies none. [Nested draft list/create](https://github.com/GoldDiggerTriangle/magpie/blob/abf682730df9b71c0ea2f0f9aefa899e6bacde29/backend/apps/listing/views.py#L157) orders by newest created and creates another draft rather than resolving a canonical draft (157-182).

Required follow-through, **not implemented in this audit**:

- [ ] Restore first-class access within the existing accordion layout (D-137); do not implement tabs. Bring the editor entry forward without dropping copy packs, manual board tracking, source evidence, local photos or any B01-B22 control.
- [ ] Unify draft resolution and query invalidation before folding QuickPublishPanel/nested PublishPanel into the single editor/preview. The current selected full draft and the first quick result can differ; later migration/keeper rules must preserve the Phase 0 staged offer and published history.
- [ ] Supply the missing human-selected condition/policy/location/duration metadata controls; keep IDs/names/provenance visible. Existing plain ID inputs must not be mistaken for the requested dropdowns. An optional-condition gold category also needs the quick readiness model aligned with exact category metadata, not a fabricated global grade.
- [ ] Preserve the full staged read-back, withdraw and typed-SKU full path while converging the two-tap shortcut onto the same preview. Current quick blockers do not inspect all full-path policy/aspect requirements; a saved postage note is not proof of a valid fulfilment policy.
- [ ] Preserve D-129 throughout the unified editor. The legacy Regenerate price path and valuation-derived draft prices are not automatically a human-picked evidence price. A subsequent manual draft price edit does not clear `generated_meta.price_source` in ListingDraftSerializer.update (100-108), while Quick's chooser rejects any object in that field: the quick blocker's suggestion to manually edit a draft price is therefore incomplete for a previously generated price. Provide explicit human price provenance instead of bypassing the guard. Quick Publish also substitutes copy-pack description during its final patch (110-114); an edited full draft description must not be silently lost when the paths converge.
- [ ] Repair Q06's broken reconnect destination and verify Q02/Q04/Q05 fix links through the actual item shell, not only an isolated component.
- [ ] Keep the sold-out take-down notice impossible to miss; a default-closed Listings section now hides the item's alert even though the board/dashboard alternatives still exist.
- [ ] Add the spec's integrated reachability gate during the build phases: representative unlisted/drafted/published/sold/partial items, actual panels, every section opened, visibility and usable controls asserted. Existing ItemDetail tests mock ListingPanel, CopyPackPanel, SalesPanel and many others to `null` (ItemDetail.test.tsx 52-66), so their passing accordion tests do **not** prove the old publish/editor controls are reachable. Do not weaken the existing component/backend tests.

### What Code Alone Cannot Settle: Regan's Phone Checks

These are **outstanding observational follow-ups**, not checks performed in this task. A browser/PWA can serve a stale bundle, safe-area geometry depends on the device, and clipboard/downloads depend on the actual browser/security context. This audit did not navigate the live app; even opening an item can mount eBay preflight queries. No eBay/AI/refresh/stage/publish/withdraw or business-data-mutating button should be pressed merely to complete this audit.

1. On the real iPhone/Safari/PWA, confirm the served version after the intended restart/hard refresh. Check Photos/Core open by default for a fresh item state, expansion persistence, sticky headers clear of the clock, and the desktop index's intentional absence on phone.
2. Open Listings / channels, scroll past copy packs/quick card, and confirm **Listing** -> draft row -> full editor -> **eBay Publish** can actually be seen/read at roughly 390px. If it looks missing despite the code path, record screenshot, selected draft and scroll position; do not infer deletion from the folded view.
3. With the Phase 0 staged GOLD-00002 draft selected, visually confirm the Unpublished offer/Review & publish/Withdraw controls without invoking them. With a published draft, confirm the existing listing link and absence of stage/withdraw/publish; with partial/sold-out stock, check the different notice and sale-quantity states without recording a test sale.
4. Observe quick-preview category/postage fix actions, then the condition/photos anchor actions, to establish real expansion, scrolling, keyboard focus and return-to-preview behaviour. These paths have code and some isolated tests, but the final phone result is not proven here. Do not use Search or Post live as an audit test. The bad `/settings` target is already established from source and need not be visited to prove its defect.
5. In a later authorised manual session, verify Copy/Copy whole ad/Photo zip on the real LAN/PWA browser and that the bottom navigation does not cover controls. No download/clipboard interaction or UI screenshot was captured in this task.

No new claim is made about completion of Sprint 23R2/Sprint 24 live evidence. Their outstanding evidence remains separate; Phase 1 does not supersede it.

### Audit Boundaries And Stop Point

Only this appended evidence section and one handoff session-log entry are changed. No source/config/settings/.env/dependency/schema/service/database change, live UI action, eBay call, AI call, staging, publishing, withdraw or Phase 2 restoration occurred. Historical source was read with `git show`/blob comparisons; no checkout/reset was used. Secret checks cover the documentation before commit/push.

**Phase 1 stop and report:** the restoration inventory is delivered. Await Regan's direction before any build phase, canonical-draft migration, UI restoration or live publish. Phase 0 remains **staging passed; live publishing remains unproven**.

## 2026-11-13: Phase 2 Canonical Draft Model - Migration A Dry Run Only

**STOP FOR OWNER APPROVAL.** The canonical model and Migration A command are implemented and dual-lane tested. The live run was dry-run only: no draft was archived, no audit row was appended, and no migration was applied to the live database. Regan must approve the report below before real Migration A. Migration B is intentionally not written in this phase.

### Step 0 Preconditions

| Check | Result |
| --- | --- |
| Checkout / starting HEAD | `D:\Magpie\app`, `main`, `59e1e0da95972ac66ce4c1f957f798074234568c` |
| Controlling documents | `docs/MASTER_HANDOFF.md` v4.65; `docs/specs/SPRINT_25_SPEC.md` and kickoff v3.4; Phase 1 restoration checklist above read first |
| Initial working tree | Only pre-existing untracked `CLAUDE_STRUCTURAL_AUDIT.md`; left untouched |
| Latest applicable main Validation at preflight | `43379342303`, successful on both lanes, commit `d32f00fae3ba526051e7583be0a57d0479ce407f` (ancestor of starting HEAD); SQLite job `131733201076`, PostgreSQL job `131733201446` |
| Live venv requirements | All 13 direct requirement constraints satisfied; DRF exactly 3.18.3; Python 3.13.4 and Django 5.2.15; no install or dependency-file change required |
| Restart freshness | Fix `08b6ae2325aeba66934dbe49a30903211101a78f` committed at 2026-11-13 05:56:18 UTC; actual port-8000 Python listener PID 12604 started at 06:17:14.181225 UTC, after that commit; NSSM PID 23328 |
| End-of-task service observation | Same service/listener PIDs and start time, Running; live `/api/health/` HTTP 200. No restart performed by this task |

### Actual Status Classification (Before Any Cleanup)

The inspected model had six statuses, not merely the five named in the early Sprint 7 spec. There is **no separate `publish_state` field**. Existing remote state/proof lives in `channel_data` (for example offer/listing IDs) and the related `ChannelListing`; those records are not rewritten by cleanup.

| Status | Existing / added | Classification | Treatment |
| --- | --- | --- | --- |
| `draft` | Existing | Active | Eligible for keeper selection |
| `ready` | Existing | Active | Eligible; an offer ID still takes precedence over completeness |
| `exported` | Existing | Active | Export is not evidence of a terminal marketplace outcome |
| `staged` | Existing | Active | An unpublished offer holder wins if it is the only one |
| `publish_failed` | Existing | Active | Failure does not terminate the draft or discard its offer |
| `published` | Existing | Terminal | Immutable history; never a cleanup candidate |
| `archived` | Added | Terminal | Retained and viewable read-only, never deleted by cleanup |
| `publishing` | Added | Active | Unresolved until the publish outcome is reconciled; not auto-archived |
| `publish_unknown` | Added | Active | Unresolved until reconciled; not auto-archived |
| Any unclassified/future status | Safety rule | Active | Cannot bypass the active predicate |

`draft_status.py` centralises this mapping and the active predicate (exclude only published/archived). Tests enumerate every actual choice plus an unknown status. There is no existing ended-listing status to classify. An active-status row with a local published listing ID or linked ChannelListing is protected and reported unresolved rather than relabelled or archived.

### Implementation And Safety Boundaries

- `canonical.py` plans per item/channel, entirely from owned local records. Exactly one offer holder wins; multiple offer holders leave the group unresolved. Otherwise score, newest `updated_at`, then highest UUID primary key decide the keeper. No offered non-keeper is archived automatically.
- The score has ten explicit components: title, category, condition, positive price, photos, payment, postage, returns, merchant location and all required aspects. Required aspects are rechecked against current specifics using the cached category-matching metadata. Unknown metadata scores incomplete. The existing cached `required=false` condition policy makes a category with no condition requirement complete without inventing a condition.
- Item-scoped create/open reuses the canonical active draft without changing it (HTTP 200); an actual new draft is HTTP 201. The existing item-list endpoint orders the canonical eBay draft first. The generic collection POST cannot bypass canonical creation. Unresolved groups refuse creation. UI unification remains Phase 3+ work; no frontend code changed here.
- Published and archived draft writes/deletes are rejected through model saves, bulk updates, queryset deletes, item-delete cascades and API mutation actions. Detail/export reads remain available without changing export status/timestamps. Relisting seeds a separate draft from published content and allowlisted listing settings, without copying offer/listing IDs, old EPS URLs, errors or response payloads.
- The full suite exposed Sprint 11 attaching last-order sync metadata to a published draft. That path now leaves published/archived history untouched; the SaleRecord retains the order/line identifiers. Regression coverage checks full historical row equality, active-draft metadata updates, quantity accounting and sync idempotence. No real order sync was run.
- Management command `canonicalize_listing_drafts` defaults to dry run; `--dry-run` is explicit. Real `--apply` additionally requires the exact `--approved-fingerprint` from the reviewed report and rechecks it inside a transaction. Changes to the plan abort; an audit failure rolls back archival. Every real archived row would append a new `listing.draft.archived` audit row with its prior status, offer ID, score/components and keeper ID; existing audit history is not modified. Tests exercise apply only on isolated test databases.
- Additive migration `listing.0004_listingdraft_canonical_statuses` only extends status choices. SQLite `sqlmigrate` reports a no-op; no data cleanup is hidden in it. **It has not been applied to live.** Django check passes and `makemigrations --check --dry-run --noinput` reports no changes.
- **Migration B remains deferred:** no partial unique constraint or its pre-check migration is installed or claimed here. Its database-level rejection/constraint-coverage tests belong to the later supervised step, after approved Migration A and resolution. Parent locking is not presented as a substitute for SQLite uniqueness protection. Current tests prove the shared active predicate and canonical create/reuse behaviour on both database lanes.

### Encrypted Backup Before Live Dry Run

The unchanged existing `backup --no-upload` command created:

`D:\Magpie\backups\phase2-pre-dry-run-20261113\magpie-backup-20261113-070636.tar.gz.enc`

27,959,020 bytes; decryption with B and tar validation passed: **92 members, 64 media files**, including the SQLite snapshot. The process environment was compared to the Windows user-level B without printing values; D-139 is unchanged. No cloud upload, rclone or eBay call was made. Verification plaintext was immediately deleted. Task test/verification scratch directories were removed after path checks; the encrypted archive is retained outside the repository.

### Live Migration A Dry-Run Report

The command ran against the actual `backend/db.sqlite3` with SQLite **`PRAGMA query_only=ON`** and an outbound socket-connect guard. No `migrate`, seed, archive/apply, staging, publishing, withdraw or remote lookup was invoked. The final report fingerprint is:

`f2a614c9862ff30ef8cd7866582b3f32770699426416657757b56178ecbf8f99`

| Item | Channel | Draft | Current status | Offer ID | Score / 10 | Proposed action |
| --- | --- | --- | --- | --- | --- | --- |
| GOLD-00002 | ebay_au | `af013dd9-0611-431c-be4a-223c44ec4e06` | staged | `356038014011` | 10 | **KEEP**: sole staged-offer holder |
| GOLD-00002 | ebay_au | `0fe7df74-b982-4173-8aa0-d449fa228128` | draft | None | 2 | Archive after approval |
| GOLD-00002 | ebay_au | `151cbc31-0146-4300-a061-40a4c6f36d1a` | draft | None | 2 | Archive after approval |
| GOLD-00002 | ebay_au | `2ddac3c1-7462-48ea-8432-cab907e20693` | draft | None | 2 | Archive after approval |
| GOLD-00002 | ebay_au | `6a66b92a-fac7-4414-9c5a-e51614c36e27` | draft | None | 2 | Archive after approval |
| GSP-00001 | ebay_au | `d1e714f6-58b3-4640-b705-b185dbb083fb` | draft | None | 3 | KEEP: only active draft |
| PH-00001 | ebay_au | `a089618e-7dea-4b69-96b6-cab9257cfb5a` | draft | None | 2 | KEEP: only active draft |
| STM-00003 | ebay_au | `781043d7-fca6-4944-a1ee-9eb4493be27b` | published | Not inspected for selection | Excluded | Preserve published history unchanged |

**Planned archival: 4. Unresolved groups: 0.** GOLD-00002 would have one active and four archived drafts, exactly as expected. The four informally called empty drafts do have title/photo references (2/10); they have no price, category or policy configuration. No claim that they are literally blank is needed. GSP-00001 is a separate record and is not treated as the selected gold item. No groups on other channels exist in this live snapshot.

### Before/After: Dry Run Wrote Nothing

Full ordered row values were hashed in memory before and after, not printed as payloads. Every count, status distribution and digest matched:

| Table / state | Before | After | Full-row SHA-256 before = after |
| --- | --- | --- | --- |
| `listing_listingdraft` | 8 | 8 | `fbf48dffaca915e9219b80da606aa8bb314477b0cad0084ccc1892191e77b5dd` |
| `audit_auditlog` | 151 | 151 | `1d984815623d8fa93a27d70432450e9f83c41885136dfad4d71cf043eaefe99c` |
| `listing_channellisting` | 1 | 1 | `f1e3038cbd4a9034de5c6d2f2d2afb6192e4db3fc98b029da8c13f431ac45a1f` |
| `django_migrations` | 51 | 51 | `ffe5d7a6748816c58e8d350154c7a12221fa70a2fa32b798b5583752362d3983` |
| Draft statuses | draft 6; staged 1; published 1 | draft 6; staged 1; published 1 | No archived/new-state row was written |

### Tests, Validation And Commits

Implementation commit: **`8d223247e3929fe3997015377da95cba6b95c871`**, pushed to main.

| Validation | Result |
| --- | --- |
| Focused canonical / Sprint 5 / Sprint 7 suite | 64 passed after correcting the test-only placeholder photo UUID and matching the existing condition-policy key |
| Full local backend, updated live venv, isolated SQLite, socket connects blocked | **252 passed, 1 skipped**, 14 warnings, 140.12 seconds |
| GitHub [Validation 43384013974](https://github.com/GoldDiggerTriangle/magpie/actions/runs/43384013974) | **Both lanes green**, exact implementation commit above |
| SQLite job `131748128680` | **252 passed, 1 skipped** backend; migrations/check/seed and marketplace-confinement guard passed; encrypted backup/restore passed |
| PostgreSQL job `131748128217` | **240 passed, 13 skipped**; migrations/check/seed/fake-adapter checks passed; same canonical/archival/history tests run here |
| Frontend in SQLite CI lane | **123 passed across 33 files**; typecheck, build and collectstatic passed |
| Production checks in CI | Deploy check and Waitress/WhiteNoise smoke passed |
| Repository checks | `git diff --check` passed; secret scan found no known secret values or credential-shaped values in changed files |

Coverage includes every status/unknown-active fallback, ten-component scoring and category-specific optional conditions, sole/multiple offer holders, deterministic ties, per-item/channel separation, uncertain outcomes, published-proof protection, unchanged dry runs, exact-plan approval, per-archive audit rows, rollback/idempotence, published/archived immutability and export, canonical create/reuse/list priority, safe relisting, and adapter-forbidden local planning/apply tests. Existing suites remain enabled; platform-specific backup tests retain their existing skips.

No `.env`, requirement, settings, credential, specification, frontend or structural-audit file was changed. No eBay or AI call occurred, and no live migration or service restart occurred. This task changes backend implementation/tests plus this appended evidence and one handoff session line; Phase 1's restoration checklist remains intact and unchecked work is not silently declared complete.

**Phase 2 stop and report:** approve the four-row GOLD-00002 archival plan above before real Migration A. Do not proceed to Migration B or UI restoration on the strength of this dry run. Phase 0 remains **staging passed; live publishing remains unproven**. Sprint 25 is not closed.

## 2026-11-14: Approved Migration A Applied; Migration B Tested, Not Installed Live

**STOP BEFORE LIVE MIGRATION B.** Regan approved the Migration A report at `64712feb` and authorised exactly the four GOLD-00002 archives. Migration A is now applied and verified. Migration B is committed/tested and its live read-only pre-check is clean, but its index and migration record are deliberately absent from live. No service restart or UI work was performed; B installation remains a separate owner-approved backup/Administrator-restart step. Phase 0 remains staging-only, not live-publish proof.

### Approval And Drift Protection

- Starting HEAD was `64712feb5e7406e5685de5777f3ff475a908e910`, with only the existing untracked `CLAUDE_STRUCTURAL_AUDIT.md`. Main Validation `43384549149` was green on both lanes.
- Before any live change, the full plan fingerprint matched the approved report exactly: `f2a614c9862ff30ef8cd7866582b3f32770699426416657757b56178ecbf8f99`. Full ordered-row hashes/counts for drafts, audit rows, ChannelListing and migration records also matched the prior evidence snapshot. The only pending migration was additive `listing.0004_listingdraft_canonical_statuses`.
- The same operation was rehearsed on a scratch restore of the fresh pre-operation backup. Live execution then used a single SQLite **BEGIN IMMEDIATE** transaction: recheck the exact fingerprint and four UUIDs, verify the pending migration list, apply 0004, invoke the existing approved-fingerprint Migration A command, and verify all resulting rows before commit. A plan mismatch or failed verification aborts the entire transaction, including the migration record; the migration was not recorded separately before the recheck.
- All other table values, all existing audit rows and all non-target draft values were compared inside the transaction. Each archived draft changed only `status` and `updated_at`; its original content remains retained. Published STM-00003, its ChannelListing, inventory and sale/audit history were not changed.

### Fresh Encrypted Backups And Restore Spot-Check

Backup filenames use UTC; this session is dated **14 November Australia/Sydney**.

| Stage | Encrypted archive | Bytes | Verification |
| --- | --- | --- | --- |
| Before A | `D:\Magpie\backups\phase2-migration-a-20261114\pre\magpie-backup-20261113-223737.tar.gz.enc` | 27,959,029 | B decryption; 92 archive members, 64 media files; restored to scratch for the successful transaction rehearsal |
| After A | `D:\Magpie\backups\phase2-migration-a-20261114\post\magpie-backup-20261113-224016.tar.gz.enc` | 27,958,972 | B decryption; 92 members; full restore spot-check passed |

Both use the unchanged existing `backup --no-upload` / `restore` paths. The child environment matched Windows user passphrase B without displaying its value; B and `.env` were not changed. The post-A restore contains **46 tables, 728 rows, 64 media files**. Every restored table's row-content digest and every media-file digest matched live; SQLite integrity check returned `ok`, with zero foreign-key violations. It includes all eight drafts, the four new archival audit records and the new 0004 migration record. No restore targeted live. Decrypted tar files were deleted immediately; rehearsal/restore/test scratch folders were path-checked and removed. Both encrypted archives remain outside the repository; no cloud upload/rclone was run.

### Actual Migration A Result

`listing.0004_listingdraft_canonical_statuses` was recorded at **2026-11-13 22:39:18.584929 UTC** (14 November locally). The four appended audit rows were created between 22:39:18.679281 and 22:39:18.684309 UTC, inside the same transaction.

| Check | Before | After |
| --- | --- | --- |
| All ListingDraft rows | 8 | **8** |
| GOLD-00002 active drafts | 5 | **1** |
| GOLD-00002 archived drafts | 0 | **4** |
| GOLD-00002 keeper | `af013dd9-0611-431c-be4a-223c44ec4e06`, staged | Same UUID/status; offer `356038014011` unchanged |
| Global statuses | draft 6; staged 1; published 1 | draft 2; archived 4; staged 1; published 1 |
| Audit rows | 151 | **155**, exactly four new rows; all 151 original rows unchanged |
| ChannelListing rows | 1 | **1**, full row unchanged |
| Migration records | 51 | **52**, only 0004 added |
| STM-00003 published draft/history | Preserved | **Unchanged**, including its related listing and historical rows |
| Unresolved groups | 0 | **0** |

Exactly these rows were archived, with one new `listing.draft.archived` audit record each (actor `migration_a`, keeper linkage retained):

| Draft UUID | Pre-archive status | Offer ID recorded | Score recorded | Current status |
| --- | --- | --- | --- | --- |
| `0fe7df74-b982-4173-8aa0-d449fa228128` | draft | None | 2/10 | archived |
| `151cbc31-0146-4300-a061-40a4c6f36d1a` | draft | None | 2/10 | archived |
| `2ddac3c1-7462-48ea-8432-cab907e20693` | draft | None | 2/10 | archived |
| `6a66b92a-fac7-4414-9c5a-e51614c36e27` | draft | None | 2/10 | archived |

GSP-00001 and PH-00001 retain their original single active drafts. GOLD-00002's keeper was neither edited nor restaged; the offer ID above is unchanged local evidence, not a new remote read-back.

**Archived read-only proof:** authenticated GETs to all four `/api/listing-drafts/<uuid>/` routes on the actual port-8000 service returned HTTP 200 and status `archived`. Each model reports read-only. Direct current API-handler PATCH checks, authenticated in-process against a `PRAGMA query_only=ON` connection, returned HTTP 400 with the read-only message; no live HTTP write attempt was made. Content was not rewritten just to test a guard. No browser/UI edit path was added or claimed here.

**Supervised resolution: COMPLETE, nothing to resolve.** The post-A planner reports zero unresolved groups and zero further archives. No offer needed withdrawal/deletion and no eBay operation was made.

### Migration B Implementation And Live Pre-Check

Implementation commit: **`1564d32127d2553585b2f291792b371cce78e836`**.

- New `listing.0005_listingdraft_one_active` runs a historical-model pre-check first. Duplicate active groups abort with SKU, item UUID, channel and count; it never silently repairs/archives data or calls eBay. The shared local query accepts the frozen migration predicate.
- Only after a clean pre-check does it add partial `UniqueConstraint` **`listing_one_active_draft`** on `(item, channel)`, excluding only `archived` and `published`. Every other value, including unknown/future statuses, stays active. The model predicate and frozen migration predicate are asserted equal in tests.
- SQLite SQL generation is `CREATE UNIQUE INDEX ... WHERE NOT (status IN ('archived', 'published'))`. The index is genuinely installed in isolated test databases on both SQLite and PostgreSQL. No new table or business-data rewrite is involved.
- New management command **`check_canonical_drafts`** is read-only and reports violating groups plus whether the constraint is installed; it exits nonzero and names the items on violation. It does not apply migrations.
- The live command ran with SQLite query-only enabled and outbound connections blocked. Result: **violation_count 0, violations [], constraint_installed false**. Draft/audit/listing/migration counts and full-row digests were identical before and after. The only pending migration is **0005**; live remains at **52 migration records**, with no B index.

Post-A / live-pre-check digests (unchanged by the pre-check):

| Table | Rows | SHA-256 |
| --- | --- | --- |
| `listing_listingdraft` | 8 | `c0dd12a51acb4e19ed232bde5cd7a143101b10c66892cb2861d1162bd78443e0` |
| `audit_auditlog` | 155 | `6729b9be30095f45355981d6a22544c28287427e45f0531f216701d18e279d95` |
| `listing_channellisting` | 1 | `f1e3038cbd4a9034de5c6d2f2d2afb6192e4db3fc98b029da8c13f431ac45a1f` |
| `django_migrations` | 52 | `1637b2dbe01dee7bf430bf9dc092f48ab561cebb993338f08a85b7bd707fa157` |

### Tests And Validation

| Check | Result |
| --- | --- |
| Focused canonical + constraint suite | **34 passed** |
| Full local backend, live venv / isolated DB / network blocked | **264 passed, 1 skipped**, 14 warnings; 157.37 seconds |
| Django check | No issues |
| `makemigrations --check --dry-run --noinput` | No changes detected |
| [Validation 43522671807](https://github.com/GoldDiggerTriangle/magpie/actions/runs/43522671807), commit `1564d321` | **Both lanes green** |
| SQLite job `132220582796` | **264 passed, 1 skipped**; fresh migrations/seed/checks/marketplace guard and backup/restore passed |
| PostgreSQL job `132220582401` | **252 passed, 13 skipped**; migrations/seed/checks and the actual uniqueness/pre-check tests passed |
| Frontend CI | **123 passed across 33 files**; typecheck/build/collectstatic passed |
| Production CI | Deploy check and Waitress/WhiteNoise smoke passed |

Required regression proof includes: a seeded `ready` + unknown-status duplicate abort names the item on both database lanes; a real file-backed SQLite MigrationExecutor failure leaves both draft rows unchanged, adds no B migration record and installs no index; a successful file-backed install rejects a second active draft for every known active status and an unknown value; both directions of active/unknown collisions are rejected on the default SQLite/PostgreSQL test databases; repeated terminal history and different channels remain permitted; pre-check queries are read-only.

Migration A's legacy-duplicate tests explicitly simulate the before-B index state inside rolled-back test transactions, restoring the index automatically. The old staging-conflict guard likewise retains its legacy-collision assertion in a rolled-back savepoint. The old readiness test now repairs its existing canonical draft instead of creating a second active one. No assertions were removed, no new skips were added, and the actual B tests keep the constraint installed.

### Documentation, Runtime And Stop Point

- `docs/specs/README.md`: corrected only the stale "actual v3.3 sources" wording to **v3.4**.
- Applied `C:\Users\Regan\Downloads\MASTER_HANDOFF_UPDATE_2026-11-13_PHASE2.md` verbatim: all **13 Find strings matched exactly once**, and the result's normalised-content hash matched the exact replacement output before adding Codex's required session line. Handoff is **v4.66**; no additional header/decision-log edits were improvised. One dated 2026-11-14 Codex line records this task's actual outcome.
- Service was already Running: NSSM PID 26960, listener PID 4764, started 2026-11-13 11:07:28.208146 UTC. The same PIDs/start time remain; live `/api/health/` returned **200**. No stop/restart or NSSM change occurred in this task.
- `.env`, Windows passphrase B, requirements/settings, credentials, controlling spec/kickoff, frontend and the existing untracked structural audit are unchanged. Changed files were checked for known secret values and credential patterns before commit/push; no values were printed or committed.

**Stop and report before installing Migration B live.** A fresh backup and Administrator restart are for that next supervised step. No Phase 3/UI work, real eBay/AI call, staging, publishing or withdrawal was undertaken. Sprint 25 remains open; the approved Migration A operation and zero-unresolved supervision step are complete.

## 2026-11-14: Migration B Installed Live - Awaiting Administrator Restart

**PENDING OWNER RESTART.** Regan accepted Migration A at `6202c4e0` and explicitly authorised installation of B. Steps 1-5 are complete. Codex has stopped live operations and asked Regan to restart the service from Administrator PowerShell. Post-restart health, serving-version and canonical-draft checks are **not yet claimed**; Phase 3 requires a separate instruction.

### Preconditions, Backup And Read-Only Pre-Check

- Checkout `D:\Magpie\app`, main HEAD `6202c4e0b276b9d95c57d283c80ca22898ecc1cc`, containing implementation `1564d32127d2553585b2f291792b371cce78e836`. Existing Validation `43523195223` is green on both lanes. Handoff v4.66 and spec v3.4 were read first; no application-code change was made in this task.
- The accepted post-A counts and full-row hashes matched: 8 drafts, 155 audit rows, 1 ChannelListing and 52 migration records. GOLD-00002 retained its exact staged keeper and four archives. The only pending migration was `listing.0005_listingdraft_one_active`.
- The unchanged `backup --no-upload` path created a fresh encrypted archive and B decryption/tar validation passed. It was also restored to scratch to rehearse B against the real owned-data snapshot, without adding test rows.
- After the backup, `check_canonical_drafts` was rerun on the live SQLite database with `PRAGMA query_only=ON` and outbound connections blocked: **violation_count 0, violations [], constraint_installed false**. Draft/audit/listing/migration counts and full-row hashes were unchanged by the check.

### Live Installation And Schema-Only Verification

Migration B was applied at **2026-11-13 23:33:08.027819 UTC**, which is 14 November in Australia/Sydney. A single SQLite BEGIN IMMEDIATE transaction rechecked zero violations and the exact pending migration, applied only 0005, and verified schema and every table's original row values before commit. No original business/audit row changed; only the expected migration record was added.

Live schema inspection confirmed:

```sql
CREATE UNIQUE INDEX "listing_one_active_draft"
ON "listing_listingdraft" ("item_id", "channel")
WHERE NOT ("status" IN ('archived', 'published'))
```

`PRAGMA index_list` reports **unique=1, partial=1**; `PRAGMA index_info` confirms columns **item_id, channel**. The sqlite_master definition matches the approved migration exactly. Verification used schema inspection, not a probe insert: **zero test rows were inserted into live data**. Integrity check returned `ok`; foreign-key checking remained enabled after the transaction.

| Check | Before B | After B |
| --- | --- | --- |
| ListingDraft rows | 8 | **8**, full values unchanged |
| GOLD-00002 active / archived | 1 / 4 | **1 / 4** |
| Canonical keeper | `af013dd9-0611-431c-be4a-223c44ec4e06` | Same UUID; staged offer `356038014011` unchanged |
| Audit rows | 155 | **155**, all values unchanged |
| ChannelListing rows | 1 | **1**, full row unchanged |
| Migration records | 52 | **53**, only 0005 added; all prior records unchanged |
| STM-00003 published history | Preserved | **Unchanged** |
| Partial unique index | Absent | **Present** |

The post-install query-only command confirms **zero violations, constraint_installed true**. No other pending migration was applied or new draft created.

### Encrypted Backups And Restore

Filenames use UTC; both backups belong to this 14-November local session. B was read/compared without displaying it and was not changed.

| Stage | Encrypted archive | Bytes | Verification |
| --- | --- | --- | --- |
| Before B | `D:\Magpie\backups\phase2-migration-b-20261114\pre\magpie-backup-20261113-233211.tar.gz.enc` | 27,958,962 | B decryption; 92 archive members / 64 media files; successful scratch rehearsal |
| After B | `D:\Magpie\backups\phase2-migration-b-20261114\post\magpie-backup-20261113-233339.tar.gz.enc` | 27,959,104 | B decryption; 92 members; full restore spot-check passed |

The post-install restore contains **46 tables, 729 rows and 64 media files**; every table's row-content digest and every media-file digest matched live. It retains the actual partial unique index and the 0005 migration record, all eight drafts and unchanged audit/listing rows. SQLite integrity is `ok`, with zero foreign-key violations. No restore targeted live. Plaintext tar files were deleted immediately, and the entire task scratch directory was path-checked and removed after verification. Only encrypted archives are retained; no cloud upload/rclone was used.

### Restart Handoff And Remaining Checks

Before the requested restart, NSSM was Running with service PID **26960**, actual port-8000 listener PID **4764**, start time **2026-11-13 11:07:28.208146 UTC**, AppDirectory **D:\Magpie\app\backend**. These are baseline observations, not proof that the requested restart has happened.

Regan was asked to run:

```powershell
Restart-Service -Name Magpie -ErrorAction Stop
```

After his confirmation, verify a new service/listener start, `/api/health/` HTTP 200, and that the process uses this checkout containing `1564d321` or later. Check GOLD-00002's existing canonical draft via the read-only local draft routes, with no saves or eBay preflight/read-back calls; it must resolve to `af013dd9`. Do not navigate a page that automatically performs remote eBay lookups merely to prove the route. These post-restart results will be recorded separately once actually observed.

No code/settings/.env/credential/dependency/UI change, real eBay/AI call, staging/publishing/withdrawal or service restart was performed by Codex. Published history remains unchanged. **Stop for Regan's restart; do not begin Phase 3.**

## 2026-11-14: Migration B Post-Restart Verification Passed

**The preceding pending-restart state is resolved.** Regan reported "Restarted"; Codex then checked the actual NSSM/Waitress service on port 8000 using read-only local requests. Migration B installation, backup/restore and the requested post-restart checks are complete. This is not Sprint 25 closure and does not authorise Phase 3.

### Service Restart And Serving-Version Proof

| Check | Observed result |
| --- | --- |
| NSSM service | Running, PID **22824**, changed from 26960 |
| Actual port-8000 Python listener | PID **19772**, changed from 4764 |
| Listener start | **2026-11-13 23:38:59.426633 UTC** (14 November Australia/Sydney), after the requested restart handoff and implementation commit |
| Process chain | NSSM 22824 -> venv launcher 16480 -> listener 19772 |
| NSSM AppDirectory | `D:\Magpie\app\backend` |
| NSSM application | `D:\Magpie\app\backend\.venv\Scripts\python.exe` |
| Entrypoint | `D:\Magpie\app\backend\serve.py`; imports Waitress and `django.core.wsgi` |
| Health | GET `http://127.0.0.1:8000/api/health/` -> **200**, status `ok` |
| Checked checkout HEAD | **`ef2b0ee1a63bab1d347827876aad2c9f8f3813ba`**, descendant of **`1564d32127d2553585b2f291792b371cce78e836`** |
| Runtime source check | Entrypoint, WSGI and canonical/model/view/check/migration files match that checked HEAD; no application-code diff |

The new start time, live-checkout entrypoint/venv, source match and live canonical API response jointly verify the restarted service is using the implementation containing **1564d321 or later**. This is recorded as runtime-path/source/behaviour evidence, not a claim that an unimplemented version endpoint returned a Git hash.

### Canonical Draft Opens Read-Only

Only these authenticated local draft requests were made:

| Method / route | HTTP | Result |
| --- | --- | --- |
| GET `/api/items/4ab42c61-d9cb-428c-81bc-92278ad30f83/listing-drafts/` | **200** | Five GOLD-00002 drafts; first result is **`af013dd9-0611-431c-be4a-223c44ec4e06`**, staged, offer `356038014011`; four remaining rows are archived |
| GET `/api/listing-drafts/af013dd9-0611-431c-be4a-223c44ec4e06/` | **200** | The same canonical draft and unchanged local staged offer |

Source trace: `listItemListingDrafts` in `frontend/src/api/listing.ts` uses the first route; both `ListingPanel` and `QuickPublishPanel` use that shared function and default to the first result when no explicit selection/preview is active. This verifies the existing draft-opening resolution without clicking a create/save/publish action. No claim is made that the future Phase 3 "List on eBay" UI has been implemented. The item page was deliberately not mounted, because its eBay panels can trigger additional preflight/read-back queries.

The existing authenticated session was used in memory only; no session token, credential or raw response payload was printed or saved. The checker blocked outbound connects except to local port 8000, allowed no redirects, and performed no POST/PATCH/DELETE, save, draft creation, stage, publish, withdraw, eBay metadata/preflight or AI operation.

### Data And Constraint Remain Correct

- **8 drafts**, GOLD-00002 **1 active / 4 archived**, keeper `af013dd9`, local offer `356038014011` unchanged.
- **155 audit rows**, **1 ChannelListing**, **53 migration records**.
- Schema-only inspection still shows `listing_one_active_draft` as **unique and partial**, columns `item_id, channel`; no test rows inserted.
- Query-only `check_canonical_drafts`: **zero violations, constraint_installed true**. MigrationExecutor's read-only plan reports **zero pending migrations**.
- Full ordered-row digests for every table were equal before and after the GET checks. No data, historical record or session row was changed by validation.

At the checked runtime HEAD, [Validation 43528199055](https://github.com/GoldDiggerTriangle/magpie/actions/runs/43528199055) is **green on both lanes** (SQLite job `132239066750`, PostgreSQL job `132239067137`). The unchanged implementation's previously recorded results remain 264 passed / 1 skipped SQLite, 252 passed / 13 skipped PostgreSQL, and 123 frontend tests plus typecheck/build/collectstatic/smoke. No new application code, settings, credentials or schema change was needed for this verification.

**Stop and report:** the approved Migration B installation/restart sequence is verified. Phase 3 requires a separate instruction. Sprint 25 remains open; live publishing remains unproven.

## 2026-11-14 - Phase 3: Canonical Local Listing Editor

**Implementation complete and CI-validated; Administrator restart and Regan's phone acceptance remain pending. Sprint 25 is OPEN. Live publishing remains unproven.**

### Contract And Handoff

- Started from accepted Phase 2 head `fd6c43de076ba61c39fe80e5367c91a5843ca8e5` in `D:\Magpie\app`.
- Applied `MASTER_HANDOFF_UPDATE_2026-11-13_PHASE2_CLOSE.md` first, verbatim: all **13 Find strings matched exactly once**; handoff is **v4.67**. The supplied update was checked against the expected complete-file digest before adding this task's separate section 9 session entry.
- Controlling implementation scope: `docs/specs/SPRINT_25_SPEC.md` **v3.4 section 5**, D-136 canonical draft, D-137 unchanged item-page layout, and D-129 human price sources.
- Implementation head: **`5a1d345939494e2916f7f5929cc59da6e8502bab`**.

### Editor Surface

| Field / step | Implemented control and provenance |
| --- | --- |
| Title | Full editable item-title default; Unicode character count against 80; full-string save/resume tests |
| eBay category | Explicit search and leaf selection; chosen ID and name; manual ID plus explicit name confirmation after refresh; no automatic selection |
| Condition | Chosen-category snapshot options; **Not used by this category** when the policy has no conditions, including Nugget `139965`; legacy unused condition does not create a false blocker |
| Item specifics | Live-metadata snapshot's required/recommended fields; required flags and supplied values; custom rows retained; only required aspects block |
| Format / duration | Fixed or auction; duration options restricted to the chosen category's matching format; changing format clears the previous duration |
| Price | Explicit human asking price or an explicitly selected owned SaleRecord/Comparable/item asking figure; source label; server resolves evidence identity and requires known seller-receives basis and matching currency |
| Price exclusions | No AI/valuation default or price-regeneration action. Unknown-basis and unrelated evidence cannot be selected. Legacy source-uncertain price requires human confirmation or replacement |
| Quantity | Editable and positive; current draft value retained. Remaining-stock defaults remain Phase 8, not silently claimed here |
| Photos | Item-owned photo selection, order controls, visible selected order; at least one required; foreign or duplicate photo IDs rejected |
| Payment / postage / returns | Saved policy dropdowns show names **and actual supplied terms**; selected terms also render below: services, costs, handling, return window/payer, payment timing/methods. Missing terms say not recorded rather than assuming free postage or another value |
| Merchant location | Existing verified local merchant-location record, including ID/name/address and provenance; no Inventory API location call |
| Description | Editable, privacy-filtered eBay copy-pack-template default; existing regenerate/edit confirmation, HTML preview, subtitle, shipping note, boilerplate, SKU footer, copy and ZIP export controls retained |
| Readiness | Named blockers/recommendations, counts, passed-check details, and jump-to-field focus links |
| Source labels | Each field has an origin label; earlier values without recorded provenance say so honestly; explicit edits record human selection/edit provenance |

### Persistence And Safety

- **No schema change or migration.** Reuses `ListingDraft.channel_data` for bounded chosen-category metadata snapshots and the last category search, `generated_meta` for field/price provenance, existing `EbayAccountSnapshot` for policies, and existing `MerchantLocation` records.
- GET `/api/listing-drafts/<id>/editor/` reads saved context only. Loading the editor does not refresh eBay, stage, create an offer or save a draft.
- Explicit POST `/api/listing-drafts/<id>/refresh-metadata/` uses the existing taxonomy/account adapters and chosen-category Sell Metadata GETs, including the documented `get_listing_type_policies` operation. These are metadata-only paths. Snapshots show `fetched_at`, provenance and missing/stale state. Failed refreshes retain cached draft metadata and return a credential-free actionable error. **No live metadata refresh was invoked by Codex in this task.**
- Merchant-location refresh is deliberately not an Inventory API call: the editor uses the saved verified record and its recorded provenance. New locations are not silently created or selected.
- Queued autosave serialises human edits and uses `expected_updated_at` with an atomic conditional claim, including on SQLite. An older save response or background refetch cannot replace newer typing; conflicts return 409 without overwriting text. Save failure remains visibly unsaved. Navigation completes pending local saves and invalidates the shared draft queries.
- Existing canonical create/open endpoints remain the authority. Listing entry opens/reuses the canonical draft; the existing quick card also links to **Edit canonical listing draft** within the unchanged Listings / channels section. No new top-of-item action or layout migration was added.
- A staged draft retains its status and offer ID during local editing. Changed fields show **Local changes are not yet on eBay**. Drift from an older saved staging payload is also detected. Remote IDs, snapshots and stage markers cannot be overwritten through an editor save.
- Existing staging/publish pipeline code and its guards remain regression-tested independently. The new editor's staging/review actions are deliberately inert in this local-only phase. No auto-restage, Inventory call, offer call, publish, withdraw, AI call, live draft save, new live draft, service restart, dependency change, settings change or credential change occurred.
- Historical/published/archived and in-flight drafts remain non-editable. No history or ChannelListing was rewritten.

### Tests And Build

Implementation [Validation **43534577678**](https://github.com/GoldDiggerTriangle/magpie/actions/runs/43534577678) is **green on both lanes**:

| Check | Result |
| --- | --- |
| SQLite job `132260360753` | **294 passed, 1 skipped** |
| PostgreSQL job `132260360380` | **282 passed, 13 skipped** |
| Frontend, 34 test files | **134 passed** |
| Typecheck / production build | PASS |
| CI collectstatic / deploy checks / Waitress-WhiteNoise smoke | PASS |
| Local Django check / migration check | PASS; **No changes detected** |
| Local collectstatic | PASS; production static files rebuilt; no restart performed |

Thirty new backend cases cover field round trips, conditionless/required-condition and format-duration rules, required-only aspect blocking, real policy terms, D-129 source validation, unknown-currency/unrelated evidence rejection, local staged drift, reserved metadata, stale-save conflict, malformed JSON, immutable history, explicit metadata GET ports, offline reads and secret-free refresh failure. Eleven new frontend tests cover full editor save/resume, no mount-time write/remote operation, actual policy terms, explicit source selection, refresh, readiness focus, stale-response and refetch races, save failure, and read-only history. Prior canonical/partial-unique, copy-pack, AI review, photo, pricing and quantity regressions remain in the green suites.

The local backend runner refuses outbound socket connections and uses an isolated SQLite test database and synthetic configuration. An initial concurrent frontend run timed out in an unchanged pricing-panel test; rerunning with one worker passed without changing or skipping that test or increasing its timeout. GitHub's ordinary frontend run also passed. The existing large-bundle warning remains non-blocking; no bundling/layout refactor was attempted.

### Browser Proof - Isolated, Not Live Phone Acceptance

Reproducible utility: `node scripts/sprint25_editor_check.mjs`, using temporary external Playwright tooling, the actual React editor and stylesheet, and `frontend/src/fixtures/listingEditor.json`. Every API request is intercepted. Unrecognised requests and all non-local browser destinations are blocked. The harness has no production API proxy or live database connection and closes its Vite/browser processes after checking.

- **390 x 844:** document scroll width **390**, every editor field inside viewport, button targets at least **44px**.
- **1440 x 1000:** document scroll width **1440**; fields and buttons fit.
- Full human title saved through the UI and reloaded intact; staged-local-change notice shown. **0 unexpected requests, 0 page errors, no stage/publish/withdraw/preflight/read-back call.**
- [Phone metadata and real-shaped policy terms](docs/evidence/sprint25/phase3/phone-metadata.png)
- [Phone title, source and editor controls](docs/evidence/sprint25/phase3/phone-title-price.png)
- [Desktop canonical editor](docs/evidence/sprint25/phase3/desktop-editor.png)

These are browser-emulated fixture screenshots, **not** a claim of an iPhone or live-service save. Regan must still restart and try the real editor on his phone.

### Live Data Was Not Saved

Read-only ordered-row digests across **all 46 live tables** matched the pre-task baseline. Counts remain **8 drafts, 1 ChannelListing, 156 audit rows and 53 migration records**. The baseline already contained 156 audit rows at task start; the earlier Phase 2 entry's 155 was not rewritten, and this task created none. GOLD-00002's canonical `af013dd9-0611-431c-be4a-223c44ec4e06` and staged offer `356038014011` remain untouched.

`ItemDetail.tsx` is byte-for-byte unchanged. Protected settings/credential/dependency/spec files and the pre-existing untracked `CLAUDE_STRUCTURAL_AUDIT.md` remain unchanged. The supplied handoff update and all changed files were scanned without exposing any secret value. No migration means no new live migration backup/restore operation was necessary in Phase 3; Phase 2's recorded installation/restore proof stands.

### Stop For Regan

Run `Restart-Service -Name Magpie` in Administrator PowerShell, then load the live port **8000** app and hard-refresh. On **GSP-00001**, open **Listings / channels -> Listing -> Open listing draft** (Create draft if none), then verify the fields on the phone. Search/refresh metadata explicitly, select category/condition/policies/location yourself, set or confirm the asking price, check photo order, wait for **Saved locally**, leave and reopen to confirm it resumes. On GOLD-00002, any later edits must remain visibly local to offer `356038014011`; **nothing is to be re-staged or published in this phase**.

**Stop point:** awaiting Regan's Administrator restart and phone feedback. No Phase 4 defaults, Phase 5 publish work, Phase 6 top action/layout work or live listing acceptance is claimed.
