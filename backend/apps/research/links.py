from urllib.parse import quote_plus


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


def ebay_active_url(query: str) -> str:
    return f"https://www.ebay.com.au/sch/i.html?_nkw={quote_plus(query)}"


def ebay_sold_url(query: str) -> str:
    return (
        "https://www.ebay.com.au/sch/i.html?"
        f"_nkw={quote_plus(query)}&LH_Sold=1&LH_Complete=1"
    )


def research_links(item) -> list[dict[str, str]]:
    query = search_query(item)
    brand_model = brand_model_query(item)
    exact_query = f'"{query}"'
    sold_query = f"{brand_model} sold".strip()

    return [
        {"label": "eBay active", "url": ebay_active_url(query)},
        {"label": "eBay sold", "url": ebay_sold_url(query)},
        {
            "label": "Terapeak",
            "url": (
                "https://www.ebay.com.au/sh/research?"
                f"marketplace=EBAY-AU&keywords={quote_plus(query)}&tabName=SOLD"
            ),
        },
        {
            "label": "Google",
            "url": f"https://www.google.com/search?q={quote_plus(query)}",
        },
        {
            "label": "Google Images",
            "url": f"https://www.google.com/search?tbm=isch&q={quote_plus(query)}",
        },
        {
            "label": "Exact title",
            "url": f"https://www.google.com/search?q={quote_plus(exact_query)}",
        },
        {
            "label": "Brand/model sold",
            "url": f"https://www.google.com/search?q={quote_plus(sold_query)}",
        },
    ]

