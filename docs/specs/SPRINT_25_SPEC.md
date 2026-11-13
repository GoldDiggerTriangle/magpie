# Magpie — Sprint 25 spec (v3.3 LOCKED): eBay listing, end to end

**Audience:** Codex. **Author:** Claude, with a ChatGPT cross-check. **Status:** LOCKED v3.3 (2026-09-27). It incorporates both ChatGPT cross-checks. v3.3 tightens the implementation only; no decision changes. It fixes the migration sequencing, the draft-status mapping, recovery of interrupted publishes, and the D-135 wording.
**Decisions:** D-135, D-136 and D-137 are **approved** by Regan.
**Supersedes:** SPRINT_25_SPEC.md v2.1. v3 keeps every v2.1 correction; §0 says what changed.
**Locks carried forward:** D-129 (prices only from Regan's figure or a picked evidence figure), D-132 (preview-gated publish), D-133 (the overhaul), and human-confirmed publish (zero-tap is forbidden). F-19, F-20 and F-21 also carry forward.
**D-137 (approved):** the tab migration is **deferred out of Sprint 25**. D-134 stays the target design, and only its timing changes. Regan reports the regression began with the tab/section reorganisation, when features stopped being reachable. Sprint 25 does not move the item-page layout; it restores reachability first. The MASTER_HANDOFF records D-134 as "locked, deferred by D-137".
**Baseline:** `main` @ `afe9b351` (structural audit, 2026-09-24).

---

## 0. Why v3 exists

The 2026-09-24 structural audit found that the v1 quick-publish was built **on top of** the degraded flow, before the restoration v2 required. What Regan experiences now:

- **Errors at publish.** This is now compounded by the rotation: the secrets were rotated, but eBay was never reconnected.
- **Features became unreachable after the item-page reorganisation** (Regan's report). The eBay publish surface is the worst case.
- **Can't find where to list.** There are three overlapping entry points: `QuickPublishPanel`, `ListingPanel`, and `PublishPanel` nested inside it. There are also `CopyPackPanel`, `ChannelListingsPage` and `EbaySettings`.
- **Missing fields/controls.** Drafts never acquire eBay mappings. GSP-00001 has a price and 4 photos but no category, condition, policies or location. GOLD-00002 has **five** drafts, and four of them are empty.

v3 fixes this with one principle: **one canonical eBay draft per item, one editor, one preview.** Quick publish and the full path both lead to the same preview of the same draft.

---

## 1. Gate 0: Reconnect and token proof (Regan and Codex)

1. Rotation is done. **Regan reconnects eBay** from Settings → eBay. This mints a fresh token under Pro Basic.
2. Codex proves, without printing any token values:
   - the access token was minted after the reconnect;
   - an automatic refresh succeeds (force-expire the access token locally, then make one read-only call);
   - granted scopes are complete;
   - the policy snapshot is refreshed, with `fetched_at` recorded.
3. The v2.1 rotation-recoverability requirement stands: restore-test old archives with the old passphrase and new archives with the new one.

**No UI work begins until Gate 0 and Phase 0 are reported.**

## 2. Phase 0: Diagnostic harness (report before building)

This carries forward v2.1. Using a real item Regan picks, the harness runs these calls in order and captures status, eBay error ID, message and `operation` for each:

1. `createOrReplaceInventoryItem`
2. `createOffer`
3. offer fees/validation where available

**`publishOffer` is forbidden in Phase 0.** Codex reports the raw results to Regan and Claude. The branches are:

- **Calls succeed:** "staging passed; live publishing remains unproven." `createOffer` can succeed with fields missing that later make `publishOffer` fail. Publishing is proven only by the supervised live listing in §13.
- **A specific error appears:** fix it and report.
- **Permission is still denied:** stop.

## 3. Phase 1: Reachability audit (written inventory, before rebuilding)

The regression was structural: features stopped being reachable when their container moved. So this audit covers the **whole item page and eBay surface**, not only the publish panel.

1. **Establish the layout history from git.** Find the commit(s) where the item page moved to tabs and/or collapsible sections. The 2026-09-24 audit describes collapsible sections at HEAD, while Regan experienced it as tabs, so the history must settle what actually shipped and whether it changed more than once.
2. **Diff three points:** the Phase-4 publish surface (Sprint 7: `fdbab2a`, `befa502`), the last commit **before** the first layout reorganisation, and HEAD.
3. **Deliver a table** with these columns: feature/control/step · where it was reachable before · where it is reachable now (the exact tap path) · status (reachable / hidden / only conditionally rendered / imported but never rendered / removed) · which commit changed it.
4. This table becomes the restoration checklist, and it goes in the evidence file. The rule is **nothing fewer than before the reorganisation**, and nothing fewer than Phase 4 on the eBay side.

**Automated reachability gate (new):** add a frontend test that renders the item page for representative items (unlisted, drafted, published, and sold/partially sold), opens each section, and asserts that every panel in the Phase-1 inventory is present. A future layout change that orphans a feature fails CI instead of reaching Regan.

## 4. Phase 2: Canonical draft model (D-136, approved)

- **One active eBay draft per item.** Other drafts get status `archived`. They are never deleted, and they stay viewable read-only.
- **Status mapping comes first.** Codex inspects the **actual** draft model: every status choice, plus any separate publish-state field. The Sprint 7 spec defined at least `draft`, `ready`, `staged`, `publish_failed` and `published`, and this sprint adds `archived`, `publishing` and `publish_unknown`.
  - Every status must be explicitly classified as **active** or **terminal**, in a table in the evidence file.
  - **Terminal** means only `published` and `archived`, plus any status that proves the listing ended on eBay. **Everything else is active**, including `ready`, `publish_failed`, `publishing` and `publish_unknown`.
  - A status nobody classified counts as active.
  - A test asserts that the constraint covers every active status, so no status can bypass the one-active-draft rule.
- **Database-level rule:** a partial `UniqueConstraint` on (item, channel) where status is active. It must be verified to be created on both SQLite and PostgreSQL.
- **Published history is never touched.** Published drafts, their `ChannelListing` rows and audit history are excluded from the migration and the constraint.
- **Choosing the keeper, per item and channel, among active drafts:**
  1. If exactly one draft holds a staged (unpublished) eBay offer, it is the keeper.
  2. If **more than one** holds a staged offer, the item goes on the **unresolved list** (see sequencing below).
  3. Otherwise, the keeper is the draft with the highest **completeness score**: one point each for title, eBay category ID, condition, price, at least 1 photo, payment policy, postage policy, return policy, merchant location, and having all required aspects filled (maximum 10).
  4. Ties go to the most recent `updated_at`, then the highest pk.
- **A draft holding a staged offer that is not the keeper is never archived automatically.** It also goes on the unresolved list. Migrations never call eBay.
- **Sequencing: the constraint is installed only after every duplicate is resolved.**
  1. **Migration A (data clean-up):** additive only. It adds the new statuses, then archives the non-keepers wherever the rules allow. It writes one audit-log row per archived draft, including the pre-archive status, offer ID if any, and score. Regan approves a dry-run report before the real run. Expected result: GOLD-00002 goes to 1 active draft and 4 archived.
  2. **Supervised resolution:** each item on the unresolved list is resolved with Regan present. Unwanted staged offers are withdrawn or deleted on eBay, and their drafts are archived with audit rows. The unresolved list must reach **zero**.
  3. **Migration B (the constraint):** before installing the partial unique constraint, a pre-check counts violations. If there are any, it **aborts and names the items**, so it never half-applies. It is installed only when the count is zero, and it is verified on both SQLite and PostgreSQL.
- Creating a draft when an active one exists **opens the existing one**. It does not duplicate.
- Published drafts are immutable. Relisting creates a new draft, which is seeded from the published one.
- Quick publish, the item page and the eBay hub all resolve to the same canonical draft.

## 5. Phase 3: The draft editor becomes the listing screen

Every field is visible and editable, and each shows where its value came from:

| Field | Source / control |
|---|---|
| Title | item title, editable; 80-char counter |
| eBay category | live taxonomy suggestions and search; chosen ID and name shown |
| Condition | live valid conditions for the chosen category |
| Item specifics | live required/recommended aspects; required ones flagged |
| Format | Fixed / Auction |
| Duration | valid durations for the format |
| Price | D-129 sources only, with a visible source label |
| Quantity | defaults to remaining quantity (Phase 8) |
| Photos | select and reorder from the item's photos; ≥1 required |
| Payment / Postage / Return policy | dropdowns from the refreshed snapshot (2 / 9 / 4 today) |
| Merchant location | dropdown (MARYBOROUGH-AU today) |
| Description | copy-pack template as the default body, editable |

- Taxonomy and policy data are **offline snapshots with `fetched_at` and provenance** (v2.1), plus a "Refresh from eBay" control. Live validation re-runs at publish time.
- A **readiness panel** lists every blocker by name, with a jump-to-field link.
- Autosave. The draft can be resumed from anywhere.

## 6. Phase 4: Per-category listing defaults (D-135, approved)

Regan sets defaults **once per Magpie category**: eBay category, condition, three policies, location, format and duration. New drafts pre-fill from these, and each pre-filled field shows a "from Stamps defaults" tag.

This **relaxes v2's "never pre-select" wording.** Nothing is chosen by the system: every value is a human choice made earlier, visible in the editor and in the preview. **Category defaults never supply price or quantity; listing quantity comes from remaining stock** (Phase 8). A category with no defaults set leaves the default-able fields empty.

Editing a default does **not** rewrite existing drafts.

## 7. Phase 5: Review and publish (one pipeline)

- **Preview:** the composed listing as eBay will see it, with hard gates (price source, ≥1 photo, postage, condition, category, required aspects, healthy connection). If any gate fails, Post is disabled and the failures are named with fix links.
- **Full path:** editor → preview → stage (`createOffer`) → staged review → **type-the-SKU** → `publishOffer`. The Sprint-7 protocol stays intact, including withdraw.
- **Quick publish** is a shortcut to the same preview for the canonical draft. Two taps; the second is "Post live to eBay". It is not a separate pipeline.
- Keep the `befa502` guards: refuse to publish if `listing_id` exists or the draft is already published.
- **Concurrency protection must work on SQLite,** which is the live database. There, `select_for_update()` does nothing, so a row lock alone is not enough. Instead:
  - **Atomic claim:** a conditional update such as `filter(pk=…, publish_state="idle").update(publish_state="publishing", publish_attempt=<uuid>)`. Only the request whose update affects 1 row calls `publishOffer`; every other request gets "already publishing".
  - **Outcomes:** on a definite failure the draft returns to `idle` and the error is recorded. On an **unknown outcome** (timeout or dropped connection) it becomes `publish_unknown`. Retry is blocked until a reconcile step reads the offer from eBay and records either the live listing ID or a clean failure.
  - **Interrupted attempts (crash recovery):** every claim records `publish_started_at`. The publish call has a hard timeout shorter than a stale threshold (for example, a 60 s timeout against a 10 min threshold). A draft still `publishing` past the threshold is treated as interrupted: it is moved to `publish_unknown`, which means it must be reconciled. This check runs on app startup, before any new claim on that draft, and from a management command. The health panel lists drafts stuck in `publishing` or `publish_unknown`.
  - **Reconcile** reads the offer from eBay:
    - if it is published with a listing ID, write the `ChannelListing` row and mark the draft `published` (catching an eBay success the crash hid);
    - if it is definitely unpublished, return the draft to `idle`;
    - if eBay can't be reached, the draft stays `publish_unknown`.
  - **Another publish is never allowed while a draft is `publishing` or `publish_unknown`.**
  - **Uniqueness backstop:** a `UniqueConstraint` on `ChannelListing` (channel, external listing ID) and on (channel, draft).
  - **Tests:** simultaneous-publish tests (threads or processes, with `publishOffer` mocked) run against **both** a file-backed SQLite test database (not in-memory) and PostgreSQL. They assert exactly one `publishOffer` call and exactly one `ChannelListing` row.
- On success: live URL, `ChannelListing` row, item status updated, and the Sprint-22 board and take-down checklist stay truthful.

## 8. Phase 6: Findability, without a layout migration (D-137)

- **No tab migration in this sprint.** The existing item-page layout stays. Every feature the Phase-1 table marks as hidden, conditionally unreachable or never rendered is made reachable again within that layout.
- **"List on eBay" is always visible on the item page.** It appears near the top of the page, not inside a collapsed section, and it creates or opens the canonical draft. The Listings section opens with the draft editor entry; copy packs sit below it, unchanged.
- The standalone `QuickPublishPanel` and nested `PublishPanel` entry points are **folded into the one draft flow** (§7). Their controls survive only as parts of the editor, preview or publish steps. Nothing is removed until the Phase-1 table confirms it exists in the new flow.
- The **eBay hub** (`/settings/ebay`, or a new `/ebay` in the nav) shows drafts in progress, live listings, orders and connection health.
- **Mandatory "no content lost" checklist:** every row of the Phase-1 table is ticked off as reachable after the sprint, with its tap path, and the checklist goes in the evidence file. The automated reachability gate (§3) must be green.
- D-134 (tabs) returns later as its own small sprint, only after the reachability gate exists to protect it.

## 9. Phase 7: Honest errors and connection health

- Every error is named and actionable. Plan/permission errors say so. Token failure shows "Reconnect eBay". Validation errors map to the offending field in the editor.
- A health panel shows: account, token status/expiry, last successful call, scopes, snapshot ages, and a Reconnect button.
- A persistent banner appears across the app when eBay is disconnected or refresh has failed.

## 10. Phase 8: Multi-quantity

Wire remaining quantity to listing quantity, respecting Sprint-10 semantics (sold X of Y; take-down only at zero remaining). Variations, volume pricing and bulk tools are out of scope.

## 11. Fee engine

- Add a **category-tier fee table**: FVF % up to the threshold, % above it, per-order fee, and international %. Regan enters the figures himself; they are never estimated.
- F-21 covers Coins, Stamps, Collectables, Banknotes and Gold (Tier 4). **Phones & Electronics, Tools and any unmapped category show "fee rate not configured"** and are excluded from profit maths. They never borrow another tier's rate.
- Seller mode moves to Pro. Own listings are on a seller-receives basis. Sprint-18 comp-basis rules are unchanged.

## 12. Out of scope

Variations, volume pricing, Discounts Manager, bulk/batch/background posting, other channels' APIs, and any scraping.

## 13. Acceptance criteria (closure gate)

- Gate 0 proof and the Phase 0 diagnostic were reported **before** UI work began.
- The Phase 1 inventory was delivered, and the rebuilt editor was checked field by field against it.
- Canonical draft (tests):
  - The status-classification table is in the evidence file, and the test proves every active status is covered by the constraint.
  - The Migration A dry-run report was approved by Regan, the unresolved list reached zero, and Migration B's pre-check aborts on a seeded violation (test).
  - Duplicates are archived with audit rows, and published history is unchanged.
  - The partial unique constraint rejects a second active draft on SQLite and on PostgreSQL.
  - The keeper-selection rules (staged offer, completeness score, tie-breaks) each have a test.
  - Creating a draft while one is active opens the existing one.
- Concurrent publish: the simultaneous-publish tests pass on SQLite and PostgreSQL. Reconcile is tested for published, unpublished and unreachable offers. A crash is simulated (a stale `publishing` row where eBay shows the offer published), and reconcile records the listing without a second `publishOffer` call.
- Phase 0 was reported as "staging passed; live publishing remains unproven" (or as an error), never as UX-only.
- Editor: create → edit every field → save → resume → preview (tests and live proof).
- Defaults pre-fill and are labelled; category defaults never supply price or quantity, and quantity comes from remaining stock; editing defaults doesn't touch existing drafts (tests).
- Each gate blocks and names its blocker (tests for missing price, photo, postage, condition and category).
- Forced-error tests (expired token, validation failure, permission denied) each give a named message.
- The Phase-1 reachability table is in the evidence file, with every row ticked as reachable (with its tap path), and the automated reachability gate is green.
- No item-page layout migration took place (D-137).
- **Live:** ONE real listing, Regan present, of an item he genuinely wants to sell. Result: live URL plus a `ChannelListing` row.
- No zero-tap path exists. Copy packs and the take-down checklist stay regression-green.
- Suites, typecheck, build and collectstatic are green; dual-lane Validation is green; migrations are additive only, with a backup plus restore spot-check; Administrator restart done.
- Phone screenshots of: the item page's "List on eBay" action, the editor, the gated preview and the live URL.
- `SPRINT24_EVIDENCE.md` and `SPRINT25_EVIDENCE.md` are brought up to date with the owner confirmations.
- The closure note quotes the head hash and the Validation run ID.

## 14. For Codex

Reasoning: High. Work in this order: reconnect proof, then diagnose, then audit, and only then build. Do not move the item-page layout (D-137); restore reachability within it. Restore against evidence, not memory. There is one draft, one editor and one preview; quick publish is a shortcut to that preview, not a second pipeline. Prices only from D-129 sources. Gates are hard, failures are named, and `ChannelListing` stays truthful. Never echo `.env` values or tokens, including in logs, evidence or audit payloads.
