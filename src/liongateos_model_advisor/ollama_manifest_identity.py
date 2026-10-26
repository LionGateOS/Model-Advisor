"""Read-only discovery of exact local Ollama manifest identities."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

_DIGEST = re.compile(r"^sha256:([0-9a-f]{64})$")
_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9._-]+$")
_MODEL_LAYER = "application/vnd.ollama.image.model"


def _is_safe_component(part: str) -> bool:
    """Accept a safe path component, rejecting literal ``.`` and ``..``.

    Ordinary dotted names such as ``model.v2`` or ``model..v2`` stay valid;
    only whole components made only of one or two dots are traversal.
    """
    return part not in (".", "..") and _SAFE_COMPONENT.fullmatch(part) is not None


def _model_path_parts(model_name: str) -> tuple[str, ...] | None:
    """Return safe registration path components, not a guessed upstream ID."""
    name = model_name.strip()
    if not name or "\\" in name or "\x00" in name:
        return None

    slash = name.rfind("/")
    colon = name.rfind(":")
    if colon > slash:
        base, tag = name[:colon], name[colon + 1:]
    else:
        base, tag = name, "latest"

    if not base or not tag:
        return None

    parts = base.split("/")
    if len(parts) == 1:
        parts.insert(0, "library")

    if any(not _is_safe_component(part) for part in (*parts, tag)):
        return None

    return (*parts, tag)


def _model_layer_is_present(models_root: Path, manifest: object) -> bool:
    if not isinstance(manifest, dict):
        return False

    layers = manifest.get("layers")
    if not isinstance(layers, list):
        return False

    model_layers = [
        layer for layer in layers
        if isinstance(layer, dict) and layer.get("mediaType") == _MODEL_LAYER
    ]
    if len(model_layers) != 1:
        return False

    layer = model_layers[0]
    digest = layer.get("digest")
    size = layer.get("size")
    match = _DIGEST.fullmatch(digest) if isinstance(digest, str) else None
    if match is None or isinstance(size, bool) or not isinstance(size, int) or size < 0:
        return False

    blob = models_root / "blobs" / ("sha256-" + match.group(1))
    try:
        return blob.is_file() and blob.stat().st_size == size
    except OSError:
        return False


def _models_roots() -> tuple[Path, ...]:
    roots: list[Path] = []
    configured = os.environ.get("OLLAMA_MODELS")
    if configured:
        roots.append(Path(configured).expanduser())

    roots.extend((
        Path("/usr/share/ollama/.ollama/models"),
        Path("/var/lib/ollama/.ollama/models"),
        Path.home() / ".ollama" / "models",
    ))

    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key not in seen:
            unique.append(root)
            seen.add(key)
    return tuple(unique)


def discover_registry_identity(
    model_name: str,
    *,
    models_roots: tuple[Path, ...] | None = None,
) -> str | None:
    """Return a unique manifest identity only when its model blob verifies.

    The returned value is a registry-relative manifest path. Local filesystem
    paths are never returned. Missing, invalid, or ambiguous matches stay
    unknown; this function never downloads or starts a model.
    """
    parts = _model_path_parts(model_name)
    if parts is None:
        return None

    matches: set[str] = set()
    for root in models_roots if models_roots is not None else _models_roots():
        manifest_root = root / "manifests"
        if not manifest_root.is_dir():
            continue

        try:
            candidates = tuple(manifest_root.rglob(parts[-1]))
        except OSError:
            continue

        for candidate in candidates:
            try:
                relative_parts = candidate.relative_to(manifest_root).parts
            except ValueError:
                continue

            if len(relative_parts) < len(parts):
                continue
            if relative_parts[-len(parts):] != parts or not candidate.is_file():
                continue

            try:
                manifest = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, ValueError):
                continue

            if _model_layer_is_present(root, manifest):
                matches.add("/".join(relative_parts))

    if len(matches) != 1:
        return None
    return next(iter(matches))
