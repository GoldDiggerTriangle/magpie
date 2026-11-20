# Sprint 27 kickoff (v1.0): Small fixes — sold-out draft guard and keyboard-aware nav

**To Codex. Reasoning: High.** The controlling document is `SPRINT_27_SPEC.md` **v1.0 (LOCKED 2026-11-20, D-146)**. Read it in full first.

## What it is
Two small fixes from the Sprint 26 backlog. **A:** the server refuses to create a *new* eBay draft for an item with nothing left in stock (409, `sold_out`, “Sold out — nothing to list”), on every creation path. **B:** on iPhone, the bottom nav hides while the on-screen keyboard is open and returns when it closes. Plus a read-only attribution check of the right-edge drawer overlay.

## What it builds on
D-136 canonical-draft reuse and the canonical resolver (`backend/apps/listing/canonical.py`); Sprint 10 `quantity_remaining`; Sprint 25 `stock_revision`; Sprint 26’s audit test (whose 201 contract this sprint replaces); `AppShell` and `ListingSaveBar`.

## Must not break
- Resolver order: unresolved publish outcomes still go to reconciliation; an existing active draft is still returned (200) even at zero stock; the stock check comes only before fresh creation and relist seeding.
- Edits, withdrawal, archive and reconciliation at zero stock; Phase 5/8 stage/publish gates.
- Concurrency on SQLite (use `stock_revision`; `select_for_update()` does nothing there).
- Save bars must sit against the real visible bottom edge when the nav hides; never hide the nav when unsure.

## Order of work
Fix A (backend incl. admin Add and seed command, then the frontend message) → Fix B → drawer check → stop and report for Regan’s iPhone check.

## Guardrails
No migrations expected (§0 rule 12 if one appears). No eBay writes. **Never print token or `.env` values.**

## Closure gate
Spec §5: both lanes green with the race and admin/seed tests; Regan’s iPhone check; drawer closed only on positive attribution; restart; closure note; independent review.
