# Magpie — Sprint 26 spec (v1.1 LOCKED): Item page — tabs and decluttering (phone-first)

**Audience:** Codex. **Author:** Claude, with a ChatGPT cross-check (D-143; eight corrections adopted). **Status:** LOCKED v1.1 (2026-11-19). v1.1 adds the Phase 0 review decisions (§11): Regan chose a compact photo grid with an Arrange mode, and a plain “Sold out” status in place of the top button on sold-out items; Claude confirmed the tab mapping and the `#sales-valuations` destination. v1.0 (same day) was the ChatGPT-cross-checked lock. Regan chose the area (“GUI and graphical ergonomics”) and its focus: mostly iPhone use, item page first, and the problems are **clutter / confusing controls** and **too much scrolling**.
**Decisions:** **D-145** (this sprint; activates **D-134**, item-page tabs, locked 2026-07-13 and deferred by D-137 until a reachability gate existed — Sprint 25 built that gate).
**Locks carried forward:** D-126 (legibility first: readable text is never shrunk to look compact), D-129, D-132, D-133, D-135, D-136, D-144, §0 rules 10–12 (kickoff note, ChatGPT cross-check, migration preservation). Sprint 25’s pipeline behaviour is unchanged.
**Baseline:** `main` @ `8d0b1066` (handoff v4.95).

**Authorisation:** Phase 0 delivered (`0dc7e622`) and reviewed. **Phases 1–5 are authorised** under §11.

---

## 0. Why this sprint

On a phone, the item page currently shows, top to bottom: title, status and a red Delete button; the “List on eBay” entry and the quantity panel; Expand all / Collapse all; a seven-button section index; then seven accordions (Photos, Core details, Category specifics, AI research, Pricing evidence & comps, Listings / channels, Sales & valuations). (Phase 0 found the seven-button index shows only at desktop widths; on the phone it is Expand/Collapse plus accordions.) That is overlapping ways to move around one page, a destructive action at the top, and long scrolling once sections are open. The Sprint 24 regression came from reorganising this page without a reachability gate; Sprint 25 added that gate (76-row checklist; integrated reachability tests). This sprint changes the layout **behind** that gate.

## 1. Phase 0 — audit, then stop (no code changes)

1. 390px screenshots of every item-page state (each section open), for GOLD-00002 (live), GSP-00001 (draft), STM-00002 (sold out), plus fixture states: staged, publishing, publish_unknown, partial stock.
2. A control inventory that **reuses the Sprint 25 76-row table**, adding every control’s proposed tab and tap path (see §3).
3. **Task baselines, not just page height:** count taps and scroll distance (px) at 390px for three tasks — (a) edit a core field and a category specific and save; (b) open valuation and record a figure; (c) reach the listing editor and preview. Also record page height per state.
4. A list of every developer-style label on the item page and on the listing editor (all entry points): raw ISO dates, “AUD 0.0”, “source not recorded”, internal IDs, monospace dumps.
5. Which panels hold unsaved local state (editor fields, selected photos, research inputs) and how they behave if unmounted.
6. **Stop and report.** Regan marks what annoys him on the screenshots; Claude finalises the mapping.

## 2. Phase 1 — tabs (D-134)

- **Tabs:** Details · Photos · Research · Pricing · eBay · Sales. Sticky under the header. On a phone the bar scrolls sideways, and an off-screen tab must be visibly discoverable (edge fade or partial next tab; never hidden with no cue). On desktop, a full tab row.
- **Selection priority:** explicit deep link → remembered valid tab for this item → **Details**. A remembered tab that no longer exists falls back to Details.
- **Deep links preserved:** every existing `#hash` (including `#ai-review`, `#listing-…`, `#quick-ebay-…`), `?draft=` history links, upload-photo shortcuts and browser Back. Navigation **selects the destination tab first, then scrolls to and focuses the control.**
- **Removed:** Expand all / Collapse all and the section index. Accordions within a tab only where a tab is long enough to need them (justify each in the Phase 0 report).

## 3. Tab mapping (proposed; confirmed after Phase 0)

| Tab | Contents |
|---|---|
| Details | Core details form (title, category, location, condition and the rest, with its Save) · Category specifics (`SchemaFieldsForm`, with its Save) |
| Photos | `PhotoGallery`, `PhotoUploader`, `PhotoFixupPanel` |
| Research | `AIResearchPanel`, `SuggestionReviewPanel`, `ResearchLinks`, `ResearchLog` |
| Pricing | `DescriptorEvidencePanel`, `PricingEvidencePanel`, `SoldSearchPanel`, `ComparableList`, **`ValuationPanel` with its valuation-based `ProfitBreakdown`** |
| eBay | The canonical listing flow (`ListingPanel` / editor / preview / history), `EbayQuantityPanel`, `TakeDownChecklist`, and `CopyPackPanel` labelled **“Copy packs for other channels”** (usable with no eBay connection) |
| Sales | `SalesPanel` (actual sales) |

Every component on the page today must appear in exactly one row, and nothing may be dropped (the Phase 0 inventory proves it).

## 4. Phase 2 — compact header

- Title, SKU, status, and the Sprint 25 “List on eBay” entry with its status (behaviour unchanged).
- **Urgent warnings stay visible outside the eBay tab:** quantity mismatches (“Update eBay: N → M”) and zero-stock take-down, as a compact banner linking to the control (tab selected first).
- **Delete moves to a “More actions” menu**, keeping its existing confirmation, cancellation and restrictions; the confirmation names the item (title and SKU).
- Readable at D-126 sizes; tap targets at least 44px; safe areas respected.

## 5. Phase 3 — state preservation (critical)

- Today’s hidden accordion panels stay mounted. Tabs must **not** discard unsaved work: keep inactive tab panels mounted (or persist their state) so editor fields, selected photos and research inputs survive switching away and back, and survive background refreshes.
- Field-scoped saves stay as they are. **Tab navigation never saves, stages or publishes anything.**
- Tests: edit, switch tab, switch back, value intact; select photos, switch, return, selection intact; background refresh does not wipe input.

## 6. Phase 4 — plain language (item page and listing editor, all entry points)

- Reword for a reader; **never remove truth.** Unknown provenance becomes plain wording (e.g. “Source unknown”), not deleted. Missing money is never shown as $0.00 (“not set”). Calculated-versus-actual fee distinctions and named blockers stay.
- Dates in local, plain form (e.g. “15 Nov 2026, 12:44 am”). No monospace dumps; internal IDs only in details where they help.
- The editor’s wording changes apply wherever the editor appears (item page, hub, deep links).

## 7. Phase 5 — gate, tests and measurement

- **Keep all 76 original inventory rows and every existing behavioural assertion** in the reachability tests; add the tab dimension (each control’s tab and tap path). CI fails if any control becomes unreachable.
- New tests: tab-switch persistence (§5); deep-link tab selection and focus; published-history immutability; blocker navigation into the right tab and field; copy and download coverage; the remembered-tab fallback.
- States covered: unlisted, draft, staged, publishing, publish_unknown, failed, published, published-plus-active-draft, archived, partial stock, sold out.
- 320px and 390px with normal and larger text: no horizontal overflow; keyboard-open Save controls stay reachable; safe areas; off-screen tabs discoverable.
- **Repeat the Phase 0 task baselines.** Report taps and scroll distance before/after per task; a task that gets worse needs a reason or a fix.

## 8. Out of scope

Other screens (inventory list, home, hub layout), backend and API changes, eBay pipeline behaviour, the drawer/PRODUCTION-badge backlog item (unless Phase 0 shows it sits on the item page), new features. **No migrations expected**; if one appears necessary, stop under §0 rule 12.

## 9. Acceptance (closure gate)

- Phase 0 audit delivered and reviewed by Regan before any layout code.
- All six tabs live; every control from the 76-row table plus any later additions mapped and reachable; reachability CI green with the original assertions intact.
- No unsaved-work loss on tab switching (tests); no automatic save, stage or publish from navigation.
- Plain-language pass complete with truth preserved (missing values not shown as $0.00; calculated vs actual kept).
- Before/after task measurements show the three tasks need no more taps and less scrolling, or each exception is explained and accepted by Regan.
- Suites, typecheck, build, collectstatic and both Validation lanes green; Administrator restart; Regan’s phone acceptance on GOLD-00002, GSP-00001 and STM-00002, with screenshots of each tab and the header.
- Closure note quoting the final head and Validation run; independent review per D-143 before CLOSED.

## 10. For Codex

Reasoning: High. Audit first, stop, then build in phase order. Restore against evidence, not memory: the 76-row table is the contract. No live saves, staging or publishing during development or checks unless Regan explicitly asks. Never echo `.env` values or tokens.

## 11. Phase 0 review decisions (v1.1, 2026-11-19)

Phase 0 (`0dc7e622`): 63 screenshots, the 76-row inventory plus eight supplemental controls, task baselines, 46 label families and 22 state groups. Baselines to beat (390px): GOLD-00002 edit 5 taps / 10,492px scrolled, value 3 / 10,036px, list 1 / 9,518px; GSP-00001 edit 5 / 6,829px, list 2 / 11,180px; STM-00002 edit 5 / 5,169px, value 3 / 4,088px. The GOLD-00002 Photos section alone is 8,091px and open by default.

1. **Tab mapping confirmed** as in §3 and Codex’s inventory. **`#sales-valuations`** opens the **Pricing** tab at Valuation (its first content), and Pricing shows a visible shortcut to the Sales tab. Every other existing hash, `?draft=`, upload shortcut and Back mapping as proposed in the inventory.
2. **Photos tab: compact grid (Regan).** Thumbnails three across at 390px; tap a thumbnail to view it full size. **Arrange mode** (an explicit toggle) carries set-main, reorder (up/down or equivalent; the order saves and resumes) and delete (with its existing confirmation); these per-photo buttons are not shown on every photo outside Arrange mode. Upload stays prominent. Photo fix-up stays reachable inside the tab (an optional disclosure is acceptable). Nothing currently possible with photos may be lost: the inventory rows for photos are the contract. Fixes the per-photo button row overflowing its card at 390px.
3. **Sold-out items (Regan):** when remaining stock is zero, the header shows a plain **“Sold out”** status instead of the “List on eBay” button; if a listing exists, “View on eBay” stays. This is frontend behaviour only; Codex reports, read-only, whether the backend would accept a draft-create at zero stock, and any backend guard is a separate backlog item, not part of this layout sprint.
4. **Allocation label:** “eBay: Allocation not recorded” is shown only where it matters (multi-quantity items or a recorded allocation); on single-unit items it is hidden or worded plainly, never hiding a real mismatch warning.
5. **State-specific eBay notices:** while `publishing` or `publish_unknown`, the notice must not say “Unpublished staged offer … local changes are not yet on eBay”; it states the actual situation (publishing in progress / result being checked) and that editing is locked. Publish safety logic is unchanged; wording follows the state.
6. **Dirty-buffer protection (§5 extended):** Phase 0 found `ItemDetail`’s form resets on `item.data` changes, `ProfitBreakdown` costs reset on `item`, and other forms reset on refresh, and that `useDraftAutosave` flushes pending edits on unmount. Keep tab panels mounted (so switching never triggers that flush) **and** protect dirty fields from background-refresh resets (do not overwrite a field the user is editing; revalidate safely). Tests for each.
7. **Nested disclosures:** only those justified in the inventory’s “Nested Disclosure Justification” (Research reference lists, Pricing capture/history, eBay recommended/raw/template sections, Sales history if long). Required editor and readiness fields, review controls and valuation entry never go behind a further disclosure.
8. **Default tab Details** stands; Photos is no longer open by default.
9. **GSP-00001 value baseline** stays incomplete (no admissible figure); compare like with like using the fixture geometry rehearsal, labelled as such.
