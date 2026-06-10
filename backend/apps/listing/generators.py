from __future__ import annotations

from html import escape
from typing import Protocol

from django.utils import timezone

from apps.listing.constants import EBAY_TITLE_MAX
from apps.listing.context import safe_context


class ListingGenerator(Protocol):
    profile_key: str

    def title(self, ctx: dict) -> str: ...

    def description_html(
        self,
        ctx: dict,
        *,
        specifics,
        boilerplate_html,
        sku_footer,
    ) -> str: ...


class BaseGenerator:
    profile_key = "generic"

    def title(self, ctx: dict) -> str:
        return truncate_title(ctx.get("title") or ctx.get("category") or "Listing draft")

    def description_html(
        self,
        ctx: dict,
        *,
        specifics,
        boilerplate_html,
        sku_footer,
    ) -> str:
        sections = [
            heading("Overview"),
            paragraph(self.overview(ctx)),
            heading("Condition"),
            paragraph(ctx.get("condition_display") or "Condition not specified."),
        ]
        faults = self.faults(ctx)
        if faults:
            sections.extend([heading("Faults"), paragraph(faults)])
        sections.extend([heading("What's included"), paragraph(self.included(ctx))])
        table = specifics_table(specifics)
        if table:
            sections.append(table)
        if boilerplate_html:
            sections.append(str(boilerplate_html).strip())
        if sku_footer:
            sections.append(paragraph(f"<strong>SKU:</strong> {escape(str(sku_footer))}", raw=True))
        return "\n".join(section for section in sections if section)

    def overview(self, ctx: dict) -> str:
        return ctx.get("title") or ctx.get("category") or "Item for sale."

    def faults(self, ctx: dict) -> str:
        return str(ctx.get("faults") or "").strip()

    def included(self, ctx: dict) -> str:
        accessories = str(ctx.get("accessories") or "").strip()
        return accessories or "Item pictured only."


class PhoneGenerator(BaseGenerator):
    profile_key = "phones"

    def title(self, ctx: dict) -> str:
        storage = f"{ctx.get('storage_gb')}GB" if ctx.get("storage_gb") else ""
        parts = [
            ctx.get("brand"),
            ctx.get("model"),
            storage,
            ctx.get("colour"),
            display_choice(ctx.get("network_status")),
            ctx.get("condition_display"),
        ]
        return truncate_title(join_parts(parts))

    def overview(self, ctx: dict) -> str:
        parts = [
            ctx.get("brand"),
            ctx.get("model"),
            f"{ctx.get('storage_gb')}GB" if ctx.get("storage_gb") else "",
            ctx.get("colour"),
            display_choice(ctx.get("network_status")),
        ]
        text = join_parts(parts)
        return f"{text} handset." if text else super().overview(ctx)

    def faults(self, ctx: dict) -> str:
        return str(ctx.get("faults") or "").strip() or "None noted."


class StampGenerator(BaseGenerator):
    profile_key = "stamps"

    def title(self, ctx: dict) -> str:
        parts = [
            ctx.get("country"),
            ctx.get("year"),
            ctx.get("denomination"),
            ctx.get("topic_theme"),
            "stamp",
            ctx.get("primary_catalogue_ref"),
        ]
        return truncate_title(join_parts(parts) or super().title(ctx))

    def overview(self, ctx: dict) -> str:
        parts = [
            ctx.get("country"),
            ctx.get("year"),
            ctx.get("denomination"),
            ctx.get("topic_theme"),
            "stamp",
            ctx.get("primary_catalogue_ref"),
        ]
        return join_parts(parts) or super().overview(ctx)


class CoinGenerator(BaseGenerator):
    profile_key = "coins"

    def title(self, ctx: dict) -> str:
        cert = ctx.get("cert_no")
        parts = [
            ctx.get("country"),
            ctx.get("year"),
            ctx.get("denomination"),
            ctx.get("ruler_or_reign"),
            "coin",
            ctx.get("grade"),
            f"Cert {cert}" if cert else "",
        ]
        return truncate_title(join_parts(parts) or super().title(ctx))

    def overview(self, ctx: dict) -> str:
        parts = [
            ctx.get("country"),
            ctx.get("year"),
            ctx.get("denomination"),
            ctx.get("ruler_or_reign"),
            "coin",
        ]
        return join_parts(parts) or super().overview(ctx)


class GoldGenerator(BaseGenerator):
    profile_key = "gold"

    def title(self, ctx: dict) -> str:
        purity = fineness_or_karat(ctx)
        parts = [
            f"{ctx.get('weight_g')}g" if ctx.get("weight_g") else "",
            display_choice(ctx.get("metal")),
            display_choice(ctx.get("form")),
            purity,
        ]
        return truncate_title(join_parts(parts) or super().title(ctx))

    def overview(self, ctx: dict) -> str:
        parts = [
            f"{ctx.get('weight_g')}g" if ctx.get("weight_g") else "",
            display_choice(ctx.get("metal")),
            display_choice(ctx.get("form")),
            fineness_or_karat(ctx),
        ]
        return join_parts(parts) or super().overview(ctx)


GENERATORS: dict[str, ListingGenerator] = {
    "phones": PhoneGenerator(),
    "stamps": StampGenerator(),
    "coins": CoinGenerator(),
    "gold": GoldGenerator(),
    "generic": BaseGenerator(),
}


def generator_for(item) -> ListingGenerator:
    profile_key = item.category.profile_key if item.category else ""
    return GENERATORS.get(profile_key or "generic", GENERATORS["generic"])


def generated_timestamp() -> str:
    return timezone.now().isoformat()


def generated_meta(template_key: str) -> dict:
    return {
        "template_key": template_key,
        "version": 1,
        "generated_at": generated_timestamp(),
    }


def render_title(item) -> str:
    ctx = safe_context(item)
    return generator_for(item).title(ctx)


def render_description(item, *, specifics, boilerplate_html="", include_sku_footer=False) -> str:
    ctx = safe_context(item)
    sku_footer = item.sku if include_sku_footer else ""
    return generator_for(item).description_html(
        ctx,
        specifics=specifics,
        boilerplate_html=boilerplate_html,
        sku_footer=sku_footer,
    )


def heading(text: str) -> str:
    return f"<h2>{escape(text)}</h2>"


def paragraph(text: str, *, raw: bool = False) -> str:
    content = text if raw else escape(str(text))
    return f"<p>{content}</p>"


def specifics_table(specifics) -> str:
    rows = []
    for row in specifics or []:
        name = str(row.get("name") or "").strip()
        value = str(row.get("value") or "").strip()
        if not name or not value:
            continue
        rows.append(
            f"<tr><th>{escape(name)}</th><td>{escape(value)}</td></tr>"
        )
    if not rows:
        return ""
    return "<h2>Item specifics</h2>\n<table><tbody>" + "".join(rows) + "</tbody></table>"


def join_parts(parts) -> str:
    return collapse_whitespace(" ".join(str(part).strip() for part in parts if part not in (None, "")))


def truncate_title(value: str) -> str:
    text = collapse_whitespace(value)
    if len(text) <= EBAY_TITLE_MAX:
        return text
    cut = text[:EBAY_TITLE_MAX].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0].rstrip(" -")
    return cut or text[:EBAY_TITLE_MAX]


def collapse_whitespace(value: str) -> str:
    return " ".join(str(value or "").split())


def display_choice(value) -> str:
    return str(value or "").replace("_", " ").strip()


def fineness_or_karat(ctx: dict) -> str:
    if ctx.get("fineness"):
        return f"{ctx['fineness']} fine"
    if ctx.get("karat"):
        return f"{ctx['karat']}ct"
    return ""
