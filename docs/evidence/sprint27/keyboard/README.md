# Sprint 27 Keyboard Geometry Checks

Automated Chromium fixtures at320/390x844, not real iPhone screenshots. All API requests are intercepted; external origins and unexpected writes are rejected. No live inventory, eBay or credential data is used. Test source: `frontend/e2e/sprint27.spec.ts`.

The visualViewport is simulated at a known844px closed height,450px keyboard height, with scroll/pan offsets. No keyboard bitmap is drawn: full-window screenshots can show content below the simulated visible bottom, which would be occluded by a real keyboard. Assertions use visualViewport geometry, not that unobscured image area. At layout scroll limits, the harness models independent Safari viewport panning; controls are reached by scrolling, not by an invented automatic save. The editor test also checks a shrinking innerHeight with an unchanged layout viewport, plus field clearance above the Save bar.

| Check |320px |390px |
|---|---|---|
| Writable focus plus viewport drop: nav hidden, document dimensions/scroll unchanged | [Image](keyboard-hidden-320.png) | [Image](keyboard-hidden-390.png) |
| Keyboard dismissed while field retains focus: nav restored | [Image](keyboard-restored-320.png) | [Image](keyboard-restored-390.png) |
| Orientation/uncertain baseline: nav remains visible | [Image](conservative-320.png) | [Image](conservative-390.png) |
| Details Save reachable by scrolling above keyboard | [Image](details-save-320.png) | [Image](details-save-390.png) |
| Add comparable reachable by scroll/viewport pan | [Image](comparable-320.png) | [Image](comparable-390.png) |
| Listing Save at the actual visible bottom; focused title clear above it | [Image](listing-save-320.png) | [Image](listing-save-390.png) |

Twelve PNGs copied unchanged/hash-verified from the final focused browser run; all decode at320/390x844 and are nonblank. Normal field focus/hardware-keyboard-like focus, minor browser-chrome changes, native select/read-only focus, zoom, orientation, desktop and absent/invalid viewport metadata are separately tested. Existing larger-text/long-title/reachability checks remain in the full34-test browser suite. Only the obsolete always-visible-nav offset assertion was adapted: when the nav is hidden, Save must clear the actual visible edge instead.

Regan's real-iPhone acceptance remains OPEN: switch fields, check Details Save, Add comparable and listing Save, dismiss the keyboard and confirm the nav returns without an added page jump. No physical keyboard, Safari or phone acceptance is inferred from Chromium. No eBay action is needed.
