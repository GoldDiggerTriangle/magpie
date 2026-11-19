# Sprint 26 Implementation Screenshots

Baseline source checkout: `0dc7e622a40d5086b3f0c983aaca7571153ba9bc`. Sprint26 spec v1.1; 2026-11-19. New source UI rendered by an isolated Vite server, not claimed as already running on production.

390x844 CSS-pixel Chromium mobile/touch emulation, scale1, en-AU/Australia-Sydney. Owned-record responses were collected through the same guarded read-only snapshot as Phase0; every browser API request was intercepted. Four fixture states remain synthetic. These are not real iPhone captures or live eBay validation.

| State | Header / initial Details | Six full-page tab images | Arrange mode |
|---|---|---|---|
| GOLD-00002 | [Default](gold-live--default.png) | [Details](gold-live--details.png) / [Photos](gold-live--photos.png) / [Research](gold-live--research.png) / [Pricing](gold-live--pricing.png) / [eBay](gold-live--ebay.png) / [Sales](gold-live--sales.png) | [Arrange](gold-live--arrange.png) |
| GSP-00001 | [Default](gsp-draft--default.png) | [Details](gsp-draft--details.png) / [Photos](gsp-draft--photos.png) / [Research](gsp-draft--research.png) / [Pricing](gsp-draft--pricing.png) / [eBay](gsp-draft--ebay.png) / [Sales](gsp-draft--sales.png) | [Arrange](gsp-draft--arrange.png) |
| STM-00002 | [Default](stm-sold-out--default.png) | [Details](stm-sold-out--details.png) / [Photos](stm-sold-out--photos.png) / [Research](stm-sold-out--research.png) / [Pricing](stm-sold-out--pricing.png) / [eBay](stm-sold-out--ebay.png) / [Sales](stm-sold-out--sales.png) | [Arrange](stm-sold-out--arrange.png) |
| Fixture staged (fixture) | [Default](fixture-staged--default.png) | [Details](fixture-staged--details.png) / [Photos](fixture-staged--photos.png) / [Research](fixture-staged--research.png) / [Pricing](fixture-staged--pricing.png) / [eBay](fixture-staged--ebay.png) / [Sales](fixture-staged--sales.png) | [Arrange](fixture-staged--arrange.png) |
| Fixture publishing (fixture) | [Default](fixture-publishing--default.png) | [Details](fixture-publishing--details.png) / [Photos](fixture-publishing--photos.png) / [Research](fixture-publishing--research.png) / [Pricing](fixture-publishing--pricing.png) / [eBay](fixture-publishing--ebay.png) / [Sales](fixture-publishing--sales.png) | [Arrange](fixture-publishing--arrange.png) |
| Fixture publish_unknown (fixture) | [Default](fixture-publish-unknown--default.png) | [Details](fixture-publish-unknown--details.png) / [Photos](fixture-publish-unknown--photos.png) / [Research](fixture-publish-unknown--research.png) / [Pricing](fixture-publish-unknown--pricing.png) / [eBay](fixture-publish-unknown--ebay.png) / [Sales](fixture-publish-unknown--sales.png) | [Arrange](fixture-publish-unknown--arrange.png) |
| Fixture partial stock (fixture) | [Default](fixture-partial-stock--default.png) | [Details](fixture-partial-stock--details.png) / [Photos](fixture-partial-stock--photos.png) / [Research](fixture-partial-stock--research.png) / [Pricing](fixture-partial-stock--pricing.png) / [eBay](fixture-partial-stock--ebay.png) / [Sales](fixture-partial-stock--sales.png) | [Arrange](fixture-partial-stock--arrange.png) |

56 PNGs: initial viewport, six full-tab images and Arrange per state. All decode at390px and are nonblank; document scrollWidth equals clientWidth in every captured tab. Full-page images may show fixed navigation/Save at the original viewport position; scrollable content continues below it. Fixture photos without a stored URL remain placeholders, not invented production images.

[Capture metrics](capture-metrics.json), [21 repeated task runs](task-metrics.json), [GSP geometry-only valuation rehearsal](task-metrics-value-rehearsal.json). Real-record task saves and previews were simulated in browser memory only; no live save/eBay/provider call.

Browser regression suite additionally covers320/390px, normal/larger text, an80-character unbroken title, modal photo view, Arrange controls, staged/quick review, a reduced-height keyboard geometry check, sticky tabs and deep-link focus. Real Safari keyboard/safe-area/phone acceptance remains Regan's post-restart gate.
