# Sprint 11 UI Completion Evidence

Date: 2026-06-15

Status: UI completion implemented and live-service proof captured. Final remote Validation is recorded below.

## Scope Implemented

- Added a first-class `eBay Orders` navigation entry.
- Added a reachable eBay order-import screen at `/ebay/orders`.
- Wired the screen to the existing Sprint 11 endpoints:
  - manual read-only order sync;
  - pending `EbayOrderStaging` list;
  - staging resolution by link, quick-create, or mark external;
  - pending `EbayOrderDuplicateCandidate` list;
  - duplicate candidate link/dismiss actions.
- Added loading, empty, success, and error states for sync, staging, and duplicate candidate panels.
- Added item-picker based linking using the existing inventory list API.
- Kept API calls same-origin through relative `/api/...` frontend clients.
- No backend models, migrations, schemas, or eBay API calls were added for this UI completion pass.

## Safety

- No real live staged rows were resolved during UI validation.
- The four real pending staged rows remained pending after the browser proof.
- No fake live sales were created.
- No engineered matched Magpie sale was created.
- Secret-bearing values, OAuth codes/tokens, credential payloads, rclone config, backup passphrases, and encryption keys were not printed or committed.

## Automated Frontend Evidence

Frontend:

- `npm run test`
  - passed: 20 files, 57 tests
- `npm run typecheck`
  - passed
- `npm run build`
  - passed

New UI tests prove:

- manual sync trigger shows created/staged/duplicate/skipped and fee actual/review counts;
- link-to-existing-item resolution posts the existing item choice;
- resolved staging row leaves the pending queue in the UI fixture;
- quick-create resolution posts a minimal item payload;
- mark-external with blank cost basis posts `cost_basis_override=null`;
- blank external cost basis surfaces as cost-basis-unknown sale feedback;
- resulting sale is reachable through the Sales screen link;
- Sales screen renders an eBay resolved external sale fixture;
- duplicate candidate empty state is shown;
- duplicate candidate link action is explicit and not auto-merged.

## Runtime Build and Service Evidence

Production build and collection:

- `npm run build`
  - passed
- `backend\.venv\Scripts\python.exe manage.py collectstatic --noinput`
  - passed: 7 files copied, 155 unmodified, 425 post-processed

Service restart:

- Regan restarted the `Magpie` Windows service from Administrator PowerShell after the new bundle was collected.
- `Get-Service Magpie` after restart:
  - status: Running
  - start type: Automatic
- `netstat` after restart:
  - `0.0.0.0:8000` listening on PID 8416
- `GET http://localhost:8000/api/health/`
  - 200, `{"status":"ok"}`
- `GET http://localhost:8000/assets/index-2lR74DoU.js`
  - 200
- `GET http://192.168.1.86:8000/ebay/orders`
  - 200, served the built SPA shell with the new hashed asset

The restart was required because the pre-restart Waitress/WhiteNoise process served the new `index.html` but returned 404 for the new hashed JavaScript asset.

## Live Browser UI Proof

Live browser evidence was captured against `http://localhost:8000/ebay/orders` using a short-lived Django session that was deleted after capture.

Screenshot:

- `docs/evidence/sprint11-ui-ebay-orders.png`

Sanitized browser-result summary:

- before clicking Sync:
  - pending staged rows text: `4 pending staged rows`
  - staging action rows: 4
  - duplicate candidate empty state: true
  - broken panel detected: false
- after clicking Sync:
  - sync completed: true
  - pending staged rows text: `4 pending staged rows`
  - staging action rows: 4
  - duplicate candidate empty state: true
  - fee actual count tile visible: true
  - fee review count tile visible: true
  - broken panel detected: false

Secret-free model-count check after browser proof:

- pending staging rows: 4
- resolved staging rows: 0
- pending duplicate candidates: 0
- sale records: 0
- external sale records: 0

## Remote Validation

- `Validation` for UI completion commit `41310c1` passed:
  - run: https://github.com/GoldDiggerTriangle/magpie/actions/runs/27506306626
  - sqlite: success
  - postgres: success

## Closure Status

Sprint 11 UI completion is implemented, live-deployed, and validated by the dual-lane `Validation` workflow. Final closure requires this evidence update to be committed and pushed.
