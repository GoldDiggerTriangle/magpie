from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote


@dataclass(frozen=True)
class ReferenceSourceLink:
    label: str
    url: str


REFERENCE_SEARCH_SOURCES = (
    ("Google Images", "https://www.google.com/search?tbm=isch&q={query}"),
    ("General web reference", "https://www.google.com/search?q={query}"),
)


def build_reference_source_links(query: str, *, label_prefix: str = "") -> list[ReferenceSourceLink]:
    encoded = quote(query, safe="")
    prefix = f"{label_prefix} - " if label_prefix else ""
    return [
        ReferenceSourceLink(label=f"{prefix}{label}", url=template.format(query=encoded))
        for label, template in REFERENCE_SEARCH_SOURCES
    ]
