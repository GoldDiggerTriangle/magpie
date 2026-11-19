# Sprint 26 Phase 0 Control Inventory

Audit baseline: `8d0b10666bc8cbdb92f86232c586a62c4856cfb4`; proposed layout only. No tabs or controls are implemented by this report. Source: Sprint25 Phase6's exact76-row checklist in `SPRINT25_EVIDENCE.md`. The original `[x]` marks mean Sprint25 functional homes were accounted for; they do **not** mark Sprint26 implemented. Original IDs and current-path wording are retained unchanged.

## Component Homes (One Home Each)

| Component / ownership group | Proposed home |
|---|---|
| ItemDetail core/category forms + SchemaFieldsForm | Details |
| PhotoGallery / PhotoUploader / PhotoFixupPanel | Photos |
| AIResearchPanel / SuggestionReviewPanel | Research |
| ResearchLinks / ResearchLog | Research |
| DescriptorEvidencePanel / PricingEvidencePanel / SoldSearchPanel / ComparableList | Pricing |
| ValuationPanel + valuation-based ProfitBreakdown | Pricing |
| ListingPanel + ListingWorkflow + metadata/specifics/defaults dialogs | eBay |
| CopyPackPanel (Copy packs for other channels) | eBay, independent of connection |
| EbayQuantityPanel / TakeDownChecklist | eBay, with urgent header shortcut/status |
| SalesPanel (actual sales) | Sales |
| EbayListingEntry / item title/status/SKU / destructive-action confirmation | Header / More actions, not duplicated per tab |

A20 is an old grouped row spanning source links and reference research; its components have the distinct single homes above. Header warning shortcuts do not duplicate editable quantity/checklist forms. Global board/Settings/hub rows remain out of layout scope, with existing links preserved.

## All 76 Original Rows, With Proposed Tab And Tap Path

| Sprint25 row | Original Sprint25 current functional tap path / retained guard (unchanged) | Proposed tab / destination | Proposed tap path / behaviour to retain |
|---|---|---|---|
| [x] A01 | I header: title/status/SKU and confirmed Delete; unchanged. Top List on eBay added below header, outside accordions. | Header | Header title/status/SKU; More actions -> Delete -> title/SKU-named existing confirmation; cancel/restrictions retained. |
| [x] A02 | Existing AuthRequiredState full-page /admin/login/ recovery; routing regression retained. | Shell / sign-in | Existing full-page Sign in -> /admin/login/; do not put authentication recovery behind a tab. |
| [x] A03 | I -> Expand all / Collapse all; same seven sections and per-item stored state, no tab migration. | Tab navigation | Item -> Details/Photos/Research/Pricing/eBay/Sales; replace page-wide expand/collapse with destination selection, never save. |
| [x] A04 | Desktop Item sections index; existing section hashes and listing-* / quick-ebay-* hashes expand Listings; draft query deep link opens exact history. | Tab navigation / deep links | Desktop tab row or existing hash/query -> owning tab -> scroll/focus; explicit link beats remembered valid tab, then Details. |
| [x] A05 | I -> Photos -> gallery, Set main, Move earlier/later and confirmed photo delete; unchanged. | Photos | Photos -> own gallery -> Set main / Move earlier/later / confirmed Delete photo. |
| [x] A06 | I -> Photos -> Take photo / Choose from library (multiple, no capture on library); unchanged. | Photos | Photos -> Take photo / Choose from library -> Upload selected; retain library/camera choice and pending files. |
| [x] A07 | I -> Photos -> Local photo fix-up -> Generate review / Fix up all photos; unchanged, manual only. | Photos | Photos -> Local photo fix-up -> Generate review / Fix up all photos (explicit only). |
| [x] A08 | I -> Photos -> existing before/after review -> Tweak / Approve / Reject / Revert; conditional on own versions, unchanged. | Photos | Photos -> existing own-photo review -> Tweak / Approve / Reject / Revert; keep versions and pending tweaks. |
| [x] A09 | I -> Core details -> title/status/global condition/category/location/quantity -> Save; unchanged and separate from draft. | Details | Details -> Core details -> same fields -> field-scoped Save. |
| [x] A10 | I -> Category specifics -> schema/pickers/custom entry/catalogue repeater; unchanged. | Details | Details -> Category specifics -> schema pickers/custom values/catalogue repeater. |
| [x] A11 | I -> Category specifics -> cost inputs, estimated value and notes -> Save; no computed asking-price seeding. | Details | Details -> Category specifics -> costs/estimated value/notes -> field-scoped Save; no price inference. |
| [x] A12 | I -> Category specifics -> lot/source/disposition/scrap date; inherited source and cost locks unchanged. | Details | Details -> Category specifics -> lot/source/disposition/scrap date; retain inherited-source locks. |
| [x] A13 | I -> AI research -> existing status, provider/model/usage/cap and credential actions; untouched. | Research | Research -> AI research -> saved status/provider/model/usage/cap and credential controls; navigation makes no AI call. |
| [x] A14 | I -> AI research -> Identify & fill / Price-assist / existing view-only reference links; unchanged, no calls made. | Research | Research -> Identify & fill / Price-assist / view-only reference links; only explicit action invokes existing path. |
| [x] A15 | I -> AI research -> completion Review N staged suggestions -> #ai-review; unchanged. | Research | Completion Review N staged suggestions -> Research selected first -> #ai-review focus. |
| [x] A16 | I -> AI research -> Suggested fields -> Run OCR / Scan duplicates; manual staging only, unchanged. | Research | Research -> Suggested fields -> Run OCR / Scan duplicates; no call on tab open. |
| [x] A17 | I -> AI research -> suggestion row Approve / Edit / Reject; candidate leads remain separate, unchanged. | Research | Research -> suggestion -> Approve / Edit / Reject; preserve draft edit state and review-only candidates. |
| [x] A18 | I -> AI research -> Approve all shown over the rendered list; explicit sign-off, unchanged. | Research | Research -> rendered suggestion list -> Approve all shown; explicit visible-list sign-off only. |
| [x] A19 | I -> AI research -> formatted candidate text, Raw payload disclosure and quiet audit line; unchanged. | Research | Research -> formatted candidate -> Raw payload details and quiet audit metadata; retain truth, not primary JSON. |
| [x] A20 | I -> Pricing evidence & comps -> Own sales first sources / Search eBay sold / Assisted research; URL-only. | Pricing + Research (grouped row) | Pricing -> own-sales/source links and SoldSearchPanel; Research -> ResearchLinks/Assisted research. Each underlying component has one home below. |
| [x] A21 | I -> Pricing evidence & comps -> Item descriptor evidence -> stats / rows / Fast capture comp; unchanged. | Pricing | Pricing -> Item descriptor evidence -> stats / rows / Fast capture comp. |
| [x] A22 | I -> Pricing evidence & comps -> Item descriptor evidence -> Use this -> Buy calculator. Newly wired existing callback passes only owned record ID/context; local re-read applies known-basis evidence, never navigation price. | Pricing -> external Buy | Pricing -> Item descriptor evidence -> Use this -> existing Buy calculator with owned record ID/context; no navigation price. |
| [x] A23 | I -> Pricing evidence & comps -> Capture verified comp / Comparables edit/delete / four pricing grids; unchanged. | Pricing | Pricing -> Capture verified comp / Comparables edit/delete / pricing grids; preserve inputs. |
| [x] A24 | I -> Pricing evidence & comps -> Fill capture form from screenshot or link -> local OCR / Live Text helper; unchanged. | Pricing | Pricing -> Fill capture form from screenshot/link -> existing local OCR/Live Text helper; no page fetch. |
| [x] A25 | I -> Pricing evidence & comps -> Research log -> save / edit / delete; unchanged. | Research | Research -> Research log -> save/edit/delete; pending note/link state stays mounted. |
| [x] A26 | I -> Sales & valuations -> Valuation -> strategy/inputs/override/report history/current selection; unchanged and never used to generate listing price. | Pricing | Pricing -> Valuation -> strategy/inputs/override/history/current selection; never seeds listing price. |
| [x] A27 | I -> Sales & valuations -> Profit breakdown -> Save costs / existing current-report manual-price Calculate; unchanged. | Pricing | Pricing -> valuation-based Profit breakdown -> Save costs / manual Calculate; keep separate from realised sales. |
| [x] A28 | I -> Sales & valuations -> Sales -> Record sale / Correct, remaining stock and realised history; unchanged. | Sales | Sales -> Record sale / Correct -> actual sales/remaining-stock/history; no automatic restock. |
| [x] B01 | Top List on eBay opens shared canonical selection; no draft -> existing create endpoint on click only. Editor history rows select exact drafts; relisting is explicit. | eBay (header link where noted) | Header List on eBay -> eBay tab -> canonical editor/history; explicit creation only if no retained draft; relist stays explicit. |
| [x] B02 | E -> autosave / bottom Save / resume; Archive -> confirmation, never hard delete. Published/archived history disabled; staged offer must be removed first. | eBay (header link where noted) | eBay -> autosave / bottom Save / resume; Archive -> existing confirmation; read-only/in-flight/staged-offer guards retained. |
| [x] B03 | E -> Title / Subtitle / visible 80-char counter / Regenerate title with overwrite confirmation; retained. | eBay (header link where noted) | eBay -> Title/Subtitle/80-char counter -> Regenerate title with existing overwrite confirmation. |
| [x] B04 | E -> Description edit/Preview, regeneration, Boilerplate and SKU footer; retained, text/source visible. | eBay (header link where noted) | eBay -> Description Edit/Preview / regenerate / template/boilerplate / SKU footer; preserve editable content and provenance. |
| [x] B05 | E -> Format fixed/auction; same canonical draft and preview. | eBay (header link where noted) | eBay -> Format -> Fixed/Auction -> same draft/review. |
| [x] B06 | E -> Price / Currency / confirm own asking price / pick owned evidence; D-129 provenance in preview. Old Regenerate price bypass deliberately not retained. | eBay (header link where noted) | eBay -> explicit own asking price or owned evidence / Currency -> source shown in preview; no generated/valuation-price bypass. |
| [x] B07 | E -> Quantity, remaining-stock source for new drafts; existing stock/readiness gates unchanged. | eBay (header link where noted) | eBay -> Quantity -> remaining-stock source and allocation/availability validation. |
| [x] B08 | E -> Photos -> checkboxes / phone Move up/down -> saved order -> same ordered preview. | eBay (header link where noted) | eBay -> Photos -> select own photos / Move up/down -> saved order -> ordered preview. |
| [x] B09 | E -> Item specifics -> required first / recommended disclosure / picker+custom / add-remove custom / regenerate; retained. | eBay (header link where noted) | eBay -> required specifics first -> Recommended disclosure -> native picker/custom / add-remove / regenerate. |
| [x] B10 | E -> Shipping note plus real Postage policy terms; both appear in reviewed draft, no parallel quick note. | eBay (header link where noted) | eBay -> Shipping note and Postage policy -> same reviewed terms, not separate quick boxes. |
| [x] B11 | E -> Listing readiness -> named required/recommended/pass checks and Go to field; Refresh from eBay remains explicit. | eBay (header link where noted) | eBay -> Listing readiness -> named blocker -> owning tab/field selected before focus; explicit Refresh from eBay. |
| [x] B12 | E -> Export -> copy title/description/specifics/boilerplate and Download zip; retained for read-only history too. | eBay (header link where noted) | eBay -> Export -> Copy title/description/specifics/boilerplate / Download zip, including read-only history. |
| [x] B13 | E -> eBay listing details -> Search/Browse leaf categories, full path, chosen ID/name and manual-ID fallback; preview Go to category id focuses same control. | eBay (header link where noted) | eBay -> eBay category -> Search/Browse -> leaf selection; chosen ID/name and manual fallback remain inspectable. |
| [x] B14 | E -> eBay condition picker from chosen category; saved unverified ID visible; conditionless category says Not used. | eBay (header link where noted) | eBay -> category-valid Condition; conditionless category states not used; unknown is not guessed. |
| [x] B15 | E -> named Payment/Postage/Return policy pickers, real selected terms underneath; preview same terms. | eBay (header link where noted) | eBay -> Payment/Postage/Return -> named picker + readable real selected terms -> same preview. |
| [x] B16 | E -> Merchant location picker / Use another existing location key / Create merchant location -> review+confirmation. Restored creation uses only pre-existing endpoint; never auto-selects result. | eBay (header link where noted) | eBay -> Merchant location -> existing key / Create location -> review+confirmation; never auto-select. |
| [x] B17 | E -> required specifics/readiness and explicit metadata refresh; preview/publish live validation remains mandatory. Legacy override-required-aspects bypass intentionally unavailable, per gates. | eBay (header link where noted) | eBay -> required specifics/readiness -> explicit metadata refresh; no override-required-aspects bypass. |
| [x] B18 | E -> Review listing -> Stage reviewed listing / Update staged offer, explicit existing pipeline, never on open or hub load. | eBay (header link where noted) | eBay -> Review listing -> Stage reviewed listing / Update staged offer; exact explicit existing pipeline. |
| [x] B19 | E -> Review listing -> one staged read-back: values, sources, ordered photos, policy terms and authoritative ListingFee. | eBay (header link where noted) | eBay -> staged review -> values/sources/photo order/policy terms/eBay ListingFee. |
| [x] B20 | E -> Remove unpublished offer -> Confirm removal; same conservative Phase 5 endpoint; disabled/absent for in-flight or published. | eBay (header link where noted) | eBay -> Remove unpublished offer -> Confirm removal; never in-flight or published; ambiguous result remains fenced. |
| [x] B21 | E -> full staged review -> type exact SKU -> Confirm publish to eBay; reviewed revision and backend gates unchanged. | eBay (header link where noted) | eBay -> full staged review -> type exact SKU -> Confirm publish to eBay; backend review gates unchanged. |
| [x] B22 | Top separate View on eBay and read-only E published history -> Open live listing; no stage/publish/remove controls on history. | eBay (header link where noted) | Header View on eBay; eBay -> retained published history -> Open live listing; no publish/remove on history. |
| [x] B23 | E -> Duration picker, format-valid choices and stored/effective GTC; retained. | eBay (header link where noted) | eBay -> format-valid Duration; retain stored/effective GTC. |
| [x] B24 | E -> category-valid eBay condition picker; not the unrelated global item condition. | eBay (header link where noted) | eBay -> chosen-category Condition, not unrelated global item condition. |
| [x] B25 | E -> named account policy pickers with headline domestic price and readable full selected terms. | eBay (header link where noted) | eBay -> named policy choices/headline price and full terms; do not replace with raw IDs. |
| [x] B26 | E -> staged review -> nonzero fee components, eBay ListingFee total, Show all fees and listing-fees-only note. | eBay (header link where noted) | eBay -> staged review -> ListingFee total / nonzero components / Show all fees / listing-fees-only note. |
| [x] Q01 | Top stable List on eBay -> E -> Quick publish preview; one preview state shared with full review, no standalone card. | eBay / owning tab for blocker | Header List on eBay -> eBay -> Quick publish preview (same canonical draft and review). |
| [x] Q02 | Quick review blocker -> exact E category field, expanding section; browse/search/confirm are the same controls. | eBay / owning tab for blocker | Preview category blocker -> eBay selected first -> category field focus -> same Search/Browse/confirm. |
| [x] Q03 | E explicit human asking/evidence price, persisted source label and preview source; no private quick price pipeline. | eBay / owning tab for blocker | eBay -> explicit human/evidence price -> persisted source and same preview. |
| [x] Q04 | Quick blocker -> E Shipping note / Postage policy; no duplicate boxes, source/terms retained. | eBay / owning tab for blocker | Preview postage blocker -> eBay -> Shipping note/Postage policy field focus. |
| [x] Q05 | Quick/full blocker -> same E condition/photo control; if no own photos, expand existing Photos upload section instead of an empty picker. | eBay / owning tab for blocker | Preview condition/photo blocker -> eBay field; no own photos -> Photos tab -> upload control focus. |
| [x] Q06 | Preview live-metadata blocker Reconnect eBay -> /settings/ebay; hub reconnect uses same destination. | eBay / owning tab for blocker | Preview Reconnect eBay -> existing /settings/ebay; no new route or metadata refresh on navigation. |
| [x] Q07 | Top, hub, history and full/quick review share listing-drafts query/canonical resolver. Published history never masks active; no mount writes. | eBay / owning tab for blocker | Header/hub/history/deep link -> exact canonical eBay draft; active wins over published history. |
| [x] Q08 | E Quick publish preview -> Post live to eBay for exact reviewed revision, no SKU; full Review listing -> typed SKU. Drifted/invalid quick review cannot stage or post. | eBay / owning tab for blocker | eBay -> quick preview -> Post live for reviewed revision; full path keeps typed SKU; drift requires explicit update/review. |
| [x] D01 | I -> Listings / channels -> E first, then unchanged Ready-to-paste ad copy channel/price controls. | eBay | eBay -> canonical editor first -> Copy packs for other channels (available offline/without eBay connection). |
| [x] D02 | Same copy pack -> section Copy / Copy whole ad / own display Photo zip; unchanged. | eBay | eBay -> Copy packs for other channels -> section Copy / Copy whole ad / own Photo zip. |
| [x] D03 | H -> Open channel listings board -> existing manual add form; no new marketplace posting. | Unchanged external board | Existing hub -> Open channel listings board -> manual add; board layout out of scope. |
| [x] D04 | H -> channel board -> existing Seed local eBay rows; local-only, not run by agent. | Unchanged external board | Existing hub -> board -> Seed local eBay rows; preserve explicit local-only action. |
| [x] D05 | H -> channel board -> groups, days listed, item links / Mark ended; manual local tracking retained. | Unchanged external board | Existing board groups/days/item links/Mark ended; no automatic market ending. |
| [x] D06 | I -> Listings / channels -> take-down checklist / partial-sale notice; also existing board/Home alerts. No automatic ending. | eBay; urgent header shortcut | Header urgent sold-out/quantity warning -> eBay selected first -> TakeDownChecklist; actual checklist only in eBay. |
| [x] S01 | H -> eBay settings (/settings/ebay) -> existing Connect/paste-back/Complete/confirmed Disconnect; unchanged. | Unchanged Settings / hub | Existing /settings/ebay Connect/paste-back/Complete/confirmed Disconnect; unchanged outside item tabs. |
| [x] S02 | Same Settings -> Status account/environment/scopes/expiry/error; H adds honestly labelled saved health and snapshot age. | Unchanged Settings / hub | Existing Settings health/account/environment/scope/expiry/error; hub saved-health summary unchanged. |
| [x] S03 | Same Settings -> Policy Readiness -> counts/Fetched/Refresh; editor metadata refresh also explicit. | Unchanged Settings / hub | Settings Policy Readiness -> counts/Fetched/Refresh; editor's explicit metadata refresh remains in eBay tab. |
| [x] S04 | Same Settings -> Audit Log -> Action prefix and read-only rows; unchanged. | Unchanged Settings / hub | Settings Audit Log -> prefix/read-only rows; unchanged, no tab-local duplication. |
| [x] S05 | Same Settings -> Order Sync -> existing manual sync and link/quick-create/external/duplicate resolution; unchanged. | Unchanged Settings / hub | Existing Settings Order Sync -> manual sync/resolution; unchanged and not exercised. |
| [x] S06 | H -> Open eBay orders -> /ebay/orders -> existing sync/picker/resolution; old route preserved. | Unchanged Settings / hub | Existing hub -> Open eBay orders -> /ebay/orders; unchanged. |
| [x] S07 | Same Settings -> unchanged AI Provider and Profit Engine forms; no provider/fee/settings behaviour changes. | Unchanged Settings / hub | Existing Settings AI Provider / fee engine forms; no other-screen wording or behaviour changes. |
| [x] S08 | Nav eBay -> /ebay -> owned drafts/staged/check-result/live listings/orders/connection/history; explicit reconcile only, opening is GET-only. | Unchanged Settings / hub | Existing nav /ebay owned-record hub -> item draft link selects eBay; hub layout stays unchanged. |

## Explicit Supplemental Controls (Do Not Replace Original Rows)

| Audit ID | Control / state | Proposed home and tap path |
|---|---|---|
| N01 | Save these as category defaults; exact change/clearing review and confirmation | eBay -> Save these as category defaults -> review -> confirm; no price/specifics/quantity defaults, no draft rewrite. |
| N02 | Quantity allocation/legacy unknown, exact change checkbox/update, quantity reconcile | eBay -> quantity panel; urgent header link selects it first. Legacy allocation not recorded remains no-write, not a mismatch warning. |
| N03 | Publishing/publish_unknown Reconcile offer and conservative disabled edit/stage/publish state | Header check-result status -> eBay -> Reconcile offer (explicit). Never turn a label/diagnosis into retry permission. |
| N04 | Create relisting draft and retained archived/published row chooser | eBay -> explicit relist or exact read-only history row. No clone or auto-create on tab selection. |
| N05 | Conditional named error/diagnostics and blocker-to-field routing | eBay -> exact blocker -> owning tab then focus. Keep sanitised audit details inspectable. |
| N06 | Sticky measured Save/status bar, disabled on history/in-flight | eBay -> existing editor Save. Preserve full height reservation, 320/390 normal/larger text geometry. |
| N07 | Category Browse starter/breadcrumb/leaf-only path and manual existing location-key disclosure | eBay -> same existing category/location controls; only explicit metadata actions can call eBay. |
| N08 | Photo review tweak selection and suggestion edit buffer | Photos / Research respectively; preserve state when inactive, never auto-apply on tab switch. |

## Deep-Link And Navigation Decisions For Review

| Existing destination | Proposed destination before scroll/focus |
|---|---|
| #photos / upload shortcut event | Photos; select it before focusing the file control. |
| #core-details / #category-specifics | Details -> corresponding still-mounted form. |
| #ai-research / #ai-review | Research -> AI actions or suggestion review. |
| #pricing-evidence | Pricing -> evidence tools. |
| #listings-channels / #listing-* / #quick-ebay-* / ?draft= | eBay -> exact canonical/history editor and field; photos-missing blocker instead selects Photos. |
| #sales-valuations (legacy combined anchor) | **Needs Regan/Claude decision:** proposed Pricing/Valuation because that was the old section's first content, with a visible Sales shortcut. The old hash cannot simultaneously select two tabs. Do not silently drop or reinterpret it. |
| Browser Back | Restore explicit destination first, then remembered valid per-item tab, then Details. |

## Nested Disclosure Justification (Proposed Only)

- Details: two named forms without page-level accordion navigation; preserve their separate Save scopes.
- Photos: gallery plus potentially long before/after photo reviews. Keep optional fix-up/tweak disclosure only if review judges needed; never unmount pending file/tweak state.
- Research: AI reference lists are3751px on Gold and7283px on the banknote. A named reference-results disclosure can reduce scanning, but review controls and completion action must remain obvious and mounted.
- Pricing: current evidence section6312/6585/8334px plus Valuation/ProfitBreakdown. Named optional capture/history disclosures may be justified; primary evidence and valuation entry must stay findable. No generic card nesting.
- eBay: current section8333/7709px for Gold/banknote. Existing Recommended aspects, raw/audit details and template/copy-pack disclosures may remain; required editor/readiness fields must not disappear behind another navigation layer. Copy packs must work without eBay.
- Sales: actual sales form/history only, not valuation. Use history disclosure only if long; keep unsaved sale/correction state mounted.

All proposals await Phase0 review. No existing reachability assertion, original row, backend guard or price-source rule changes here.
+
## 2026-11-19: Approved v1.1 Implementation Homes

This section supersedes the historical "await review" proposals above. Regan/Claude confirmed the six-tab mapping and Pricing destination for #sales-valuations. The original76-row table and its Sprint25 cells remain unchanged; no row is removed or renumbered. Names below describe the implemented destination, not a claim of live phone acceptance.

| Original ID | Implemented home | Current tap path / guard |
|---|---|---|
| A01 | Header | Header -> More actions -> Delete item -> confirmation naming title/SKU -> Cancel or existing Delete; no destructive action from navigation. |
| A02 | Shell / sign-in | Existing full-page Sign in -> /admin/login/; do not put authentication recovery behind a tab. |
| A03 | Tab navigation | Item -> Details/Photos/Research/Pricing/eBay/Sales; replace page-wide expand/collapse with destination selection, never save. |
| A04 | Tab navigation / deep links | Desktop tab row or existing hash/query -> owning tab -> scroll/focus; explicit link beats remembered valid tab, then Details. |
| A05 | Photos | Photos -> thumbnail/full-size viewer; Photos -> Arrange -> Set main / earlier/later / Delete -> existing confirmation. |
| A06 | Photos | Photos -> Take photo / Choose from library -> Upload selected; retain library/camera choice and pending files. |
| A07 | Photos | Photos -> Local photo fix-up -> Generate review / Fix up all photos (explicit only). |
| A08 | Photos | Photos -> existing own-photo review -> Tweak / Approve / Reject / Revert; keep versions and pending tweaks. |
| A09 | Details | Details -> Core details -> same fields -> field-scoped Save. |
| A10 | Details | Details -> Category specifics -> schema pickers/custom values/catalogue repeater. |
| A11 | Details | Details -> Category specifics -> costs/estimated value/notes -> field-scoped Save; no price inference. |
| A12 | Details | Details -> Category specifics -> lot/source/disposition/scrap date; retain inherited-source locks. |
| A13 | Research | Research -> AI research -> saved status/provider/model/usage/cap and credential controls; navigation makes no AI call. |
| A14 | Research | Research -> Identify & fill / Price-assist / view-only reference links; only explicit action invokes existing path. |
| A15 | Research | Completion Review N staged suggestions -> Research selected first -> #ai-review focus. |
| A16 | Research | Research -> Suggested fields -> Run OCR / Scan duplicates; no call on tab open. |
| A17 | Research | Research -> suggestion -> Approve / Edit / Reject; preserve draft edit state and review-only candidates. |
| A18 | Research | Research -> rendered suggestion list -> Approve all shown; explicit visible-list sign-off only. |
| A19 | Research | Research -> formatted candidate -> Raw payload details and quiet audit metadata; retain truth, not primary JSON. |
| A20 | Pricing + Research (grouped row) | Pricing -> own-sales/source links and SoldSearchPanel; Research -> ResearchLinks/Assisted research. Each underlying component has one home below. |
| A21 | Pricing | Pricing -> Item descriptor evidence -> stats / rows / Fast capture comp. |
| A22 | Pricing -> external Buy | Pricing -> Item descriptor evidence -> Use this -> existing Buy calculator with owned record ID/context; no navigation price. |
| A23 | Pricing | Pricing -> Capture verified comp / Comparables edit/delete / pricing grids; preserve inputs. |
| A24 | Pricing | Pricing -> Fill capture form from screenshot/link -> existing local OCR/Live Text helper; no page fetch. |
| A25 | Research | Research -> Research log -> save/edit/delete; pending note/link state stays mounted. |
| A26 | Pricing | Pricing -> Valuation method/inputs/report/current selection; legacy #sales-valuations selects Pricing first. |
| A27 | Pricing | Pricing -> valuation-based Profit breakdown -> Save costs / manual Calculate; keep separate from realised sales. |
| A28 | Sales | Sales -> Record sale / Correct -> actual sales/remaining-stock/history; no automatic restock. |
| B01 | eBay (header link where noted) | Header List on eBay -> canonical eBay editor for positive remaining stock; Sold out at zero; separate known live link, retained history accessible via eBay tab. |
| B02 | eBay (header link where noted) | eBay -> autosave / bottom Save / resume; Archive -> existing confirmation; read-only/in-flight/staged-offer guards retained. |
| B03 | eBay (header link where noted) | eBay -> Title/Subtitle/80-char counter -> Regenerate title with existing overwrite confirmation. |
| B04 | eBay (header link where noted) | eBay -> Description Edit/Preview / regenerate / template/standard text / SKU footer; preserve editable content and provenance. |
| B05 | eBay (header link where noted) | eBay -> Format -> Fixed/Auction -> same draft/review. |
| B06 | eBay (header link where noted) | eBay -> explicit own asking price or owned evidence / Currency -> source shown in preview; no generated/valuation-price bypass. |
| B07 | eBay (header link where noted) | eBay -> Quantity -> remaining-stock source and allocation/availability validation. |
| B08 | eBay (header link where noted) | eBay -> Photos -> select own photos / Move up/down -> saved order -> ordered preview. |
| B09 | eBay (header link where noted) | eBay -> required specifics first -> Recommended disclosure -> native picker/custom / add-remove / regenerate. |
| B10 | eBay (header link where noted) | eBay -> Shipping note and Postage policy -> same reviewed terms, not separate quick boxes. |
| B11 | eBay (header link where noted) | eBay -> Listing readiness -> named blocker -> owning tab/field selected before focus; explicit Refresh from eBay. |
| B12 | eBay (header link where noted) | eBay -> Export -> Copy title/description/specifics/standard text / Download zip, including read-only history. |
| B13 | eBay (header link where noted) | eBay -> eBay category -> Search/Browse -> leaf selection; chosen ID/name and manual fallback remain inspectable. |
| B14 | eBay (header link where noted) | eBay -> category-valid Condition; conditionless category states not used; unknown is not guessed. |
| B15 | eBay (header link where noted) | eBay -> Payment/Postage/Return -> named picker + readable real selected terms -> same preview. |
| B16 | eBay (header link where noted) | eBay -> Merchant location -> existing key / Create location -> review+confirmation; never auto-select. |
| B17 | eBay (header link where noted) | eBay -> required specifics/readiness -> explicit metadata refresh; no override-required-aspects bypass. |
| B18 | eBay (header link where noted) | eBay -> Review listing -> Stage reviewed listing / Update staged offer; exact explicit existing pipeline. |
| B19 | eBay (header link where noted) | eBay -> staged review -> values/sources/photo order/policy terms/eBay ListingFee. |
| B20 | eBay (header link where noted) | eBay -> Remove unpublished offer -> Confirm removal; never in-flight or published; ambiguous result remains fenced. |
| B21 | eBay (header link where noted) | eBay -> full staged review -> type exact SKU -> Confirm publish to eBay; backend review gates unchanged. |
| B22 | eBay (header link where noted) | Header View on eBay; eBay -> retained published history -> Open live listing; no publish/remove on history. |
| B23 | eBay (header link where noted) | eBay -> format-valid Duration; retain stored/effective GTC. |
| B24 | eBay (header link where noted) | eBay -> chosen-category Condition, not unrelated global item condition. |
| B25 | eBay (header link where noted) | eBay -> named policy choices/headline price and full terms; do not replace with raw IDs. |
| B26 | eBay (header link where noted) | eBay -> staged review -> ListingFee total / nonzero components / Show all fees / listing-fees-only note. |
| Q01 | eBay / owning tab for blocker | Header List on eBay -> eBay -> Quick publish preview (same canonical draft and review). |
| Q02 | eBay / owning tab for blocker | Preview category blocker -> eBay selected first -> category field focus -> same Search/Browse/confirm. |
| Q03 | eBay / owning tab for blocker | eBay -> explicit human/evidence price -> persisted source and same preview. |
| Q04 | eBay / owning tab for blocker | Preview postage blocker -> eBay -> Shipping note/Postage policy field focus. |
| Q05 | eBay / owning tab for blocker | Preview condition/photo blocker -> eBay field; no own photos -> Photos tab -> upload control focus. |
| Q06 | eBay / owning tab for blocker | Preview Reconnect eBay -> existing /settings/ebay; no new route or metadata refresh on navigation. |
| Q07 | eBay / owning tab for blocker | Header/hub/history/deep link -> exact canonical eBay draft; active wins over published history. |
| Q08 | eBay / owning tab for blocker | eBay -> quick preview -> Post live for reviewed revision; full path keeps typed SKU; drift requires explicit update/review. |
| D01 | eBay | eBay -> canonical editor first -> Copy packs for other channels (available offline/without eBay connection). |
| D02 | eBay | eBay -> Copy packs for other channels -> section Copy / Copy whole ad / own Photo zip. |
| D03 | Unchanged external board | Existing hub -> Open channel listings board -> manual add; board layout out of scope. |
| D04 | Unchanged external board | Existing hub -> board -> Seed local eBay rows; preserve explicit local-only action. |
| D05 | Unchanged external board | Existing board groups/days/item links/Mark ended; no automatic market ending. |
| D06 | eBay; urgent header shortcut | Header urgent sold-out/quantity warning -> eBay selected first -> TakeDownChecklist; actual checklist only in eBay. |
| S01 | Unchanged Settings / hub | Existing /settings/ebay Connect/paste-back/Complete/confirmed Disconnect; unchanged outside item tabs. |
| S02 | Unchanged Settings / hub | Existing Settings health/account/environment/scope/expiry/error; hub saved-health summary unchanged. |
| S03 | Unchanged Settings / hub | Settings Policy Readiness -> counts/Fetched/Refresh; editor's explicit metadata refresh remains in eBay tab. |
| S04 | Unchanged Settings / hub | Settings Audit Log -> prefix/read-only rows; unchanged, no tab-local duplication. |
| S05 | Unchanged Settings / hub | Existing Settings Order Sync -> manual sync/resolution; unchanged and not exercised. |
| S06 | Unchanged Settings / hub | Existing hub -> Open eBay orders -> /ebay/orders; unchanged. |
| S07 | Unchanged Settings / hub | Existing Settings AI Provider / fee engine forms; no other-screen wording or behaviour changes. |
| S08 | Unchanged Settings / hub | Existing nav /ebay owned-record hub -> item draft link selects eBay; hub layout stays unchanged. |

Supplemental N01-N08 are implemented at their approved homes: defaults change/clear review in eBay; quantity/unknown result/take-down in eBay with urgent header shortcut; immutable history and explicit relist; named diagnostics and blocker focus; measured Save bar; category browse/manual key fallback; Photos Arrange/fix-up and Research suggestion buffers. Copy packs are labelled for other channels and do not require an eBay connection.

Evidence: full248 frontend tests; ItemDetail real-panel31-test state/navigation gate; 76-row raw-document CI integrity test; original editor/workflow/copy/download/take-down assertions;29 Playwright tests, including photo endpoint/order resume and deep-link focus. Obsolete Expand/Collapse/desktop-index assertions now assert the expressly authorised tabs; business assertions are retained (including all four original EbayListingEntry tests). No skip was added.

All11 listing/stock states remain covered. New320/390 normal/larger-text gates keep intentional tab-strip scrolling separate from document overflow. Header Sold out is frontend only: the unchanged backend still accepts a zero-stock draft (isolated201 test), backlogged separately. Independent review and Regan's phone acceptance remain open.
