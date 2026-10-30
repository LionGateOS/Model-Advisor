"""Read-only data assembly for the LionGateOS Model Advisor dashboard."""

from __future__ import annotations

from typing import Any, Sequence

from .capability_discovery import collect_runtime_capability_evidence
from .compatibility import assess_compatibility
from .context_guidance import compare_context_options
from .discovery import discover_hardware
from .model_discovery import discover_ollama_models
from .ollama_memory_observation import observe_loaded_models
from .catalog_discovery import discover_huggingface_models
from .openrouter_discovery import discover_openrouter_models
from .qualification import qualification_capabilities, qualify_gpu_model_from_evidence
from .recommendation import recommend_local_model
from .memory_calculation import estimate_model_memory
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
    memory_observations = observe_loaded_models()
    local_ids = {
        artifact.model_id
        for artifact in models.artifacts
        if artifact.location == "local"
    }
    memory_observations["models"] = [
        item for item in memory_observations["models"]
        if item["model_id"] in local_ids
    ]
    huggingface_models = discover_huggingface_models()
    openrouter_models = discover_openrouter_models()

    context_comparisons = []
    suitability_summaries = []
    workload_recommendations = []
    runtime_by_name = {
        item.runtime_name.lower(): item
        for item in compatibility.runtimes
    }
    capability_by_name = {
        item.runtime_name.lower(): item
        for item in evidence
        if hasattr(item, "runtime_name")
    }
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

        estimate = estimate_model_memory(
            model,
            artifact,
            context_length=4096,
            key_bytes_per_element=2.0,
            value_bytes_per_element=2.0,
        )

        runtime = runtime_by_name.get("ollama")
        if runtime is not None:
            qualification = qualify_gpu_model_from_evidence(
                estimate=estimate,
                hardware=hardware,
                runtime=runtime,
                capability=capability_by_name.get("ollama"),
            )
            status = qualification.status
            reasons = list(qualification.reasons)
            evidence_sources = list(qualification.evidence_sources)

            # A qualified result requires a complete memory estimate.
            # Missing memory evidence must never be hidden by a positive
            # partial-fit assessment.
            if status == "qualified" and estimate.estimated_total_bytes is None:
                status = "unknown"
                reasons.append("complete-model-memory-unknown")
        else:
            status = "unknown"
            reasons = ["ollama-runtime-compatibility-unknown"]
            evidence_sources = []

        if estimate.estimated_total_bytes is None:
            reasons.append("complete-model-memory-unknown")


        from .qualification import ModelQualification

        safe_qualification = ModelQualification(
            model_id=model.model_id,
            artifact_id=artifact.artifact_id,
            runtime_name="ollama",
            status=status,
            execution_path=(
                qualification.execution_path
                if runtime is not None and status == qualification.status
                else "unknown"
            ),
            reasons=tuple(dict.fromkeys(reasons)),
            evidence_sources=tuple(evidence_sources),
        )

        for workload in ("coding", "general_chat", "reasoning"):
            recommendation = recommend_local_model(
                model=model,
                artifact=artifact,
                qualification=safe_qualification,
                workload=workload,
            )
            workload_recommendations.append(recommendation.to_dict())

        suitability_summaries.append(
            {
                "model_id": model.model_id,
                "artifact_id": artifact.artifact_id,
                "status": status,
                "reasons": list(dict.fromkeys(reasons)),
                "evidence_sources": evidence_sources,
            }
        )

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
        "memory_observations": memory_observations,
        "huggingface_models": huggingface_models.to_dict(),
        "openrouter_models": openrouter_models.to_dict(),
        "context_comparisons": context_comparisons,
        "suitability_summaries": suitability_summaries,
        "workload_recommendations": workload_recommendations,
        "qualification_capabilities": qualification_capabilities(),
    }
