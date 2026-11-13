# Sprint 25 kickoff (v3.3): eBay listing, end to end

**To Codex. Reasoning: High.** The controlling document is `SPRINT_25_SPEC.md` **v3.3 (LOCKED 2026-09-27)**. It replaces v2.1 and the v1 quick-publish design. Read it in full before touching anything.

## Situation
- eBay publishing has errored since the Sprint 23–24 era. Features on the item page stopped being reachable when the layout was reorganised (tabs/collapsible sections).
- Your own structural audit (2026-09-24, `afe9b351`) found three overlapping publish entry points and drafts that never acquire eBay mappings. GOLD-00002 has 5 drafts, 4 of them empty.
- Secrets **have been rotated**. eBay has **not yet been reconnected**; Regan does that from Settings → eBay.

## What changed in v3 (the short version)
- **One canonical eBay draft per item, one editor, one preview** (D-136). Quick publish is a shortcut to that preview, not a separate pipeline.
- **Per-category listing defaults** (D-135). They are visibly labelled, and never supply price or quantity; quantity comes from remaining stock.
- **No item-page layout changes this sprint** (D-137). D-134 tabs are deferred. You restore reachability within the current layout.
- **Concurrency protection that works on SQLite**: an atomic claim via conditional update, a `publish_unknown` state with a reconcile step, recovery of interrupted `publishing` attempts via a stale threshold, unique constraints, and tests on both backends. `select_for_update()` is not protection on SQLite.
- **Draft clean-up:**
  - First, classify every real draft status as active or terminal; unclassified counts as active.
  - Then Migration A (clean-up, with a dry run Regan approves), then supervised resolution until the unresolved list is at zero, then Migration B (the constraint, with an abort-on-violation pre-check).
  - It never calls eBay and never touches published history.

## Order of work (strict)
1. **Gate 0:** after Regan reconnects, prove a fresh token, a working automatic refresh, complete scopes and a refreshed policy snapshot. **Never print token or `.env` values.**
2. **Phase 0 diagnostic:** run inventory item → `createOffer` → fees/validation on an item Regan picks. **`publishOffer` is forbidden.** Report the raw results. Success means "staging passed; live publishing remains unproven."
3. **Phase 1 reachability audit:** use git to establish the layout history, diff the three points (Phase 4, pre-reorganisation, HEAD), and deliver the reachability table. **Stop and report before building.**
4. Only then, the build phases 2–8 in spec order, plus the automated reachability gate.

## Stop-and-report points
- After Gate 0, after Phase 0, and after Phase 1.
- Before Migration A (dry-run report).
- Before Migration B, if the unresolved list isn't at zero.
- If Phase 0 returns "permission denied".
- Any item with more than one staged offer.

## Closure
Every item in spec §13, including:
- ONE supervised live listing with Regan present;
- the reachability table ticked off, and the automated gate green;
- dual-lane Validation green;
- migrations additive only, with a backup and restore spot-check;
- Administrator restart;
- phone screenshots;
- evidence files for Sprint 24 and 25 brought up to date;
- the closure note quoting the head hash and the Validation run ID.
