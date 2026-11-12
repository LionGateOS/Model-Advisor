"""Read-only discovery of exact local Ollama manifest identities."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

_DIGEST = re.compile(r"^sha256:([0-9a-f]{64})$")
_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9._-]+$")
_MODEL_LAYER = "application/vnd.ollama.image.model"

_MANIFEST_MAX_BYTES = 1024 * 1024


@dataclass(frozen=True)
class ManifestLayerRecord:
    """One local manifest's identity claims, read-only.

    ``model_layer_digest`` is the digest *declared* by the local manifest
    file, not a recomputed blob hash. ``from_label`` is a pull/import label
    claim supplied by the manifest itself; it is never proof of upstream
    identity, and a malformed or private-path label is withheld entirely.
    """

    registry_identity: str
    model_layer_digest: str
    model_layer_size: int
    from_label: str | None = None
    from_label_well_formed: bool = True


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


def _read_capped(manifest_path: Path) -> bytes:
    """Read a manifest file with a strict size cap."""

    if not manifest_path.is_file():
        raise OSError("not a file")

    with manifest_path.open("rb") as handle:
        data = handle.read(_MANIFEST_MAX_BYTES + 1)

    if len(data) > _MANIFEST_MAX_BYTES:
        raise OSError("manifest exceeds size cap")
    return data


def collect_manifest_layer_records(
    models_root: Path,
    *,
    manifest_reader: Callable[[Path], bytes] | None = None,
) -> tuple[ManifestLayerRecord, ...]:
    """Collect per-registration manifest layer records, read-only.

    One record per local registration whose manifest declares a single
    model layer of the model media type whose blob exists locally with the
    declared size (stat metadata only; model blobs are never read or
    hashed here). The manifest-level ``from`` label, when present, is
    preserved as a claim: well-formed labels are kept, malformed or
    private-path labels are withheld. Unreadable, oversized, or malformed
    manifests are skipped, never guessed.
    """

    reader = manifest_reader or _read_capped
    manifest_root = models_root / "manifests"
    if not manifest_root.is_dir():
        return ()

    records: dict[str, ManifestLayerRecord] = {}
    try:
        candidates = sorted(manifest_root.rglob("*"))
    except OSError:
        return ()

    for candidate in candidates:
        if not candidate.is_file():
            continue

        try:
            relative_parts = candidate.relative_to(manifest_root).parts
        except ValueError:
            continue

        if any(not _is_safe_component(part) for part in relative_parts):
            continue

        identity = "/".join(relative_parts)

        try:
            data = reader(candidate)
        except (OSError, ValueError):
            continue
        if not isinstance(data, bytes):
            continue

        try:
            manifest = json.loads(data.decode("utf-8"))
        except (UnicodeError, ValueError):
            continue
        if not isinstance(manifest, dict):
            continue

        layers = manifest.get("layers")
        if not isinstance(layers, list):
            continue
        model_layers = [
            layer
            for layer in layers
            if isinstance(layer, dict)
            and layer.get("mediaType") == _MODEL_LAYER
        ]
        if len(model_layers) != 1:
            continue

        digest = model_layers[0].get("digest")
        size = model_layers[0].get("size")
        match = _DIGEST.fullmatch(digest) if isinstance(digest, str) else None
        if (
            match is None
            or isinstance(size, bool)
            or not isinstance(size, int)
            or size < 0
            or not _model_layer_is_present(models_root, manifest)
        ):
            continue

        from_label: str | None = None
        from_label_well_formed = True
        raw_from = manifest.get("from")
        if raw_from is not None:
            if (
                isinstance(raw_from, str)
                and raw_from.strip()
                and "\\" not in raw_from
                and not raw_from.strip().startswith(("/", "."))
                and all(
                    _is_safe_component(part)
                    for part in raw_from.strip().split("/")
                )
            ):
                from_label = raw_from.strip()
                from_label_well_formed = True
            else:
                from_label_well_formed = False

        records[identity] = ManifestLayerRecord(
            registry_identity=identity,
            model_layer_digest=match.group(0),
            model_layer_size=size,
            from_label=from_label,
            from_label_well_formed=from_label_well_formed,
        )

    return tuple(
        sorted(records.values(), key=lambda record: record.registry_identity)
    )
