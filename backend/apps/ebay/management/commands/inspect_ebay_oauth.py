from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.http import QueryDict

from integrations.ebay import EbayUnavailable, HttpEbayAuthAdapter, _api_base


def _first(query: QueryDict, key: str) -> str:
    return query.get(key, "")


def _raw_query_value(query: str, key: str) -> str:
    prefix = f"{key}="
    for part in query.split("&"):
        if part.startswith(prefix):
            return part[len(prefix):]
    return ""


class Command(BaseCommand):
    help = "Print debug-safe parsed eBay OAuth authorize URL fields."

    def handle(self, *args, **options):
        state = "debug-state-for-inspection"
        try:
            adapter = HttpEbayAuthAdapter()
            consent_url = adapter.build_consent_url(state=state)
        except EbayUnavailable as exc:
            raise CommandError(str(exc)) from exc

        authorize_base, _, raw_query = consent_url.partition("?")
        query = QueryDict(raw_query, mutable=False)
        client_id = _first(query, "client_id")
        scopes = [scope for scope in _first(query, "scope").split(" ") if scope]
        raw_scope = _raw_query_value(raw_query, "scope")
        scope_separator = "%20" if "%20" in raw_scope else "+" if "+" in raw_scope else "(single)"

        self.stdout.write(f"environment={settings.EBAY_ENV}")
        self.stdout.write(f"authorize_base={authorize_base}")
        self.stdout.write(f"token_endpoint={_api_base(adapter.environment)}/identity/v1/oauth2/token")
        self.stdout.write(f"client_id_suffix={client_id[-6:] if client_id else '(missing)'}")
        self.stdout.write(f"redirect_uri={_first(query, 'redirect_uri')}")
        self.stdout.write(f"response_type={_first(query, 'response_type')}")
        self.stdout.write(f"scope_count={len(scopes)}")
        for scope in scopes:
            self.stdout.write(f"scope={scope}")
        self.stdout.write(f"scope_separator_encoding={scope_separator}")
        self.stdout.write(f"state_length={len(_first(query, 'state'))}")
