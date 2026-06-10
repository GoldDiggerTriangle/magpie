from collections.abc import Callable
from urllib.parse import quote, quote_plus, urlparse


URL_TEMPLATES = {
    "ebay_active": "https://www.ebay.com.au/sch/i.html?_nkw={query}",
    "ebay_sold": "https://www.ebay.com.au/sch/i.html?_nkw={query}&LH_Sold=1&LH_Complete=1",
    "terapeak": "https://www.ebay.com.au/sh/research?marketplace=EBAY-AU&keywords={query}&tabName=SOLD",
    "google": "https://www.google.com/search?q={query}",
    "google_images": "https://www.google.com/search?tbm=isch&q={query}",
    "colnect_stamps": "https://colnect.com/en/stamps/list/q/{query}",
    "colnect_coins": "https://colnect.com/en/coins/list/q/{query}",
    "numista": "https://en.numista.com/catalogue/index.php?r={query}&ct=coin",
    "pcgs_cert": "https://www.pcgs.com/cert/{cert_no}",
    "ngc_cert": "https://www.ngccoin.com/certlookup/{cert_no}/",
    "sgbaldwins": "https://sgbaldwins.com/search?searchTerm={query}",
    "gsmarena": "https://www.gsmarena.com/res.php3?sSearch={query}",
}

EXPECTED_HOSTS = {
    "ebay_active": "www.ebay.com.au",
    "ebay_sold": "www.ebay.com.au",
    "terapeak": "www.ebay.com.au",
    "google": "www.google.com",
    "google_images": "www.google.com",
    "colnect_stamps": "colnect.com",
    "colnect_coins": "colnect.com",
    "numista": "en.numista.com",
    "pcgs_cert": "www.pcgs.com",
    "ngc_cert": "www.ngccoin.com",
    "sgbaldwins": "sgbaldwins.com",
    "gsmarena": "www.gsmarena.com",
}


def verify_url_templates() -> bool:
    samples = {
        "query": quote_plus("Australia 1937 crown"),
        "cert_no": quote("12345678", safe=""),
    }
    for key, template in URL_TEMPLATES.items():
        url = template.format(**samples)
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise RuntimeError(f"{key} URL template must use https")
        if parsed.netloc != EXPECTED_HOSTS[key]:
            raise RuntimeError(f"{key} URL template host changed: {parsed.netloc}")
        if "{" in url or "}" in url:
            raise RuntimeError(f"{key} URL template left placeholders unresolved")
    return True


URL_TEMPLATES_VERIFIED = verify_url_templates()


def search_query(item) -> str:
    title = (item.title or "").strip()
    if title:
        return title

    attributes = item.attributes or {}
    brand_model = " ".join(
        str(attributes.get(key, "")).strip()
        for key in ("brand", "model")
        if str(attributes.get(key, "")).strip()
    )
    return brand_model or item.sku


def brand_model_query(item) -> str:
    attributes = item.attributes or {}
    brand_model = " ".join(
        str(attributes.get(key, "")).strip()
        for key in ("brand", "model")
        if str(attributes.get(key, "")).strip()
    )
    return brand_model or search_query(item)


def attr_query(item, attrs: dict, keys: tuple[str, ...]) -> str:
    parts = [
        str(attrs.get(key, "")).strip()
        for key in keys
        if str(attrs.get(key, "")).strip()
    ]
    return " ".join(parts) or search_query(item)


def phone_variant_query(item, attrs: dict) -> str:
    parts = [
        str(attrs.get(key, "")).strip()
        for key in ("brand", "model", "storage_gb")
        if str(attrs.get(key, "")).strip()
    ]
    if parts and attrs.get("storage_gb") not in {None, ""}:
        parts[-1] = f"{parts[-1]}GB"
    return " ".join(parts) or brand_model_query(item)


def build_url(template_key: str, query: str = "", cert_no: str = "") -> str:
    return URL_TEMPLATES[template_key].format(
        query=quote_plus(query),
        cert_no=quote(str(cert_no).strip(), safe=""),
    )


def link(label: str, url: str, source: str, note: str = "") -> dict:
    return {
        "type": "link",
        "label": label,
        "url": url,
        "note": note,
        "source": source,
    }


def checklist(label: str, note: str, source: str) -> dict:
    return {
        "type": "checklist",
        "label": label,
        "url": None,
        "note": note,
        "source": source,
    }


def ebay_active_url(query: str) -> str:
    return build_url("ebay_active", query=query)


def ebay_sold_url(query: str) -> str:
    return build_url("ebay_sold", query=query)


def generic_links(item) -> list[dict]:
    query = search_query(item)
    brand_model = brand_model_query(item)
    exact_query = f'"{query}"'
    sold_query = f"{brand_model} sold".strip()

    return [
        link("eBay active", ebay_active_url(query), "public search"),
        link("eBay sold", ebay_sold_url(query), "public search"),
        link("Terapeak", build_url("terapeak", query=query), "marketplace research"),
        link("Google", build_url("google", query=query), "public search"),
        link("Google Images", build_url("google_images", query=query), "public search"),
        link("Exact title", build_url("google", query=exact_query), "public search"),
        link("Brand/model sold", build_url("google", query=sold_query), "public search"),
    ]


def stamp_links(item, attrs: dict) -> list[dict]:
    query = attr_query(item, attrs, ("country", "year", "denomination", "topic_theme"))
    return [
        link("Colnect stamps", build_url("colnect_stamps", query=query), "public search"),
        link(
            "Stanley Gibbons Baldwin's shop/reference search",
            build_url("sgbaldwins", query=query),
            "dealer asking (shop search) - not catalogue value",
            "Dealer/shop/reference search only. Enter catalogue values manually as kind=catalogue comps.",
        ),
    ]


def coin_links(item, attrs: dict) -> list[dict]:
    query = attr_query(item, attrs, ("country", "year", "denomination"))
    entries = [
        link("Numista", build_url("numista", query=query), "public search"),
        link("Colnect coins", build_url("colnect_coins", query=query), "public search"),
        checklist(
            "Check Renniks AU Coin & Banknote Values (latest ed.)",
            "Print catalogue - no public searchable DB. Enter values as kind=catalogue comps.",
            "manual checklist",
        ),
    ]

    cert = attrs.get("cert") if isinstance(attrs, dict) else None
    if isinstance(cert, dict):
        grader = str(cert.get("grader") or "").strip()
        cert_no = str(cert.get("cert_no") or "").strip()
        if cert_no and grader == "PCGS":
            entries.append(
                link("PCGS cert verification", build_url("pcgs_cert", cert_no=cert_no), "cert verification")
            )
        elif cert_no and grader == "NGC":
            entries.append(
                link("NGC cert verification", build_url("ngc_cert", cert_no=cert_no), "cert verification")
            )
    return entries


def phone_links(item, attrs: dict) -> list[dict]:
    spec_query = attr_query(item, attrs, ("brand", "model"))
    variant_query = phone_variant_query(item, attrs)
    return [
        link("GSMArena", build_url("gsmarena", query=spec_query), "spec database"),
        link("eBay active phone variant", ebay_active_url(variant_query), "public search"),
        link("eBay sold phone variant", ebay_sold_url(variant_query), "public search"),
    ]


LINK_BUILDERS: dict[str, Callable[[object, dict], list[dict]]] = {
    "stamps": stamp_links,
    "coins": coin_links,
    "phones": phone_links,
}


def research_links(item) -> list[dict]:
    entries = generic_links(item)
    profile_key = item.category.profile_key if item.category else ""
    builder = LINK_BUILDERS.get(profile_key or "")
    if builder:
        entries += builder(item, item.attributes or {})
    return entries
