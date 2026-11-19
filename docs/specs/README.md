# Sprint Sources

Regan supplied the current Markdown documents in `C:\Users\Regan\Downloads\files.zip` on 2026-11-13. Both entries were checked for known local secrets and credential patterns before extraction, then copied byte-for-byte without editing their contents.

| Canonical File | Version / Header | Source File |
| --- | --- | --- |
| `SPRINT_25_SPEC.md` | v3.4 LOCKED: eBay listing, end to end | `C:\Users\Regan\Downloads\SPRINT_25_SPEC_v3.4.md` |
| `SPRINT_25_KICKOFF.md` | v3.4: eBay listing, end to end | `C:\Users\Regan\Downloads\SPRINT_25_KICKOFF_v3.4.md` |
| `SPRINT_26_SPEC.md` | v1.0 LOCKED: Item page - tabs and decluttering (phone-first) | `C:\Users\Regan\Downloads\SPRINT_26_SPEC.md` |
| `SPRINT_26_KICKOFF.md` | v1.0: Item page - tabs and decluttering (phone-first) | `C:\Users\Regan\Downloads\SPRINT_26_KICKOFF.md` |

The Sprint 26 sources were supplied on 2026-11-19, checked for known secrets and credential patterns, and copied byte-for-byte with matching SHA256 hashes. Only Phase 0 is authorised; importing the sources does not authorise layout implementation.

The initial D-141 commit `e1ae1059b1d4ed474215822a57edd720d51faf6e` contained clearly marked v2.0 PDF fallbacks because the Markdown sources were not yet available. Those historical PDFs are removed from this directory now that the actual v3.4 sources are present; they remain available in Git history. No PDF content was used to reconstruct these Markdown files.

The imported master handoff remains unchanged, as Regan required for this D-141 import. No session-log entry was added to it during this task because Regan explicitly prohibited editing it. This document import performs no Gate 0, staging, publishing, UI or implementation work.
