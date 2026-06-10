from apps.listing.context import safe_context


def build_specifics(item) -> list[dict]:
    return build_specifics_from_context(safe_context(item))


def build_specifics_from_context(ctx: dict) -> list[dict]:
    profile_key = ctx.get("profile_key") or "generic"
    if profile_key == "phones":
        return rows(
            [
                ("Brand", ctx.get("brand")),
                ("Model", ctx.get("model")),
                ("Storage Capacity", gb(ctx.get("storage_gb"))),
                ("RAM", gb(ctx.get("ram_gb"))),
                ("Colour", ctx.get("colour")),
                ("Network", display_choice(ctx.get("network_status"))),
                ("Condition", ctx.get("condition_display")),
            ]
        )
    if profile_key == "stamps":
        return rows(
            [
                ("Country", ctx.get("country")),
                ("Year of Issue", ctx.get("year")),
                ("Denomination", ctx.get("denomination")),
                ("Topic/Theme", ctx.get("topic_theme")),
                ("Catalogue Number(s)", catalogue_refs(ctx.get("catalogue_refs"))),
            ]
        )
    if profile_key == "coins":
        return rows(
            [
                ("Country", ctx.get("country")),
                ("Year", ctx.get("year")),
                ("Denomination", ctx.get("denomination")),
                ("Ruler/Reign", ctx.get("ruler_or_reign")),
                ("Grade", ctx.get("grade")),
                ("Certification Number", ctx.get("cert_no")),
                ("Composition", ctx.get("composition")),
                ("Weight", grams(ctx.get("weight_g"))),
            ]
        )
    if profile_key == "gold":
        return rows(
            [
                ("Metal", display_choice(ctx.get("metal"))),
                ("Form", display_choice(ctx.get("form"))),
                ("Weight", grams(ctx.get("weight_g"))),
                ("Fineness/Karat", fineness_or_karat(ctx)),
            ]
        )
    return rows([("Condition", ctx.get("condition_display"))])


def rows(entries) -> list[dict]:
    output = []
    for name, value in entries:
        text = str(value or "").strip()
        if text:
            output.append({"name": name, "value": text})
    return output


def gb(value) -> str:
    return f"{value} GB" if value not in (None, "") else ""


def grams(value) -> str:
    return f"{value} g" if value not in (None, "") else ""


def display_choice(value) -> str:
    return str(value or "").replace("_", " ").strip()


def fineness_or_karat(ctx: dict) -> str:
    if ctx.get("fineness"):
        return f"{ctx['fineness']} fine"
    if ctx.get("karat"):
        return f"{ctx['karat']}ct"
    return ""


def catalogue_refs(refs) -> str:
    if not isinstance(refs, list):
        return ""
    values = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        system = str(ref.get("system") or "").strip()
        number = str(ref.get("number") or "").strip()
        value = " ".join(part for part in [system, number] if part)
        if value:
            values.append(value)
    return ", ".join(values)
