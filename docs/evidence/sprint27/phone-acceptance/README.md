# Sprint 27: Original iPhone Evidence

Received from Regan on 2026-11-20 after the restart/hard-refresh request. The four original JPEGs were copied unchanged from attachment directory `F006510F-0D30-4853-A7AF-4AF16C6C1E2E`; source and destination SHA256 values match. No crop, redaction, conversion or recompression was performed.

| Source | Filed Image | Bytes | SHA256 | Visible Evidence |
|---|---|---:|---|---|
| 1-Photo-1.jpg | [Condition picker](01-condition-picker-nav-visible.jpg) | 100386 | 0c15ed45e3f3535945dcb32b51f65d52a69930dab06e454958b61f309c027df3 | Native condition picker open; bottom navigation remains visible. |
| 2-Photo-2.jpg | [Title keyboard](02-title-keyboard-nav-hidden.jpg) | 98199 | 2ce0573ca1666e3771d5a10dbc2bd51d580c170af915013c8686eb1b630b63e2 | Writable title focused, keyboard open; Magpie bottom navigation hidden. |
| 3-Photo-3.jpg | [Title keyboard, second capture](03-title-keyboard-nav-hidden.jpg) | 99068 | e7be6cea23e64f0928462431d5d630d9ffc7b8c9e693ad8bef28a5fb64e92217 | Title focused at another cursor position; keyboard open, navigation hidden. This does not prove switching to another writable field. |
| 4-Photo-4.jpg | [Keyboard dismissed](04-keyboard-dismissed-nav-restored.jpg) | 92986 | 61b8e5fbf7e46dd6527f299ee98da08163598b740e6bf24d7a98c5dd03d0fbb7 | Keyboard absent; bottom navigation restored. |

## Evidence Limits

These are real iPhone screenshots, not the simulated Playwright geometry captures in the sibling `keyboard/` folder. They support conservative select behaviour, keyboard-time hiding and restoration. Still images do not prove absence of a transition jump, switching between writable fields, or reachability of Details Save, Pricing Add comparable and listing-editor Save with the keyboard open. Regan has been asked to confirm these; no click/save, full phone PASS or independent approval is inferred.

The gray right-edge handle remains visible. Its owner is still unknown: no same-Settings-screen external-feature on/off evidence was supplied. Drawer attribution remains OPEN, with no code change.

Read-only deployment verification and current acceptance status are appended to [SPRINT27_EVIDENCE.md](../../../../SPRINT27_EVIDENCE.md).
