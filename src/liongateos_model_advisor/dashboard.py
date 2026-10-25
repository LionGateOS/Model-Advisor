"""Read-only data assembly for the LionGateOS Model Advisor dashboard."""

from __future__ import annotations

from typing import Any, Sequence

from .capability_discovery import collect_runtime_capability_evidence
from .compatibility import assess_compatibility
from .context_guidance import compare_context_options
from .discovery import discover_hardware
from .model_discovery import discover_ollama_models
from .catalog_discovery import discover_huggingface_models
from .openrouter_discovery import discover_openrouter_models
from .qualification import qualification_capabilities
from .runtime_discovery import discover_runtimes


def collect_dashboard_data(
    runtime_paths: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Collect existing public profiles for dashboard presentation.

    This function does not implement hardware/runtime discovery or
    compatibility policy itself. Existing Model Advisor domain logic remains
    authoritative.
    """
    paths = list(runtime_paths or ())

    hardware = discover_hardware()
    runtimes = discover_runtimes(paths)
    evidence = collect_runtime_capability_evidence(runtimes, paths)
    compatibility = assess_compatibility(
        hardware,
        runtimes,
        evidence,
    )
    models = discover_ollama_models()
    huggingface_models = discover_huggingface_models()
    openrouter_models = discover_openrouter_models()

    context_comparisons = []
    models_by_id = {model.model_id: model for model in models.models}
    for artifact in models.artifacts:
        # Only a concrete locally stored artifact is eligible.  In
        # particular, do not turn remote registrations or hosted offerings
        # into local memory comparisons.
        if artifact.location != "local":
            continue

        model = models_by_id.get(artifact.model_id)
        if model is None:
            continue

        context_comparisons.append(
            {
                "model_id": model.model_id,
                "artifact_id": artifact.artifact_id,
                "options": [
                    option.to_dict()
                    for option in compare_context_options(
                        model,
                        artifact,
                        hardware,
                        key_bytes_per_element=2.0,
                        value_bytes_per_element=2.0,
                    )
                ],
            }
        )

    return {
        "hardware": hardware.to_dict(),
        "runtimes": runtimes.to_dict(),
        "compatibility": compatibility.to_dict(),
        "models": models.to_dict(),
        "huggingface_models": huggingface_models.to_dict(),
        "openrouter_models": openrouter_models.to_dict(),
        "context_comparisons": context_comparisons,
        "qualification_capabilities": qualification_capabilities(),
    }
