"""Read-only, bounded Ollama loaded-model memory observations."""

from __future__ import annotations

from collections.abc import Mapping

from .model_discovery import _request_json


def observe_loaded_models() -> dict:
    """Observe already-loaded models without starting or changing them."""
    try:
        payload = _request_json("/api/ps")
    except (OSError, ValueError):
        return {"status": "unavailable", "models": []}

    if not isinstance(payload, Mapping):
        return {"status": "error", "models": []}

    entries = payload.get("models")
    if not isinstance(entries, list):
        return {"status": "error", "models": []}

    observations = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue

        name = entry.get("name") or entry.get("model")
        if not isinstance(name, str) or not name.strip():
            continue

        total = entry.get("size")
        gpu = entry.get("size_vram")

        if (
            isinstance(total, bool)
            or not isinstance(total, int)
            or total < 0
        ):
            total = None

        if (
            isinstance(gpu, bool)
            or not isinstance(gpu, int)
            or gpu < 0
        ):
            gpu = None

        observations.append({
            "model_id": "ollama:" + name.strip(),
            "loaded_bytes": total,
            "gpu_bytes": gpu,
        })

    return {"status": "available", "models": observations}
