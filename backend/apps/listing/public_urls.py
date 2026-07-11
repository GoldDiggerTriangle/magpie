from __future__ import annotations

from urllib.parse import quote


def ebay_listing_url(listing_id: str) -> str:
    return f"https://www.ebay.com.au/itm/{quote(str(listing_id), safe='')}"
