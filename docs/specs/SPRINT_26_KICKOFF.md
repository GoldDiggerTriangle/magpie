# Sprint 26 kickoff (v1.1): Item page — tabs and decluttering (phone-first)

**To Codex. Reasoning: High.** The controlling document is `SPRINT_26_SPEC.md` **v1.1 (LOCKED 2026-11-19)**. Read it in full before touching anything. **v1.1 (same day): Phase 0 reviewed; Phases 1–5 authorised under spec §11** (compact photo grid with Arrange mode; “Sold out” header status; state-specific eBay notices; dirty-field protection).

## What it is
Regan uses Magpie mostly on his iPhone. On the item page his problems are **clutter / confusing controls** and **too much scrolling**. This sprint replaces the seven accordions, the Expand/Collapse buttons and the section index with **tabs** (D-134: Details · Photos · Research · Pricing · eBay · Sales), compacts the header, moves Delete into “More actions”, and replaces developer-style labels with plain ones.

## What it builds on
- **Sprint 25’s reachability gate** (76-row checklist and integrated reachability tests). It exists precisely so this layout change cannot repeat the Sprint 24 regression.
- The Sprint 25 “List on eBay” entry and canonical listing flow, unchanged in behaviour.

## Must not break
- Any control’s reachability: all 76 original rows and every existing behavioural test assertion stay.
- Unsaved work: switching tabs must never lose editor fields, selected photos or research input (today’s hidden accordions stay mounted; tabs must match that).
- Deep links: `#hash` anchors, `?draft=` links, upload shortcuts, browser Back. Select the tab first, then scroll and focus.
- Truth in wording: plain language never deletes provenance, never shows missing money as $0.00, keeps calculated vs actual fees and named blockers.
- Navigation never saves, stages or publishes.
- D-126 legibility: don’t shrink text to look compact. 44px tap targets; safe areas; 320/390px with no overflow.

## Design direction
Phone first. One tab visible at a time; a sticky tab bar that visibly hints at off-screen tabs; a compact header carrying the title, SKU, status and “List on eBay”; urgent quantity and take-down warnings stay visible outside the eBay tab. Calm and readable over dense.

## Order of work
1. **Phase 0 audit (spec §1): screenshots, control inventory with proposed tab and tap path, task baselines (taps and scroll distance for edit / value / list), label list, unsaved-state findings. Stop and report.**
2. After Regan’s review: Phase 1 tabs → 2 header → 3 state preservation → 4 plain language → 5 gate, tests and remeasurement.

## Guardrails
No migrations expected (stop under §0 rule 12 if one appears). No live saves, staging or publishing unless Regan asks. **Never print token or `.env` values.**

## Closure gate
Spec §9: all tabs live and reachable with the original assertions intact; no lost work; truthful plain language; before/after task measurements; both Validation lanes green; Administrator restart; Regan’s phone acceptance with screenshots; closure note with head and Validation run; independent review (D-143).
