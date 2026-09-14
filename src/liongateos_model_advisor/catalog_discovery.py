"""Read-only remote model catalog discovery for LionGateOS Model Advisor."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .model_profile import (
    ModelArtifact,
    ModelIdentity,
    ModelProfile,
    ModelSourceStatus,
)
from .model_sources import profile_from_huggingface_model_info


HUGGINGFACE_MODELS_URL = "https://huggingface.co/api/models"
HUGGINGFACE_SOURCE = "huggingface-hub-api"
HUGGINGFACE_TIMEOUT_SECONDS = 10
HUGGINGFACE_DEFAULT_LIMIT = 20
HUGGINGFACE_MAX_LIMIT = 100
HUGGINGFACE_DEFAULT_DETAIL_LIMIT = 10
HUGGINGFACE_MAX_DETAIL_LOOKUPS = 20

_ALLOWED_SORTS = {
    "created_at",
    "downloads",
    "last_modified",
    "likes",
    "trending_score",
}


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = value.strip()
    return cleaned or None


def _build_huggingface_url(
    *,
    search: str | None,
    sort: str,
    limit: int,
    pipeline_tag: str | None,
    num_parameters: str | None,
) -> str:
    if sort not in _ALLOWED_SORTS:
        raise ValueError(f"unsupported Hugging Face sort: {sort}")

    if limit <= 0 or limit > HUGGINGFACE_MAX_LIMIT:
        raise ValueError(
            "Hugging Face result limit must be between "
            f"1 and {HUGGINGFACE_MAX_LIMIT}"
        )

    params: list[tuple[str, str]] = [
        ("sort", {"created_at": "createdAt", "last_modified": "lastModified", "trending_score": "trendingScore"}.get(sort, sort)),
        ("direction", "-1"),
        ("limit", str(limit)),
        ("full", "true"),
        ("cardData", "true"),
    ]

    cleaned_search = _clean_optional_text(search)
    cleaned_pipeline_tag = _clean_optional_text(pipeline_tag)
    cleaned_num_parameters = _clean_optional_text(num_parameters)

    if cleaned_search is not None:
        params.append(("search", cleaned_search))

    if cleaned_pipeline_tag is not None:
        params.append(("pipeline_tag", cleaned_pipeline_tag))

    if cleaned_num_parameters is not None:
        params.append(("num_parameters", cleaned_num_parameters))

    return f"{HUGGINGFACE_MODELS_URL}?{urlencode(params)}"


def _request_huggingface_model_list(
    *,
    search: str | None = None,
    sort: str = "trending_score",
    limit: int = HUGGINGFACE_DEFAULT_LIMIT,
    pipeline_tag: str | None = None,
    num_parameters: str | None = None,
) -> list[Mapping[str, Any]]:
    """Fetch one bounded public model listing from the Hugging Face Hub."""

    url = _build_huggingface_url(
        search=search,
        sort=sort,
        limit=limit,
        pipeline_tag=pipeline_tag,
        num_parameters=num_parameters,
    )

    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "LionGateOS-Model-Advisor/0.1",
        },
        method="GET",
    )

    with urlopen(
        request,
        timeout=HUGGINGFACE_TIMEOUT_SECONDS,
    ) as response:
        decoded = json.load(response)

    if not isinstance(decoded, list):
        raise ValueError(
            "Hugging Face model-list response must be an array"
        )

    return [
        item
        for item in decoded
        if isinstance(item, Mapping)
    ]


def _request_huggingface_model_detail(
    repo_id: str,
) -> Mapping[str, Any]:
    """Fetch metadata for one public Hub model without downloading weights."""

    cleaned_repo_id = repo_id.strip()

    if not cleaned_repo_id:
        raise ValueError("Hugging Face repo id must not be empty")

    url = (
        HUGGINGFACE_MODELS_URL
        + "/"
        + quote(cleaned_repo_id, safe="/")
    )

    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "LionGateOS-Model-Advisor/0.1",
        },
        method="GET",
    )

    with urlopen(
        request,
        timeout=HUGGINGFACE_TIMEOUT_SECONDS,
    ) as response:
        decoded = json.load(response)

    if not isinstance(decoded, Mapping):
        raise ValueError(
            "Hugging Face model-detail response must be an object"
        )

    return decoded


def discover_huggingface_models(
    *,
    search: str | None = None,
    sort: str = "trending_score",
    limit: int = HUGGINGFACE_DEFAULT_LIMIT,
    pipeline_tag: str | None = None,
    num_parameters: str | None = None,
    detail_limit: int = HUGGINGFACE_DEFAULT_DETAIL_LIMIT,
) -> ModelProfile:
    """Discover public Hub models with bounded optional detail enrichment."""

    if (
        detail_limit < 0
        or detail_limit > HUGGINGFACE_MAX_DETAIL_LOOKUPS
    ):
        raise ValueError(
            "Hugging Face detail limit must be between 0 and "
            f"{HUGGINGFACE_MAX_DETAIL_LOOKUPS}"
        )

    try:
        entries = _request_huggingface_model_list(
            search=search,
            sort=sort,
            limit=limit,
            pipeline_tag=pipeline_tag,
            num_parameters=num_parameters,
        )
    except (HTTPError, URLError, OSError):
        return ModelProfile(
            sources=(
                ModelSourceStatus(
                    source=HUGGINGFACE_SOURCE,
                    status="unavailable",
                    reason="api-unavailable",
                ),
            ),
        )
    except (json.JSONDecodeError, ValueError):
        return ModelProfile(
            sources=(
                ModelSourceStatus(
                    source=HUGGINGFACE_SOURCE,
                    status="error",
                    reason="invalid-model-list-response",
                ),
            ),
        )

    models: list[ModelIdentity] = []
    artifacts: list[ModelArtifact] = []
    seen_model_ids: set[str] = set()
    failed_entries = 0
    failed_details = 0
    detail_lookups = 0

    for entry in entries:
        repo_id_value = entry.get("id") or entry.get("modelId")
        repo_id = (
            repo_id_value.strip()
            if isinstance(repo_id_value, str)
            else None
        )

        if repo_id is not None:
            prospective_id = f"huggingface:{repo_id}"

            if prospective_id in seen_model_ids:
                continue

        payload: Mapping[str, Any] = entry

        if (
            repo_id is not None
            and detail_lookups < detail_limit
        ):
            detail_lookups += 1

            try:
                payload = _request_huggingface_model_detail(repo_id)
            except (
                HTTPError,
                URLError,
                OSError,
                json.JSONDecodeError,
                ValueError,
            ):
                failed_details += 1
                payload = entry

        try:
            normalized = profile_from_huggingface_model_info(payload)
        except ValueError:
            failed_entries += 1
            continue

        if not normalized.models:
            failed_entries += 1
            continue

        model = normalized.models[0]

        if model.model_id in seen_model_ids:
            continue

        seen_model_ids.add(model.model_id)
        models.extend(normalized.models)
        artifacts.extend(normalized.artifacts)

    if failed_entries and failed_details:
        status = "partial"
        reason = "one-or-more-model-records-and-details-unavailable"
    elif failed_entries:
        status = "partial"
        reason = "one-or-more-model-records-unusable"
    elif failed_details:
        status = "partial"
        reason = "one-or-more-model-details-unavailable"
    else:
        status = "available"
        reason = None

    return ModelProfile(
        models=tuple(models),
        artifacts=tuple(artifacts),
        sources=(
            ModelSourceStatus(
                source=HUGGINGFACE_SOURCE,
                status=status,
                reason=reason,
            ),
        ),
    )
