# Magpie — Sprint 27 spec (v1.0 LOCKED): Small fixes — sold-out draft guard and keyboard-aware nav

**Audience:** Codex. **Author:** Claude, with a ChatGPT cross-check (D-143; six corrections adopted). **Status:** LOCKED v1.0 (2026-11-20). Regan chose to continue with the Sprint 26 backlog (“lets continue”).
**Decision:** **D-146** (this sprint).
**Locks carried forward:** D-126, D-136 (one active eBay draft per item; reuse), D-137’s successor D-145 (tabs), Sprint 10 stock semantics (`quantity_remaining` excludes superseded sales), Sprint 25 Phase 5 and Phase 8 rules (stage/publish gates, allocations, pending orders), §0 rules 10–12.
**Baseline:** `main` @ `dc2aea1` (handoff v5.00).

---

## 0. Why this sprint

Two Sprint 26 backlog items: (a) the backend accepts creating an eBay draft for an item with zero remaining stock (HTTP 201, quantity 0; `backend/apps/listing/tests/test_sprint26_audit.py`); the item page’s “Sold out” status only hides the entry; (b) on iPhone, the fixed bottom nav (`AppShell` `.mobile-bottom-nav`) stays visible above the keyboard and takes space while typing. A third item, the right-edge drawer overlapping the PRODUCTION badge, is attributed only on positive evidence (§3).

## 1. Fix A — server-side sold-out guard on NEW eBay drafts

1. **Order in the canonical resolver** (`backend/apps/listing/canonical.py`, `get_or_create_canonical_draft`), preserved exactly: (i) an unresolved publish outcome (`publishing` / `publish_unknown`) still requires reconciliation, as today; (ii) an eligible existing active draft is returned unchanged (`200`, D-136 reuse), **even at zero stock**; (iii) **only then** check stock, before both fresh creation and relist seeding from published history.
2. **Refusal:** `409` with a stable machine key `sold_out` and the message “Sold out — nothing to list.” (The create view currently maps validation errors to `400`; this refusal is `409`.) The frontend shows the message wherever it can be hit.
3. **Fresh stock inside the creation transaction:** use Sprint 10’s `quantity_remaining` (superseded sales excluded), never the item’s `sold` status label. Guard against a concurrent last-unit sale with the existing `stock_revision` conditional check (SQLite ignores `select_for_update()`).
4. **Every creation path:** the item page, the hub, relist seeding, quick publish, **Django admin “Add”** and the **seed command**, both of which bypass the resolver today. A supported change of channel into eBay counts as creation.
5. **Not a guard on updates:** otherwise-valid edits, withdrawal, archive and reconciliation stay available at zero stock. Phase 5/8 continue to enforce stock, allocations and pending orders at stage and publish.
6. **Restock:** raising `quantity_total` so that remaining > 0 makes creation possible again.
7. **Tests (SQLite and PostgreSQL):** refusal at zero (409, `sold_out`, no row created); reuse of an existing active draft at zero (200, unchanged); relist seeding refused at zero, with history untouched; partial stock allowed; restock re-enables creation; the sale-versus-create race (exactly one outcome consistent with final stock); admin Add and seed command refuse. **Replace** the Sprint 26 audit test’s HTTP 201 / quantity 0 assertion with the new contract.

## 2. Fix B — hide the bottom nav while the iPhone keyboard is open

1. **Detect the keyboard, not just focus.** On the mobile layout only, the nav hides when **both** a writable text field (text-like input or textarea) has focus **and** `visualViewport` height has dropped substantially from its keyboard-closed baseline. Recheck on viewport resize and scroll; restore the nav when the keyboard closes, even if focus remains. A native select or a hardware keyboard can hold focus with no on-screen keyboard; zoom and rotation also change the viewport: handle them so the nav is not hidden wrongly. **If uncertain, leave navigation visible.**
2. **No layout jump;** desktop unaffected; safe areas respected.
3. **Save bars:** `ListingSaveBar` measures the nav’s height today. When the nav is hidden, Save bars must position against the actual visible bottom edge and safe area, not a stale offset.
4. **Tests:** Playwright at 320/390px with a simulated viewport drop, for focus in and out, select focus with no keyboard, and nav restore. **Regan’s iPhone check:** switch between fields; reach Details Save, Add comparable and the listing editor’s Save; dismiss the keyboard and confirm the nav returns without a jump.

## 3. Drawer / PRODUCTION-badge backlog item

Read-only: Codex confirms whether Magpie’s code renders anything on the right edge (`AppShell` shows only a left desktop sidebar, hidden on phones). **Close the item only on positive attribution:** if toggling an external feature on Regan’s phone makes the overlay appear and disappear on the same Settings screen, record that evidence and close it as external. Otherwise it stays unattributed in the backlog. It does not block Fixes A and B.

## 4. Out of scope

The first live multi-quantity listing (needs a genuine multi-unit item); evidence-file tidying; any other screen or feature. **No migrations expected** (stop under §0 rule 12 if one appears). No eBay writes; no live saves except Regan’s own phone checks.

## 5. Acceptance (closure gate)

- Fix A tests green on both lanes, including the race and the admin/seed paths; the Sprint 26 audit contract replaced; no change to reuse, reconciliation or stage/publish behaviour.
- Fix B Playwright checks green; Regan’s iPhone check passes (nav hides only while typing, returns on dismiss, all three Saves reachable, no jump).
- Drawer item: closed on positive attribution, or left open with a note.
- Suites, typecheck, build, collectstatic and both Validation lanes green; Administrator restart; closure note with final head and Validation run; independent review (D-143) before CLOSED.

## 6. For Codex

Reasoning: High. Fix A first (backend, then frontend message), then Fix B, then the drawer check. Stop and report before Regan’s phone check. Never echo `.env` values or tokens.
