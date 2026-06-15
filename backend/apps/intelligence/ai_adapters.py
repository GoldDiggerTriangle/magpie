from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AIResearchUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class PreparedImage:
    photo_id: str
    mime_type: str
    data: bytes
    exif_stripped: bool


@dataclass(frozen=True)
class AISuggestionCandidate:
    field: str
    value: object
    confidence_band: str
    evidence: str
    source_basis: str = ""
    candidate_only: bool = False


@dataclass(frozen=True)
class AIReferenceQuery:
    label: str
    query: str
    source_basis: str = ""


@dataclass(frozen=True)
class AIResearchResult:
    suggestions: list[AISuggestionCandidate] = field(default_factory=list)
    search_terms: list[str] = field(default_factory=list)
    reference_queries: list[AIReferenceQuery] = field(default_factory=list)
    request_metadata: dict = field(default_factory=dict)
    response_metadata: dict = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: Decimal = Decimal("0.000000")


class AiResearchAdapter(Protocol):
    provider: str
    model_id: str

    def identify(self, *, item_context: dict, images: list[PreparedImage]) -> AIResearchResult:
        raise NotImplementedError

    def price_assist(self, *, item_context: dict) -> AIResearchResult:
        raise NotImplementedError


class FakeAiResearchAdapter:
    provider = "fake"
    model_id = "fake-ai-research-v1"

    def identify(self, *, item_context: dict, images: list[PreparedImage]) -> AIResearchResult:
        title = item_context.get("title") or "Australia 1932 Harbour Bridge 2d"
        return AIResearchResult(
            suggestions=[
                AISuggestionCandidate(
                    field="title",
                    value=f"AI identified {title}",
                    confidence_band="medium",
                    evidence="Fake adapter recognised the item title from fixture context.",
                    source_basis="photo + existing title",
                ),
                AISuggestionCandidate(
                    field="attributes.country",
                    value="Australia",
                    confidence_band="high",
                    evidence="Country text appears in the fixture response.",
                    source_basis="photo text",
                ),
                AISuggestionCandidate(
                    field="attributes.year",
                    value="1932",
                    confidence_band="medium",
                    evidence="Year appears in the fixture response.",
                    source_basis="photo text",
                ),
                AISuggestionCandidate(
                    field="ai_candidate.catalogue_id",
                    value="candidate-only reference",
                    confidence_band="candidate",
                    evidence="Catalogue reference is a lead only, not authoritative.",
                    source_basis="reference lookup lead",
                    candidate_only=True,
                ),
            ],
            search_terms=["Australia 1932 Harbour Bridge 2d", "Australia bridge stamp 2d"],
            reference_queries=[
                AIReferenceQuery(
                    label="Reference image search",
                    query="Australia 1932 Harbour Bridge 2d stamp reference image",
                    source_basis="fake adapter reference lead",
                )
            ],
            request_metadata={"image_count": len(images), "schema": "magpie_ai_research_v1"},
            response_metadata={"fake": True},
            input_tokens=100,
            output_tokens=80,
            estimated_cost_usd=Decimal("0.000100"),
        )

    def price_assist(self, *, item_context: dict) -> AIResearchResult:
        base = " ".join(
            str(value)
            for value in [
                item_context.get("title"),
                item_context.get("attributes", {}).get("country"),
                item_context.get("attributes", {}).get("year"),
                item_context.get("attributes", {}).get("denomination"),
            ]
            if value
        ) or "collectible item"
        return AIResearchResult(
            search_terms=[
                base,
                f"{base} sold completed",
                f"{base} exact variety",
            ],
            reference_queries=[
                AIReferenceQuery(
                    label="Reference image search",
                    query=f"{base} reference image",
                    source_basis="fake adapter price-assist lead",
                )
            ],
            request_metadata={"schema": "magpie_price_assist_v1"},
            response_metadata={"fake": True},
            input_tokens=80,
            output_tokens=60,
            estimated_cost_usd=Decimal("0.000080"),
        )


class OpenAIAiResearchAdapter:
    provider = "openai"

    INPUT_RATE_PER_MILLION = Decimal("0.400000")
    OUTPUT_RATE_PER_MILLION = Decimal("1.600000")

    def __init__(self, *, api_key: str, model_id: str = "gpt-4.1-mini", timeout: int = 60):
        self.api_key = api_key
        self.model_id = model_id
        self.timeout = timeout

    def identify(self, *, item_context: dict, images: list[PreparedImage]) -> AIResearchResult:
        payload = self._base_payload(
            schema_name="magpie_ai_research_v1",
            schema=_identify_schema(),
            user_text=(
                "Identify the item from its photos and current Magpie context. "
                "Return factual field suggestions only. Do not return prices, value bands, "
                "valuations, acquisition cost, profit, authoritative grade, or authoritative catalogue IDs."
            ),
            item_context=item_context,
            images=images,
        )
        return self._request(payload)

    def price_assist(self, *, item_context: dict) -> AIResearchResult:
        payload = self._base_payload(
            schema_name="magpie_price_assist_v1",
            schema=_price_assist_schema(),
            user_text=(
                "Sharpen search terms for external evidence lookup. Return search phrases and reference "
                "lookup queries only. Never return price numbers, value bands, valuations, or estimates."
            ),
            item_context=item_context,
            images=[],
        )
        return self._request(payload)

    def _base_payload(
        self,
        *,
        schema_name: str,
        schema: dict,
        user_text: str,
        item_context: dict,
        images: list[PreparedImage],
    ) -> dict:
        content = [
            {
                "type": "input_text",
                "text": (
                    f"{user_text}\n\n"
                    f"Magpie item context JSON:\n{json.dumps(item_context, ensure_ascii=False)}"
                ),
            }
        ]
        for image in images:
            encoded = base64.b64encode(image.data).decode("ascii")
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:{image.mime_type};base64,{encoded}",
                }
            )
        return {
            "model": self.model_id,
            "store": False,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You are a careful collectibles identification assistant for Magpie. "
                                "You assist identification and search-term sharpening only. "
                                "Never output prices, value bands, valuations, costs, profit, authoritative grades, "
                                "or authoritative catalogue IDs."
                            ),
                        }
                    ],
                },
                {"role": "user", "content": content},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                }
            },
            "max_output_tokens": 1200,
        }

    def _request(self, payload: dict) -> AIResearchResult:
        request = Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")[:500]
            raise AIResearchUnavailable(f"OpenAI request failed with status {exc.code}: {detail}") from exc
        except URLError as exc:
            raise AIResearchUnavailable(f"OpenAI request failed: {exc.reason}") from exc

        try:
            body = json.loads(raw)
            parsed = json.loads(_extract_response_text(body))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AIResearchUnavailable("OpenAI response could not be parsed as Magpie research JSON.") from exc

        usage = body.get("usage") or {}
        input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
        estimated_cost = _estimate_cost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_rate=self.INPUT_RATE_PER_MILLION,
            output_rate=self.OUTPUT_RATE_PER_MILLION,
        )
        return _result_from_payload(
            parsed,
            request_metadata={
                "schema": payload["text"]["format"]["name"],
                "image_count": sum(
                    1
                    for entry in payload["input"][1]["content"]
                    if entry.get("type") == "input_image"
                ),
            },
            response_metadata={
                "response_id": body.get("id", ""),
                "usage_present": bool(usage),
            },
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost,
        )


def _extract_response_text(body: dict) -> str:
    if body.get("output_text"):
        return str(body["output_text"])
    for output in body.get("output") or []:
        for content in output.get("content") or []:
            if "text" in content:
                return str(content["text"])
    raise KeyError("No response text")


def _result_from_payload(
    payload: dict,
    *,
    request_metadata: dict,
    response_metadata: dict,
    input_tokens: int,
    output_tokens: int,
    estimated_cost_usd: Decimal,
) -> AIResearchResult:
    suggestions = [
        AISuggestionCandidate(
            field=str(entry.get("field", "")),
            value=entry.get("value"),
            confidence_band=str(entry.get("confidence_band", "candidate")),
            evidence=str(entry.get("evidence", "")),
            source_basis=str(entry.get("source_basis", "")),
            candidate_only=bool(entry.get("candidate_only", False)),
        )
        for entry in payload.get("suggestions") or []
        if isinstance(entry, dict)
    ]
    reference_queries = [
        AIReferenceQuery(
            label=str(entry.get("label", "Reference lookup")),
            query=str(entry.get("query", "")),
            source_basis=str(entry.get("source_basis", "")),
        )
        for entry in payload.get("reference_queries") or []
        if isinstance(entry, dict)
    ]
    return AIResearchResult(
        suggestions=suggestions,
        search_terms=[str(term) for term in payload.get("search_terms") or []],
        reference_queries=reference_queries,
        request_metadata=request_metadata,
        response_metadata=response_metadata,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimated_cost_usd,
    )


def _estimate_cost(
    *,
    input_tokens: int,
    output_tokens: int,
    input_rate: Decimal,
    output_rate: Decimal,
) -> Decimal:
    cost = (
        Decimal(input_tokens) * input_rate / Decimal("1000000")
        + Decimal(output_tokens) * output_rate / Decimal("1000000")
    )
    return cost.quantize(Decimal("0.000001"))


def _identify_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "suggestions": {
                "type": "array",
                "items": _suggestion_schema(),
            },
            "search_terms": {"type": "array", "items": {"type": "string"}},
            "reference_queries": {
                "type": "array",
                "items": _reference_query_schema(),
            },
        },
        "required": ["suggestions", "search_terms", "reference_queries"],
    }


def _price_assist_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "suggestions": {
                "type": "array",
                "items": _suggestion_schema(),
            },
            "search_terms": {"type": "array", "items": {"type": "string"}},
            "reference_queries": {
                "type": "array",
                "items": _reference_query_schema(),
            },
        },
        "required": ["suggestions", "search_terms", "reference_queries"],
    }


def _suggestion_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "field": {"type": "string"},
            "value": {"type": "string"},
            "confidence_band": {
                "type": "string",
                "enum": ["high", "medium", "low", "candidate"],
            },
            "evidence": {"type": "string"},
            "source_basis": {"type": "string"},
            "candidate_only": {"type": "boolean"},
        },
        "required": [
            "field",
            "value",
            "confidence_band",
            "evidence",
            "source_basis",
            "candidate_only",
        ],
    }


def _reference_query_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "label": {"type": "string"},
            "query": {"type": "string"},
            "source_basis": {"type": "string"},
        },
        "required": ["label", "query", "source_basis"],
    }
