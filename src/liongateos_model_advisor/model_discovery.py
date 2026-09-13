"""Read-only local model discovery for LionGateOS Model Advisor."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

from .model_profile import (
    ModelArtifact,
    ModelIdentity,
    ModelProfile,
    ModelSourceStatus,
)
from .model_sources import profile_from_ollama_show


OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_SOURCE = "ollama-local-api"
OLLAMA_TIMEOUT_SECONDS = 5
_ALLOWED_OLLAMA_PATHS = {
    "/api/tags",
    "/api/show",
}


def _request_json(
    path: str,
    payload: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Call one approved loopback Ollama metadata endpoint."""

    if path not in _ALLOWED_OLLAMA_PATHS:
        raise ValueError(f"unsupported Ollama metadata endpoint: {path}")

    body = None
    headers: dict[str, str] = {}

    if payload is not None:
        body = json.dumps(dict(payload)).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(
        OLLAMA_BASE_URL + path,
        data=body,
        headers=headers,
        method="POST" if body is not None else "GET",
    )

    # Do not allow environment proxy settings to redirect loopback metadata
    # discovery through an external proxy.
    opener = build_opener(ProxyHandler({}))

    with opener.open(
        request,
        timeout=OLLAMA_TIMEOUT_SECONDS,
    ) as response:
        decoded = json.load(response)

    if not isinstance(decoded, Mapping):
        raise ValueError("Ollama metadata response must be an object")

    return decoded


def _nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, int) and value >= 0:
        return value

    return None


def _clean_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    cleaned = value.strip()
    return cleaned or None


def discover_ollama_models() -> ModelProfile:
    """Discover locally registered Ollama models without running them."""

    try:
        payload = _request_json("/api/tags")
    except (OSError, URLError, ValueError):
        return ModelProfile(
            sources=(
                ModelSourceStatus(
                    source=OLLAMA_SOURCE,
                    status="unavailable",
                    reason="api-unavailable",
                ),
            ),
        )

    entries = payload.get("models")

    if not isinstance(entries, list):
        return ModelProfile(
            sources=(
                ModelSourceStatus(
                    source=OLLAMA_SOURCE,
                    status="error",
                    reason="invalid-model-list-response",
                ),
            ),
        )

    models: list[ModelIdentity] = []
    artifacts: list[ModelArtifact] = []
    seen_model_ids: set[str] = set()
    failed_model_details = 0

    for entry in entries:
        if not isinstance(entry, Mapping):
            continue

        name = (
            _clean_string(entry.get("name"))
            or _clean_string(entry.get("model"))
        )

        if name is None:
            continue

        model_id = f"ollama:{name}"

        if model_id in seen_model_ids:
            continue

        remote_backed = bool(
            _clean_string(entry.get("remote_host"))
            or _clean_string(entry.get("remote_model"))
        )
        artifact_location = "remote" if remote_backed else "local"

        # For remote-backed registrations, Ollama's list size describes the
        # small local registration/manifest rather than remote model weights.
        # Do not expose it as artifact model size.
        size_bytes = (
            None
            if remote_backed
            else _nonnegative_int(entry.get("size"))
        )

        try:
            shown = _request_json(
                "/api/show",
                {"model": name},
            )

            normalized = profile_from_ollama_show(
                name,
                shown,
                size_bytes=size_bytes,
                digest=_clean_string(entry.get("digest")),
                artifact_location=artifact_location,
            )
        except (OSError, URLError, ValueError):
            # One unreadable model must not invalidate the rest of the
            # local inventory, but the profile must record incompleteness.
            failed_model_details += 1
            continue

        seen_model_ids.add(model_id)
        models.extend(normalized.models)
        artifacts.extend(normalized.artifacts)

    source_status = ModelSourceStatus(
        source=OLLAMA_SOURCE,
        status="partial" if failed_model_details else "available",
        reason=(
            "one-or-more-model-details-unavailable"
            if failed_model_details
            else None
        ),
    )

    return ModelProfile(
        models=tuple(models),
        artifacts=tuple(artifacts),
        sources=(source_status,),
    )
