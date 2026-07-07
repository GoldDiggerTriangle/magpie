from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from io import BytesIO
import re

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from PIL import Image, ImageOps

from apps.audit.services import record as audit_record
from apps.catalog.profiles import get_schema
from apps.intelligence.models import (
    AICredential,
    AIReferenceLink,
    AIResearchCall,
    AIResearchSearchTerm,
    FieldSuggestion,
)
from apps.intelligence.ai_adapters import (
    AISuggestionCandidate,
    AIResearchResult,
    AIResearchUnavailable,
    AiResearchAdapter,
    OpenAIAiResearchAdapter,
    PreparedImage,
)
from apps.intelligence.identify_scope import build_identify_scope
from apps.intelligence.reference_sources import build_reference_source_links
from apps.inventory.models import InventoryItem
from integrations.storage import LocalFileStorageAdapter


DEFAULT_PROVIDER = AICredential.Provider.OPENAI
DEFAULT_MODEL = "gpt-5.4-mini"
PROHIBITED_FIELD_FRAGMENTS = {
    "price",
    "value",
    "valuation",
    "acquisition",
    "cost",
    "profit",
    "catalogue_id",
    "catalogue_number",
    "catalog_id",
    "grade",
}
ALLOWED_ITEM_FIELDS = {"title", "condition", "notes"}
PRICE_LIKE = re.compile(r"(\$|aud|usd|gbp|eur)\s*\d|\d+(\.\d{2})?\s*(aud|usd|gbp|eur)", re.I)
PRICE_WORDS = re.compile(r"\b(price|value|valuation|estimate|worth|band)\b", re.I)


def ai_status() -> dict:
    credential = active_credential()
    usage = current_month_usage()
    cap = credential.monthly_budget_cap_usd if credential else Decimal("5.00")
    enabled = bool(credential and usage < cap)
    disabled_reason = ""
    if credential is None:
        disabled_reason = "Connect an AI provider to enable the deep-dive."
    elif usage >= cap:
        disabled_reason = "Monthly AI budget cap has been reached."
    return {
        "configured": credential is not None,
        "provider": credential.provider if credential else DEFAULT_PROVIDER,
        "model_id": credential.model_id if credential else DEFAULT_MODEL,
        "monthly_budget_cap_usd": str(cap),
        "monthly_usage_usd": str(usage),
        "budget_remaining_usd": str(max(cap - usage, Decimal("0.00"))),
        "enabled": enabled,
        "disabled_reason": disabled_reason,
    }


def configure_ai_credential(*, api_key: str = "", provider: str, model_id: str, monthly_budget_cap_usd, actor=None) -> AICredential:
    provider = provider or DEFAULT_PROVIDER
    model_id = model_id or DEFAULT_MODEL
    cap = Decimal(str(monthly_budget_cap_usd or "5.00")).quantize(Decimal("0.01"))
    existing = AICredential.objects.filter(provider=provider).first()
    cleaned_key = api_key.strip() if api_key else ""
    if not cleaned_key and existing is None:
        raise AIResearchUnavailable("API key is required.")

    defaults = {
        "model_id": model_id,
        "monthly_budget_cap_usd": cap,
        "is_active": True,
        "last_error": "",
    }
    if cleaned_key:
        defaults["api_key"] = cleaned_key
    credential, _ = AICredential.objects.update_or_create(provider=provider, defaults=defaults)
    audit_record(
        actor=actor,
        action="ai.credential.configured",
        target_type="ai_credential",
        target_id=credential.id,
        payload={"provider": provider, "model_id": model_id, "monthly_budget_cap_usd": str(cap)},
    )
    return credential


def disconnect_ai_credential(*, actor=None) -> None:
    deleted = list(AICredential.objects.values_list("provider", flat=True))
    AICredential.objects.all().delete()
    audit_record(
        actor=actor,
        action="ai.credential.disconnected",
        target_type="ai_credential",
        payload={"providers": deleted},
    )


def active_credential() -> AICredential | None:
    return AICredential.objects.filter(is_active=True).order_by("provider").first()


def current_month_usage() -> Decimal:
    now = timezone.now()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = (
        AIResearchCall.objects.filter(
            created_at__gte=start,
            status=AIResearchCall.Status.SUCCESS,
        ).aggregate(total=Sum("estimated_cost_usd"))["total"]
        or Decimal("0.00")
    )
    return Decimal(total).quantize(Decimal("0.000001"))


def run_identify_for_item(
    item: InventoryItem,
    *,
    actor=None,
    adapter: AiResearchAdapter | None = None,
    storage=None,
) -> dict:
    return _run_ai_phase(
        item,
        phase=AIResearchCall.Phase.IDENTIFY,
        actor=actor,
        adapter=adapter,
        storage=storage,
    )


def run_price_assist_for_item(
    item: InventoryItem,
    *,
    actor=None,
    adapter: AiResearchAdapter | None = None,
) -> dict:
    return _run_ai_phase(
        item,
        phase=AIResearchCall.Phase.PRICE_ASSIST,
        actor=actor,
        adapter=adapter,
    )


@transaction.atomic
def _run_ai_phase(
    item: InventoryItem,
    *,
    phase: str,
    actor=None,
    adapter: AiResearchAdapter | None = None,
    storage=None,
) -> dict:
    credential = None if adapter is not None else active_credential()
    if adapter is None:
        if credential is None:
            raise AIResearchUnavailable("Connect an AI provider to enable the deep-dive.")
        if current_month_usage() >= credential.monthly_budget_cap_usd:
            _record_blocked(item, phase, credential, "Monthly AI budget cap has been reached.", actor)
            raise AIResearchUnavailable("Monthly AI budget cap has been reached.")
        adapter = _adapter_from_credential(credential)

    item_context = build_item_context(item)
    images = prepare_item_images_for_ai(item, storage=storage) if phase == AIResearchCall.Phase.IDENTIFY else []
    try:
        result = (
            adapter.identify(item_context=item_context, images=images)
            if phase == AIResearchCall.Phase.IDENTIFY
            else adapter.price_assist(item_context=item_context)
        )
    except AIResearchUnavailable as exc:
        _record_failed(item, phase, adapter, str(exc), actor)
        if credential is not None:
            credential.last_error = str(exc)
            credential.save(update_fields=["last_error", "updated_at"])
        raise

    call = AIResearchCall.objects.create(
        item=item,
        phase=phase,
        status=AIResearchCall.Status.SUCCESS,
        provider=adapter.provider,
        model_id=adapter.model_id,
        image_count=len(images),
        exif_stripped=all(image.exif_stripped for image in images) if images else True,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        estimated_cost_usd=result.estimated_cost_usd,
        request_metadata=result.request_metadata,
        response_metadata=result.response_metadata,
    )
    suggestions = stage_ai_suggestions(
        item,
        result,
        call=call,
        ensure_copywriting_title=phase == AIResearchCall.Phase.IDENTIFY,
    )
    terms = stage_ai_search_terms(item, result, call=call)
    links = stage_reference_links(item, result, call=call)
    call.suggestions_created = len(suggestions)
    call.search_terms_created = len(terms)
    call.reference_links_created = len(links)
    call.save(
        update_fields=[
            "suggestions_created",
            "search_terms_created",
            "reference_links_created",
            "updated_at",
        ]
    )
    audit_record(
        actor=actor,
        action=f"ai.research.{phase}.completed",
        target_type="inventory_item",
        target_id=item.id,
        payload={
            "provider": adapter.provider,
            "model_id": adapter.model_id,
            "call_id": str(call.id),
            "suggestions_created": len(suggestions),
            "search_terms_created": len(terms),
            "reference_links_created": len(links),
            "image_count": len(images),
            "estimated_cost_usd": str(result.estimated_cost_usd),
        },
    )
    return {
        "call": call,
        "suggestions": suggestions,
        "search_terms": terms,
        "reference_links": links,
    }


def _adapter_from_credential(credential: AICredential) -> AiResearchAdapter:
    if credential.provider == AICredential.Provider.OPENAI:
        return OpenAIAiResearchAdapter(api_key=credential.api_key, model_id=credential.model_id)
    raise AIResearchUnavailable(f"AI provider is not supported: {credential.provider}")


def _record_blocked(item, phase: str, credential: AICredential, reason: str, actor) -> None:
    call = AIResearchCall.objects.create(
        item=item,
        phase=phase,
        status=AIResearchCall.Status.BLOCKED,
        provider=credential.provider,
        model_id=credential.model_id,
        error=reason,
    )
    audit_record(
        actor=actor,
        action=f"ai.research.{phase}.blocked",
        target_type="inventory_item",
        target_id=item.id,
        payload={"provider": credential.provider, "model_id": credential.model_id, "call_id": str(call.id), "reason": reason},
    )


def _record_failed(item, phase: str, adapter: AiResearchAdapter, error: str, actor) -> None:
    call = AIResearchCall.objects.create(
        item=item,
        phase=phase,
        status=AIResearchCall.Status.FAILED,
        provider=adapter.provider,
        model_id=adapter.model_id,
        error=error,
    )
    audit_record(
        actor=actor,
        action=f"ai.research.{phase}.failed",
        target_type="inventory_item",
        target_id=item.id,
        payload={"provider": adapter.provider, "model_id": adapter.model_id, "call_id": str(call.id), "error": error},
    )


def build_item_context(item: InventoryItem) -> dict:
    category = item.category
    profile_key = category.profile_key if category else ""
    return {
        "id": str(item.id),
        "sku": item.sku,
        "title": item.title,
        "category": category.name if category else "",
        "profile_key": profile_key,
        "condition": item.condition,
        "attributes": item.attributes or {},
        "field_schema": get_schema(profile_key).fields(),
        "identify_scope": build_identify_scope(profile_key),
    }


def prepare_item_images_for_ai(item: InventoryItem, *, storage=None) -> list[PreparedImage]:
    storage = storage or LocalFileStorageAdapter()
    images = []
    for photo in item.photos.order_by("order_index", "created_at")[:4]:
        key = photo.processed_path or photo.original_path
        if not key:
            continue
        images.append(strip_exif_for_ai(storage.open(key), photo_id=str(photo.id)))
    return images


def strip_exif_for_ai(raw: bytes, *, photo_id: str) -> PreparedImage:
    image = Image.open(BytesIO(raw))
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")
    image.thumbnail((1600, 1600))
    output = BytesIO()
    image.save(output, format="JPEG", quality=88, optimize=True)
    return PreparedImage(
        photo_id=photo_id,
        mime_type="image/jpeg",
        data=output.getvalue(),
        exif_stripped=True,
    )


def stage_ai_suggestions(
    item: InventoryItem,
    result: AIResearchResult,
    *,
    call: AIResearchCall | None = None,
    ensure_copywriting_title: bool = False,
) -> list[FieldSuggestion]:
    suggestions = []
    candidates = ensure_copywriting_title_candidate(item, result) if ensure_copywriting_title else list(result.suggestions)
    for candidate in candidates:
        field, confidence = normalize_ai_field(candidate.field, candidate.confidence_band, candidate.candidate_only)
        if not field:
            continue
        suggestion = FieldSuggestion.objects.create(
            item=item,
            field=field,
            proposed_value=candidate.value,
            source=FieldSuggestion.Source.AI,
            confidence_band=confidence,
            evidence=clean_evidence(candidate.evidence, candidate.source_basis, call),
        )
        suggestions.append(suggestion)
    return suggestions


def ensure_copywriting_title_candidate(item: InventoryItem, result: AIResearchResult) -> list[AISuggestionCandidate]:
    candidates = list(result.suggestions)
    if any(str(candidate.field or "").strip().lower() == "title" for candidate in candidates):
        return candidates
    category = item.category
    profile_key = category.profile_key if category else ""
    identify_scope = build_identify_scope(profile_key)
    if "title" not in identify_scope.get("copywriting_drafts", []):
        return candidates
    fallback = next((str(term).strip() for term in result.search_terms if str(term).strip()), "")
    if not fallback:
        return candidates
    candidates.append(
        AISuggestionCandidate(
            field="title",
            value=fallback[:200],
            confidence_band=FieldSuggestion.ConfidenceBand.LOW,
            evidence=(
                "The AI response did not include a dedicated title draft, so Magpie staged the strongest "
                "AI search phrase as an editable title lead for human review."
            ),
            source_basis="AI search-term fallback",
        )
    )
    return candidates


def normalize_ai_field(field: str, confidence_band: str, candidate_only: bool) -> tuple[str, str] | tuple[None, None]:
    cleaned = str(field or "").strip()
    lower = cleaned.lower()
    if not cleaned:
        return None, None
    if lower in {"condition", "attributes.condition", "condition_observation", "ai_observation.condition"}:
        return "ai_observation.condition", FieldSuggestion.ConfidenceBand.CANDIDATE
    if lower in {"short_description", "description", "description_draft", "ai_candidate.short_description_draft"}:
        return "ai_candidate.short_description_draft", FieldSuggestion.ConfidenceBand.CANDIDATE
    if candidate_only or any(fragment in lower for fragment in {"catalogue", "catalog", "grade"}):
        safe_name = lower.replace("attributes.", "").replace("ai_candidate.", "").replace(" ", "_")
        return f"ai_candidate.{safe_name}", FieldSuggestion.ConfidenceBand.CANDIDATE
    if any(fragment in lower for fragment in PROHIBITED_FIELD_FRAGMENTS):
        return None, None
    if cleaned in ALLOWED_ITEM_FIELDS:
        return cleaned, normalize_confidence(confidence_band)
    if cleaned.startswith("attributes."):
        attribute_name = cleaned.split(".", 1)[1]
        if attribute_name and not any(fragment in attribute_name.lower() for fragment in PROHIBITED_FIELD_FRAGMENTS):
            return cleaned, normalize_confidence(confidence_band)
    return None, None


def normalize_confidence(value: str) -> str:
    allowed = {choice for choice, _ in FieldSuggestion.ConfidenceBand.choices}
    return value if value in allowed else FieldSuggestion.ConfidenceBand.CANDIDATE


def clean_evidence(evidence: str, source_basis: str, call: AIResearchCall | None) -> str:
    parts = [part for part in [source_basis.strip(), evidence.strip()] if part]
    if call is not None:
        parts.append(f"AI call {call.id}")
    return " | ".join(parts)[:2000]


def stage_ai_search_terms(
    item: InventoryItem,
    result: AIResearchResult,
    *,
    call: AIResearchCall | None = None,
) -> list[AIResearchSearchTerm]:
    staged = []
    seen = set()
    for term in result.search_terms:
        cleaned = normalize_search_term(term)
        if not cleaned or cleaned.lower() in seen:
            continue
        seen.add(cleaned.lower())
        staged.append(
            AIResearchSearchTerm.objects.create(
                item=item,
                phrase=cleaned,
                source_basis="AI search-term sharpening",
                created_by_call=call,
            )
        )
    return staged


def normalize_search_term(term: str) -> str:
    cleaned = " ".join(str(term or "").split())[:240]
    if not cleaned:
        return ""
    if PRICE_LIKE.search(cleaned) or (PRICE_WORDS.search(cleaned) and re.search(r"\d", cleaned)):
        return ""
    return cleaned


def latest_ai_search_query(item: InventoryItem) -> str:
    term = item.ai_search_terms.filter(is_active=True).order_by("-created_at").first()
    return term.phrase if term else ""


def stage_reference_links(
    item: InventoryItem,
    result: AIResearchResult,
    *,
    call: AIResearchCall | None = None,
) -> list[AIReferenceLink]:
    links = []
    for query in result.reference_queries:
        cleaned = normalize_search_term(query.query)
        if not cleaned:
            continue
        for source_link in build_reference_source_links(cleaned, label_prefix=query.label):
            links.append(
                AIReferenceLink.objects.create(
                    item=item,
                    label=source_link.label,
                    url=source_link.url,
                    source_basis=query.source_basis or "AI reference lookup",
                    created_by_call=call,
                )
            )
    return links
