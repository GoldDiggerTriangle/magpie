# Sprint 6 Production Connect Evidence

Date: 2026-06-12

Secret handling: production Cert ID, OAuth authorization codes, pasted redirect URLs, token values, and `MAGPIE_TOKEN_ENCRYPTION_KEY` are intentionally omitted. Environment setup is recorded by key presence and API/status shape only, never by secret value.

## Current status

Status: Complete and ready for formal Sprint 6 closure review.

Sprint 6 implementation is complete and PostgreSQL Validation is green. Commit `2de2df8` fixed the post-token account endpoint/connect persistence issue. Regan then completed a fresh production OAuth connect through the normal logged-in Chrome session.

Validated:

- Items 1-10: complete.

No production OAuth redirect URL, authorization code, token value, Cert ID value, or encryption key value is recorded in this file.

## 1. Production keyset configured

Status: ✓

Evidence:

- `.env` and `backend/.env` are gitignored.
- `backend/.env` contains the required production eBay key names.
- `MAGPIE_TOKEN_ENCRYPTION_KEY` was rotated only after confirming `EbayCredential` row count was `0`.
- Backend was restarted with the production env.

Sanitized configured/disconnected status before connect:

```json
{"configured":true,"environment":"production","connected":false,"ebay_username_present":false,"scopes_count":0,"access_token_expires_at":null,"refresh_token_expires_at":null,"last_refresh_error_present":false,"snapshot":{"opted_in":null,"policy_counts":{"payment":0,"fulfillment":0,"return":0},"fetched_at":null}}
```

## 2. Production OAuth connect succeeds

Status: ✓

Evidence:

- Regan reported completing the production OAuth browser step in normal Chrome after commit `2de2df8`.
- Regan signed into the real eBay account, approved access, pasted the redirected URL into Magpie only, and Magpie completed the connection successfully.
- Chrome UI showed `PRODUCTION`, connected `Yes`, access expiry, refresh expiry, both approved scopes, and audit action `ebay.connect.completed`.
- Account display showed `-`, expected for Sprint 6 because identity lookup is non-blocking and no identity scope is requested.
- The pasted redirected URL was not logged or stored.

## 3. Status shows connected in PRODUCTION

Status: ✓

Evidence:

Backend API status after connect:

```json
{
  "api_status_code": 200,
  "configured": true,
  "environment": "production",
  "connected": true,
  "ebay_username_present": false,
  "scopes": [
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.account.readonly"
  ],
  "access_token_expires_at": "2026-06-12 09:15:47.165340+00:00",
  "refresh_token_expires_at": "2027-12-11 19:15:47.165340+00:00",
  "last_refresh_error_present": false
}
```

Credential row count: `1`.

## 4. Tokens at rest are ciphertext

Status: ✓

Evidence:

Raw SQL ciphertext prefixes only:

```text
refresh_token prefix: gAAAAABqK7
access_token prefix:  gAAAAABqK7
```

Only 10-character Fernet ciphertext prefixes were recorded.

## 5. Business Policies readiness refresh

Status: ✓

Evidence:

Read-only production policy refresh result:

```json
{
  "api_status_code": 200,
  "opted_in": true,
  "payment_count": 2,
  "fulfillment_count": 9,
  "return_count": 4,
  "fetched_at": "2026-06-12T07:23:37.625098+00:00",
  "latest_policy_audit": "ebay.policy_refresh.completed"
}
```

Note: one earlier policy refresh attempt from the Codex command sandbox failed with sanitized `eBay account endpoint request failed.` Re-running the same read-only call with outbound network access succeeded. No token or secret values were printed or recorded.

## 6. Token refresh proven once

Status: ✓

Evidence:

The cached access token expiry was set to the past, then exactly one token refresh call was made.

```json
{
  "before_last_refresh_at": null,
  "after_last_refresh_at": "2026-06-12T07:25:11.660133+00:00",
  "access_token_expires_at": "2026-06-12T09:25:11.660104+00:00",
  "last_refresh_error_present": false,
  "latest_token_audit": "ebay.token.refresh.completed"
}
```

The refreshed access token value was not printed or recorded.

## 7. Admin redaction with real data

Status: ✓

Evidence:

Django admin credential page rendered with the real production credential:

```json
{
  "admin_status_code": 200,
  "redaction_marker_present": true,
  "editable_refresh_token_field_present": false,
  "editable_access_token_field_present": false,
  "plaintext_refresh_present_in_html": false,
  "plaintext_access_present_in_html": false,
  "ciphertext_refresh_present_in_html": false,
  "ciphertext_access_present_in_html": false
}
```

## 8. Disconnect -> verify -> reconnect cycle

Status: ✓

Disconnect evidence:

```json
{
  "disconnect_status_code": 204,
  "credential_count_after_disconnect": 0,
  "status_after_disconnect": {
    "configured": true,
    "environment": "production",
    "connected": false
  },
  "latest_disconnect_audit": "ebay.disconnect.completed"
}
```

Reconnect evidence:

- Regan completed a fresh production Connect flow in normal Chrome.
- Regan approved through eBay, copied the fresh Example Domain redirected URL, pasted it into Magpie only, and clicked Complete.
- UI showed `PRODUCTION` and connected `Yes`.
- The redirected URL and OAuth code were not printed or stored.

Final backend status after reconnect:

```json
{
  "credential_count": 1,
  "api_status_code": 200,
  "configured": true,
  "environment": "production",
  "connected": true,
  "ebay_username_present": false,
  "scopes": [
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.account.readonly"
  ],
  "access_token_expires_at": "2026-06-12 09:35:18.544530+00:00",
  "refresh_token_expires_at": "2027-12-11 19:35:18.544530+00:00",
  "last_refresh_error_present": false,
  "snapshot": {
    "opted_in": true,
    "policy_counts": {
      "payment": 2,
      "fulfillment": 9,
      "return": 4
    },
    "fetched_at": "2026-06-12 07:35:30.607242+00:00"
  }
}
```

## 9. Audit trail complete

Status: ✓

Sanitized action/timestamp sequence:

```json
[
  {
    "action": "ebay.connect.started",
    "created_at": "2026-06-12T07:15:35.990540+00:00"
  },
  {
    "action": "ebay.connect.completed",
    "created_at": "2026-06-12T07:15:47.200515+00:00"
  },
  {
    "action": "ebay.policy_refresh.failed",
    "created_at": "2026-06-12T07:19:45.101776+00:00"
  },
  {
    "action": "ebay.policy_refresh.completed",
    "created_at": "2026-06-12T07:23:37.642367+00:00"
  },
  {
    "action": "ebay.token.refresh.completed",
    "created_at": "2026-06-12T07:25:11.669876+00:00"
  },
  {
    "action": "ebay.disconnect.completed",
    "created_at": "2026-06-12T07:25:52.423268+00:00"
  },
  {
    "action": "ebay.connect.started",
    "created_at": "2026-06-12T07:35:08.637720+00:00"
  },
  {
    "action": "ebay.connect.completed",
    "created_at": "2026-06-12T07:35:18.551098+00:00"
  },
  {
    "action": "ebay.policy_refresh.completed",
    "created_at": "2026-06-12T07:35:30.623593+00:00"
  }
]
```

Note: the `ebay.policy_refresh.failed` entry was the earlier Codex command-sandbox outbound network failure. The same read-only policy refresh succeeded afterward with outbound access.

## 10. No secret visible anywhere

Status: ✓

Final checks:

```json
{
  "status_contains_plain_or_cipher_token_values": false,
  "audit_payloads_contain_plain_or_cipher_token_values": false,
  "audit_payload_forbidden_secret_keys": [],
  "audit_payload_contains_fernet_prefix": false,
  "admin_redaction_marker_present": true,
  "admin_editable_token_fields_present": false,
  "admin_contains_plain_or_cipher_token_values": false,
  "logs_contain_plain_or_cipher_token_values_or_env_secrets": false,
  "logs_contain_code_equals": false,
  "logs_contain_access_token_marker": false,
  "logs_contain_refresh_token_marker": false,
  "logs_contain_authorization_code_marker": false,
  "logs_contain_client_secret_marker": false,
  "logs_contain_encryption_key_marker": false,
  "logs_contain_fernet_prefix": false,
  "evidence_file_contains_full_plain_or_cipher_token_values_or_env_secrets": false,
  "status_token_fields_are_expiry_fields_only": true
}
```

Evidence file note:

- This file intentionally records 10-character Fernet ciphertext prefixes for D-65 item 4.
- It does not contain full ciphertext, plaintext token values, OAuth authorization codes, pasted redirect URLs, the production Cert ID value, or `MAGPIE_TOKEN_ENCRYPTION_KEY`.
