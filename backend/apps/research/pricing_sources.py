from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, urlencode

from apps.intelligence.sold_search import broad_query
from apps.inventory.models import InventoryItem


@dataclass(frozen=True)
class PricingSourceLink:
    id: str
    label: str
    source_tag: str
    query: str
    url: str
    note: str
    primary: bool = False


@dataclass(frozen=True)
class PricingSourceTemplate:
    id: str
    label: str
    source_tag: str
    template: str
    note: str
    primary: bool = False

    def build(self, query: str) -> PricingSourceLink:
        if "{query_param}" in self.template:
            url = self.template.format(query_param=quote(query, safe=""))
        else:
            url = f"{self.template}?{urlencode({'q': query})}"
        return PricingSourceLink(
            id=self.id,
            label=self.label,
            source_tag=self.source_tag,
            query=query,
            url=url,
            note=self.note,
            primary=self.primary,
        )


SOURCE_TEMPLATES = [
    PricingSourceTemplate(
        id="ebay_sold",
        label="eBay sold",
        source_tag="ebay_sold",
        template="https://www.ebay.com.au/sch/i.html?_nkw={query_param}&LH_Sold=1&LH_Complete=1&_sop=13",
        note="Sold/completed eBay AU results. Magpie opens the URL only.",
        primary=True,
    ),
    PricingSourceTemplate(
        id="facebook_marketplace",
        label="Facebook Marketplace",
        source_tag="facebook_marketplace",
        template="https://www.facebook.com/marketplace/search/?query={query_param}",
        note="View-only marketplace search. Capture only what you manually verify.",
    ),
    PricingSourceTemplate(
        id="invaluable",
        label="Auction archive",
        source_tag="auction_archive",
        template="https://www.invaluable.com/search?query={query_param}",
        note="Auction-archive search. Results are not fetched or cached.",
    ),
    PricingSourceTemplate(
        id="worthpoint",
        label="Price guide",
        source_tag="price_guide",
        template="https://www.worthpoint.com/inventory/search?query={query_param}",
        note="Price-guide search. Store only user-captured evidence.",
    ),
    PricingSourceTemplate(
        id="google_general",
        label="General web",
        source_tag="web_search",
        template="https://www.google.com/search?q={query_param}",
        note="General evidence search for user review.",
    ),
]


CATEGORY_SOURCE_TEMPLATES = {
    "coins": [
        PricingSourceTemplate(
            id="numista",
            label="Numista",
            source_tag="numista",
            template="https://en.numista.com/catalogue/index.php?r={query_param}&ct=coin",
            note="Coin catalogue lookup for user review; not authoritative by itself.",
        )
    ],
    "stamps": [
        PricingSourceTemplate(
            id="colnect_stamps",
            label="Colnect stamps",
            source_tag="colnect",
            template="https://colnect.com/en/stamps/list/q/{query_param}",
            note="Stamp catalogue lookup for user review; not authoritative by itself.",
        )
    ],
}


def pricing_source_links(item: InventoryItem) -> list[PricingSourceLink]:
    query = pricing_query(item)
    if not query:
        return []
    templates = list(SOURCE_TEMPLATES)
    profile = item.category.profile_key if item.category_id and item.category else ""
    templates.extend(CATEGORY_SOURCE_TEMPLATES.get(profile, []))
    return [template.build(query) for template in templates]


def pricing_query(item: InventoryItem) -> str:
    from apps.intelligence.ai_research import latest_ai_search_query

    ai_query = latest_ai_search_query(item)
    if ai_query:
        return ai_query
    query = broad_query(item)
    if query:
        return query
    return " ".join((item.title or "").split()[:8])
