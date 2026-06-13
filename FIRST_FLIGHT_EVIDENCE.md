# Sprint 7 First-Flight Evidence

Date: 2026-06-13  
Environment: eBay production / EBAY_AU  
First-flight item: `STM-00003`  
Item: first-flight postage stamp  
Approved live publish price: AUD 1.00

## 1. CI And Pre-Publish State

Status: PASS

- PostgreSQL Validation was green before first-flight publish on commit `bcdc095`.
- Draft was staged before publish.
- Offer ID before publish: `186415699011`
- `listing_id` before publish: absent
- Draft status before publish: `staged`
- Item status before publish: `ready_to_list`
- Publish audit count before publish: `0`
- SKU publish gate had not been used before final approval.

## 2. Staged Review

Status: PASS

- Offer ID: `186415699011`
- SKU: `STM-00003`
- Title: `Australia 2017 Letter Rate stamp`
- Category: `105848` / `Postage Stamps`
- Condition ID: `3000`
- Inventory condition enum: `USED_EXCELLENT`
- Format: `FIXED_PRICE`
- Price: AUD `1.00`
- Quantity: `1`
- Photo count: `1`
- Media host: `i.ebayimg.com`
- Merchant location: `MARYBOROUGH-AU`
- Payment policy ID: `110076730020`
- Fulfillment policy ID: `179688792020`
- Return policy ID: `165601480020`
- Missing required aspects: none
- Unmapped local specifics: `Country`, `Year of Issue`, `Denomination`

## 3. Live Publish

Status: PASS

Initial publish was executed through the server-side SKU confirmation gate.

- Confirm SKU used: `STM-00003`
- Offer ID passed to `publishOffer`: `186415699011`
- Publish result: completed
- Listing ID returned by eBay and stored locally: `127919720667`
- Initial publish completed at: `2026-06-13T06:09:36Z`
- Draft status after publish: `published`
- Item status after publish: `listed`

Follow-up audit reconciliation found a second publish request from the UI actor `regan`:

- Second publish attempt at: `2026-06-13T06:29:53Z`
- Second publish success at: `2026-06-13T06:29:54Z`
- Returned listing ID: `127919720667`
- No second listing ID was observed in Magpie state or the eBay offer verification.

No revise, reprice, relist, order sync, or other post-publish automation was performed.

## 4. eBay Verification

Status: PASS

Read-only eBay Inventory API verification after publish:

- Offer ID: `186415699011`
- Offer SKU: `STM-00003`
- Offer marketplace: `EBAY_AU`
- Offer format: `FIXED_PRICE`
- Offer status: `PUBLISHED`
- Listing ID in eBay offer record: `127919720667`
- Listing status in eBay offer record: `ACTIVE`

Public listing page check:

- URL checked: `https://www.ebay.com.au/itm/127919720667`
- Result from direct non-browser request: HTTP `403 Forbidden`
- Interpretation: public page visibility could not be verified by Codex using a direct request. This is not evidence of publish failure because the eBay Inventory API reports the listing as `ACTIVE`.

Seller Hub active listing visibility:

- Regan visually confirmed the listing in Seller Hub -> Listings -> Active.
- Visible SKU: `STM-00003`
- Visible title: `Australia 2017 Letter Rate stamp`
- Visible eBay item/listing ID: `127919720667`
- Visible price: `AU $1.00`
- Visible quantity: `1`
- Visible time left: about `29d 23h`

## 5. Audit Trail

Status: PASS

Publish audit actions:

- `ebay.publish.attempted` at `2026-06-13T06:09:33Z`
- `ebay.publish.succeeded` at `2026-06-13T06:09:36Z`
- `ebay.publish.attempted` at `2026-06-13T06:29:53Z` by actor `regan`
- `ebay.publish.succeeded` at `2026-06-13T06:29:54Z` by actor `regan`

Relevant first-flight sequence includes:

- `ebay.media.uploaded`
- `ebay.inventory_item.upserted`
- `ebay.offer.created`
- `ebay.offer.withdrawn`
- `ebay.media.uploaded`
- `ebay.inventory_item.upserted`
- `ebay.offer.updated`
- `ebay.publish.attempted`
- `ebay.publish.succeeded`

No `ebay.publish.failed` audit entry was created.

## 6. No-Secret Checks

Status: PASS / PARTIAL

Checked:

- Listing-draft audit payloads for `STM-00003` contained no token/client-secret/auth-code key material.
- Publish audit payloads contained only `offer_id`, `listing_id`, and `sku`.
- Status-style local state contains no token, secret, authorization, password, or auth-code fields.
- This evidence file contains no OAuth redirect URL, OAuth code, access token, refresh token, Cert ID, or encryption key.

Log check:

- No current backend runserver log file was available under the known local temp log paths for this first-flight session.
- Old temp log files predated the first-flight publish and were not used as first-flight evidence.

## 7. Post-Publish Anomaly And Guard Fix

Status: PASS

Anomaly:

- Initial publish succeeded at `2026-06-13T06:09:36Z`.
- A later UI publish request by actor `regan` also returned success at `2026-06-13T06:29:54Z`.
- Both publish successes returned the same listing ID: `127919720667`.
- No second listing ID was observed locally or in the eBay offer verification.

Fix:

- Server-side publish now refuses if `listing_id` is already present.
- Server-side publish now refuses if the draft is already `published`.
- Server-side publish locks the draft row before checking publish state, so a second local publish request cannot call eBay after the first one stores `listing_id`.
- Frontend publish controls are hidden for drafts that are published or already have a `listing_id`.
- Existing listing ID remains visible as read-only listing state.
- Regression tests prove duplicate publish is blocked locally and does not call the eBay publish adapter.

No real eBay revise, reprice, relist, order sync, or other post-publish automation was run for this fix.

## 8. Final State

Status: PASS

- SKU: `STM-00003`
- Offer ID: `186415699011`
- Listing ID: `127919720667`
- Draft status: `published`
- Item status: `listed`
- eBay offer status: `PUBLISHED`
- eBay listing status: `ACTIVE`
- Seller Hub visual row check: confirmed by Regan
- Listing disposition: manually ended/cancelled by Regan in Seller Hub after first-flight verification.
- End/cancel method: Seller Hub manual action, not Magpie automation.
- Magpie did not run revise, reprice, relist, order sync, end-listing automation, or any other post-publish automation.
- Manual ending is outside Sprint 7 automation and is the expected first-flight exit path.
- This was a real eBay Australia live listing for the first-flight postage stamp.
