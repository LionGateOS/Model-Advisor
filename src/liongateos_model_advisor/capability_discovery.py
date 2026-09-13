"""Read-only runtime capability evidence collection."""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path

from .compatibility import RuntimeCapabilityEvidence
from .runtime_discovery import _find_llama_executables
from .runtime_profile import RuntimeProfile


def _run_probe(command: list[str], timeout: int = 20) -> str | None:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    output = "\n".join(
        part for part in (result.stdout.strip(), result.stderr.strip()) if part
    )
    return output or None


def _vendor_from_model(model: str) -> str | None:
    lowered = model.lower()

    if "nvidia" in lowered:
        return "NVIDIA"
    if "amd" in lowered or "radeon" in lowered:
        return "AMD"
    if "intel" in lowered:
        return "Intel"
    if "apple" in lowered:
        return "Apple"

    return None


def probe_llama_cpp(
    custom_paths: Iterable[str | Path] = (),
) -> RuntimeCapabilityEvidence | None:
    executables, _ = _find_llama_executables(custom_paths)
    executable = executables.get("llama-cli") or executables.get("llama-server")

    if not executable:
        return None

    output = _run_probe([executable, "--list-devices"])
    if not output:
        return None

    backends: list[str] = []
    vendors: list[str] = []
    models: list[str] = []

    pattern = re.compile(
        r"^\s*(?P<backend>CUDA|ROCm|Vulkan|Metal)\d*:\s+"
        r"(?P<model>.+?)(?:\s+\([^)]*\))?\s*$",
        re.IGNORECASE,
    )

    for line in output.splitlines():
        match = pattern.match(line)
        if not match:
            continue

        backend = match.group("backend")
        model = match.group("model").strip()

        backends.append(backend)
        models.append(model)

        vendor = _vendor_from_model(model)
        if vendor:
            vendors.append(vendor)

    if not backends:
        return None

    normalized_backends = tuple(dict.fromkeys(item.upper() for item in backends))
    backend = normalized_backends[0] if len(normalized_backends) == 1 else "MULTIPLE"

    return RuntimeCapabilityEvidence(
        runtime_name="llama.cpp",
        gpu_backend=backend,
        gpu_vendors=tuple(dict.fromkeys(vendors)),
        gpu_models=tuple(dict.fromkeys(models)),
        source="llama-list-devices",
    )


def probe_vllm() -> RuntimeCapabilityEvidence | None:
    executable = shutil.which("vllm")
    if not executable:
        return None

    output = _run_probe([executable, "collect-env"], timeout=30)
    if not output:
        return None

    backend = None

    if re.search(r"Is CUDA available\s*:\s*True", output, re.IGNORECASE):
        backend = "CUDA"
    elif re.search(
        r"ROCM used to build PyTorch\s*:\s*(?!N/A|None|Could not collect)\S+",
        output,
        re.IGNORECASE,
    ):
        backend = "ROCm"

    if not backend:
        return None

    models: list[str] = []
    vendors: list[str] = []

    for match in re.finditer(
        r"GPU\s+\d+\s*:\s*(.+)",
        output,
        re.IGNORECASE,
    ):
        model = match.group(1).strip()
        models.append(model)

        vendor = _vendor_from_model(model)
        if vendor:
            vendors.append(vendor)

    return RuntimeCapabilityEvidence(
        runtime_name="vllm",
        gpu_backend=backend,
        gpu_vendors=tuple(dict.fromkeys(vendors)),
        gpu_models=tuple(dict.fromkeys(models)),
        source="vllm-collect-env",
    )


def probe_ollama() -> RuntimeCapabilityEvidence | None:
    executable = shutil.which("ollama")
    if not executable:
        return None

    output = _run_probe([executable, "ps"])
    if not output:
        return None

    if not re.search(r"\b\d+%\s+GPU\b", output, re.IGNORECASE):
        return None

    return RuntimeCapabilityEvidence(
        runtime_name="ollama",
        active_gpu_execution=True,
        source="ollama-ps",
    )


def collect_runtime_capability_evidence(
    runtimes: RuntimeProfile,
    custom_paths: Iterable[str | Path] = (),
) -> tuple[RuntimeCapabilityEvidence, ...]:
    available = {
        runtime.name.lower()
        for runtime in runtimes.runtimes
        if runtime.available
    }

    evidence: list[RuntimeCapabilityEvidence] = []

    if "ollama" in available:
        item = probe_ollama()
        if item:
            evidence.append(item)

    if "llama.cpp" in available:
        item = probe_llama_cpp(custom_paths)
        if item:
            evidence.append(item)

    if "vllm" in available:
        item = probe_vllm()
        if item:
            evidence.append(item)

    return tuple(evidence)
