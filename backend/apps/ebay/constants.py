EBAY_ENV_SANDBOX = "sandbox"
EBAY_ENV_PRODUCTION = "production"
EBAY_ENVIRONMENTS = {EBAY_ENV_SANDBOX, EBAY_ENV_PRODUCTION}
DEFAULT_FAKE_ENVIRONMENT = EBAY_ENV_SANDBOX

EBAY_SCOPES = [
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.account.readonly",
]

OAUTH_STATE_TTL_MINUTES = 10

AUDIT_CONNECT_STARTED = "ebay.connect.started"
AUDIT_CONNECT_COMPLETED = "ebay.connect.completed"
AUDIT_CONNECT_FAILED = "ebay.connect.failed"
AUDIT_DISCONNECT_COMPLETED = "ebay.disconnect.completed"
AUDIT_TOKEN_REFRESH_COMPLETED = "ebay.token.refresh.completed"
AUDIT_TOKEN_REFRESH_FAILED = "ebay.token.refresh.failed"
AUDIT_POLICY_REFRESH_COMPLETED = "ebay.policy_refresh.completed"
AUDIT_POLICY_REFRESH_FAILED = "ebay.policy_refresh.failed"
