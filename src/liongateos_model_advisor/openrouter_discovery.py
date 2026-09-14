"""Read-only OpenRouter model catalog discovery."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .model_profile import (
    MetadataEvidence,
    ModelIdentity,
    ModelOffering,
    ModelProfile,
    ModelSourceStatus,
)

URL = "https://openrouter.ai/api/v1/models"
SOURCE = "openrouter-api"
TIMEOUT = 10


def _request_models():
    req = Request(URL, headers={"Accept": "application/json"}, method="GET")
    with urlopen(req, timeout=TIMEOUT) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("invalid OpenRouter model response")
    return payload["data"]


def discover_openrouter_models(limit=20):
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ValueError("OpenRouter limit must be between 1 and 100")

    try:
        entries = _request_models()
    except (HTTPError, URLError, OSError):
        return ModelProfile(sources=(
            ModelSourceStatus(SOURCE, "unavailable", "api-unavailable"),
        ))
    except (json.JSONDecodeError, ValueError):
        return ModelProfile(sources=(
            ModelSourceStatus(SOURCE, "error", "invalid-model-list-response"),
        ))

    models = []
    offerings = []
    seen_models = set()
    seen_offerings = set()

    for entry in entries[:limit]:
        if not isinstance(entry, dict):
            continue
        provider_id = entry.get("id")
        if not isinstance(provider_id, str) or not provider_id.strip():
            continue
        provider_id = provider_id.strip()
        offering_id = f"openrouter:{provider_id}"
        if offering_id in seen_offerings:
            continue
        seen_offerings.add(offering_id)

        hf_id = entry.get("hugging_face_id")
        model_id = None
        evidence = []

        if isinstance(hf_id, str) and hf_id.strip():
            model_id = f"huggingface:{hf_id.strip()}"
            if model_id not in seen_models:
                seen_models.add(model_id)
                models.append(ModelIdentity(
                    model_id=model_id,
                    evidence=(MetadataEvidence(
                        field="model_id",
                        source=f"{SOURCE}:hugging_face_id",
                        kind="reported",
                    ),),
                ))
            evidence.append(MetadataEvidence(
                field="model_id",
                source=f"{SOURCE}:hugging_face_id",
                kind="reported",
            ))

        arch = entry.get("architecture")
        arch = arch if isinstance(arch, dict) else {}
        context = entry.get("context_length")
        if not isinstance(context, int) or isinstance(context, bool) or context <= 0:
            context = None

        offerings.append(ModelOffering(
            offering_id=offering_id,
            source=SOURCE,
            provider_model_id=provider_id,
            model_id=model_id,
            context_length=context,
            input_modalities=tuple(arch.get("input_modalities") or ()),
            output_modalities=tuple(arch.get("output_modalities") or ()),
            supported_parameters=tuple(entry.get("supported_parameters") or ()),
            evidence=tuple(evidence),
        ))

    return ModelProfile(
        models=tuple(models),
        offerings=tuple(offerings),
        sources=(ModelSourceStatus(SOURCE, "available"),),
    )
