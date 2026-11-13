# Historical Sprint Specs

Archived on 2026-11-13 from `C:\Users\Regan\Downloads`. These 23 PDFs retain their original filenames and are byte-for-byte copies; no source files were changed.

This is a historical reference archive, not a replacement for the controlling handoff or current specs. Sprint 25 is deliberately excluded; its current v3.3 spec and kickoff remain in [docs/specs](../../specs/).

## Inventory

"Not stated" means the PDF has no explicit document-version line. Feature names such as "calculator v1" are not treated as document versions, and versions from the handoff have not been inferred. Revision notes below describe text actually present in the archived PDF.

| Sprint | Original File | Document Version Line | Revision Note |
|---|---|---|---|
| 0 + 1 | [SPRINT 0 1 SPEC.pdf](SPRINT%200%201%20SPEC.pdf) | Not stated | Combined Sprint 0 and Sprint 1 technical spec. |
| 2 | [SPRINT 2 SPEC.pdf](SPRINT%202%20SPEC.pdf) | Not stated | Research and valuation. |
| 3 | [SPRINT 3 SPEC.pdf](SPRINT%203%20SPEC.pdf) | Not stated | Commodity-live valuation and Gold schema. |
| 4 | [SPRINT 4 SPEC.pdf](SPRINT%204%20SPEC.pdf) | Not stated | Category schemas and catalogue-assisted research. |
| 5 | [SPRINT 5 SPEC.pdf](SPRINT%205%20SPEC.pdf) | Not stated | Listing draft builder. |
| 6 | [SPRINT 6 SPEC.pdf](SPRINT%206%20SPEC.pdf) | Not stated | eBay Connect. |
| 7 | [SPRINT 7 SPEC.pdf](SPRINT%207%20SPEC.pdf) | Not stated | eBay Publish. |
| 8 | [SPRINT 8 SPEC.pdf](SPRINT%208%20SPEC.pdf) | Not stated | Durability. |
| 9 | [SPRINT 9 SPEC.pdf](SPRINT%209%20SPEC.pdf) | Not stated | Robustness. |
| 10 | [SPRINT 10 SPEC.pdf](SPRINT%2010%20SPEC.pdf) | Not stated | Sales capture foundation. |
| 11 | [SPRINT 11 SPEC.pdf](SPRINT%2011%20SPEC.pdf) | Not stated | eBay own-order sync. |
| 12 | [SPRINT 12 SPEC.pdf](SPRINT%2012%20SPEC.pdf) | Not stated | Command-centre dashboard. |
| 13 | [SPRINT 13 SPEC.pdf](SPRINT%2013%20SPEC.pdf) | Not stated | Phase 5 local floor. |
| 15 | [SPRINT 15 SPEC.pdf](SPRINT%2015%20SPEC.pdf) | Not stated | Optional cloud two-phase AI deep-dive and reference lookup. |
| 16 | [SPRINT 16 SPEC.pdf](SPRINT%2016%20SPEC.pdf) | Not stated | Includes "4b. Part B - ROUND 2", added 2026-06-15. |
| 17 | [SPRINT 17 SPEC.pdf](SPRINT%2017%20SPEC.pdf) | Not stated | Local photo fix-up. |
| 18 | [SPRINT 18 SPEC.pdf](SPRINT%2018%20SPEC.pdf) | Not stated | Fee correctness and buy calculator. |
| 19 | [SPRINT 19 SPEC.pdf](SPRINT%2019%20SPEC.pdf) | Not stated | Evidence bank / comp memory. |
| 20 | [SPRINT 20 SPEC.pdf](SPRINT%2020%20SPEC.pdf) | Not stated | Profit intelligence. |
| 21 | [SPRINT 21 SPEC.pdf](SPRINT%2021%20SPEC.pdf) | Not stated | Lot purchase manager and source ROI. |
| 22 | [SPRINT 22 SPEC.pdf](SPRINT%2022%20SPEC.pdf) | Not stated | Multi-channel copy pack and sold-everywhere board. |
| 23 | [SPRINT 23 SPEC.pdf](SPRINT%2023%20SPEC.pdf) | `v1` (title continuation line) | Also includes section 6, ROUND 2, added 2026-07-06; no revised version line is stated. |
| 24 | [SPRINT 24 SPEC.pdf](SPRINT%2024%20SPEC.pdf) | Not stated | Includes section 10, ROUND 2, added 2026-07-06. |

## Missing Files and Search Coverage

- **Sprint 14 spec is missing.** No standalone spec was found in Downloads, Documents (including the old Codex checkouts), `C:\Users\Regan\.codex` (including remote attachments), or `D:\Magpie\app`. The filename search included all file formats and space/underscore/hyphen variants. Existing Sprint 14 evidence, screenshots and tests are not a substitute and were not copied as a spec.
- Ten inaccessible paths under Documents were pytest temporary/cache directories. They were not searched internally; permissions were not changed. The other searched roots reported no access errors.
- No separate kickoff, continuation or scope-discussion files matching the request were found in Downloads. This archive does not claim those companion documents are available.
- `SPRINT 25 SPEC.pdf` was intentionally skipped, as were the current Sprint 25 files in the Downloads bundle. Current Sprint 25 Markdown files remain unchanged in `docs/specs/`.

## Secret Checks and Copy Verification

Before copying, every PDF's extracted page text, metadata, form fields, annotations and raw bytes were checked against locally configured credential values and credential/token/private-key patterns. Checks ran in memory; no secret values or extracted plaintext files were written or printed. The PDFs contained no embedded attachments or large unscannable images. The empty final pages in Sprints 3 and 7 contain no extracted text or images.

No files were excluded for secret findings. SHA-256 comparisons verified that each archived PDF exactly matches its source. No application code, settings, environment files, database, service or Gate 0 state was changed.
