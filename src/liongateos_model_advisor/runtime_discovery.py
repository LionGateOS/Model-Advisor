"""Read-only local AI runtime discovery for LionGateOS Model Advisor."""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path

from .runtime_profile import Runtime, RuntimeProfile


def _run_version(executable: str) -> str | None:
    try:
        result = subprocess.run(
            [executable, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    output = "\n".join(
        part for part in (result.stdout.strip(), result.stderr.strip()) if part
    )
    return output or None


def _discover_ollama() -> Runtime:
    executable = shutil.which("ollama")
    if not executable:
        return Runtime(
            name="ollama",
            available=False,
            discovery_sources=("path",),
        )

    output = _run_version(executable)
    version = None
    if output:
        match = re.search(r"ollama version is\s+([^\s]+)", output, re.IGNORECASE)
        if match:
            version = match.group(1)

    return Runtime(
        name="ollama",
        available=True,
        version=version,
        executables=("ollama",),
        discovery_sources=("path",),
    )


def _discover_vllm() -> Runtime:
    executable = shutil.which("vllm")
    if not executable:
        return Runtime(
            name="vllm",
            available=False,
            discovery_sources=("path",),
        )

    output = _run_version(executable)
    version = None
    if output:
        for line in reversed(output.splitlines()):
            candidate = line.strip()
            if re.fullmatch(r"\d+(?:\.\d+)+(?:[A-Za-z0-9.+_-]*)?", candidate):
                version = candidate
                break

    return Runtime(
        name="vllm",
        available=True,
        version=version,
        executables=("vllm",),
        discovery_sources=("path",),
    )


def _find_llama_executables(
    custom_paths: Iterable[str | Path] = (),
) -> tuple[dict[str, str], tuple[str, ...]]:
    found: dict[str, str] = {}
    sources: list[str] = []

    for name in ("llama-cli", "llama-server"):
        executable = shutil.which(name)
        if executable:
            found[name] = executable
            if "path" not in sources:
                sources.append("path")

    for raw_path in custom_paths:
        path = Path(raw_path).expanduser()

        if path.is_file():
            candidates = [path]
        elif path.is_dir():
            candidates = [path / "llama-cli", path / "llama-server"]
        else:
            continue

        for candidate in candidates:
            if candidate.name not in ("llama-cli", "llama-server"):
                continue
            if candidate.is_file() and candidate.stat().st_mode & 0o111:
                found.setdefault(candidate.name, str(candidate))
                if "custom-path" not in sources:
                    sources.append("custom-path")

    return found, tuple(sources)


def _discover_llama_cpp(
    custom_paths: Iterable[str | Path] = (),
) -> Runtime:
    executables, sources = _find_llama_executables(custom_paths)

    if not executables:
        return Runtime(
            name="llama.cpp",
            available=False,
            discovery_sources=("path",),
        )

    preferred = executables.get("llama-cli") or executables.get("llama-server")
    output = _run_version(preferred) if preferred else None

    version = None
    build = None
    commit = None

    if output:
        match = re.search(
            r"version:\s+(\S+)\s+\(build\s+([^,\)]+),\s+commit\s+([^\)]+)\)",
            output,
            re.IGNORECASE,
        )
        if match:
            version = match.group(1)
            build = match.group(2).strip()
            commit = match.group(3).strip()

    return Runtime(
        name="llama.cpp",
        available=True,
        version=version,
        build=build,
        commit=commit,
        executables=tuple(sorted(executables)),
        discovery_sources=sources or ("custom-path",),
    )


def discover_runtimes(
    custom_paths: Iterable[str | Path] = (),
) -> RuntimeProfile:
    paths = tuple(custom_paths)

    return RuntimeProfile(
        runtimes=(
            _discover_ollama(),
            _discover_llama_cpp(paths),
            _discover_vllm(),
        )
    )
