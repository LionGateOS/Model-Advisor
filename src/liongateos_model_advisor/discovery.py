"""Read-only Linux hardware discovery for LionGateOS Model Advisor."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .hardware_profile import CPU, GPU, HardwareProfile, Memory, OperatingSystem


def _run(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout


def _read_os_release(path: Path = Path("/etc/os-release")) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values

    for line in lines:
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip('"')
    return values


def _discover_cpu() -> CPU:
    output = _run(["lscpu", "-J"])
    if not output:
        return CPU()

    try:
        entries = json.loads(output)["lscpu"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return CPU()

    fields = {
        entry.get("field", "").rstrip(":"): entry.get("data")
        for entry in entries
        if isinstance(entry, dict)
    }

    logical = _as_int(fields.get("CPU(s)"))
    cores_per_socket = _as_int(fields.get("Core(s) per socket"))
    sockets = _as_int(fields.get("Socket(s)"))
    physical = (
        cores_per_socket * sockets
        if cores_per_socket is not None and sockets is not None
        else None
    )

    return CPU(
        vendor=fields.get("Vendor ID"),
        model=fields.get("Model name"),
        architecture=fields.get("Architecture"),
        physical_cores=physical,
        logical_cpus=logical,
    )


def _discover_memory() -> Memory:
    try:
        lines = Path("/proc/meminfo").read_text(encoding="utf-8").splitlines()
    except OSError:
        return Memory()

    values: dict[str, int] = {}

    for line in lines:
        if ":" not in line:
            continue

        key, rest = line.split(":", 1)

        if key not in {"MemTotal", "MemAvailable"}:
            continue

        parts = rest.split()

        if not parts:
            continue

        try:
            values[key] = int(parts[0]) * 1024
        except ValueError:
            continue

    return Memory(
        total_bytes=values.get("MemTotal"),
        available_bytes=values.get("MemAvailable"),
    )


def _discover_pci_gpus() -> list[GPU]:
    output = _run(["lspci", "-Dnnmm"])
    if not output:
        return []

    gpus: list[GPU] = []
    pattern = re.compile(
        r'^(?P<pci>\S+)\s+"(?P<class>[^"]+)"\s+'
        r'"(?P<vendor>[^"]+)"\s+"(?P<device>[^"]+)"'
    )

    for line in output.splitlines():
        match = pattern.match(line)
        if not match:
            continue

        device_class = match.group("class")
        if not any(
            marker in device_class
            for marker in ("VGA compatible controller", "3D controller", "Display controller")
        ):
            continue

        vendor_text = match.group("vendor")
        device_text = match.group("device")

        vendor_id = _extract_bracket_id(vendor_text)
        device_id = _extract_bracket_id(device_text)

        gpus.append(
            GPU(
                vendor=_normalize_vendor(vendor_text),
                model=_strip_ids(device_text),
                pci_address=_normalize_pci_address(match.group("pci")),
                vendor_id=vendor_id,
                device_id=device_id,
                detection_sources=("lspci",),
            )
        )

    return gpus


def _enrich_nvidia(gpus: list[GPU]) -> list[GPU]:
    output = _run(
        [
            "nvidia-smi",
            "--query-gpu=name,pci.bus_id,memory.total,memory.free,driver_version",
            "--format=csv,noheader,nounits",
        ]
    )
    if not output:
        return gpus

    enriched = list(gpus)

    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 5:
            continue

        name, pci, memory_mib, free_memory_mib, driver = parts
        pci = _normalize_pci_address(pci)

        for index, gpu in enumerate(enriched):
            if gpu.pci_address != pci:
                continue
            try:
                total_vram = int(memory_mib) * 1024 * 1024
            except ValueError:
                total_vram = None

            try:
                free_vram = int(free_memory_mib) * 1024 * 1024
            except ValueError:
                free_vram = None

            enriched[index] = GPU(
                vendor=gpu.vendor or "NVIDIA",
                model=name or gpu.model,
                pci_address=gpu.pci_address,
                vendor_id=gpu.vendor_id,
                device_id=gpu.device_id,
                total_vram_bytes=total_vram,
                free_vram_bytes=free_vram,
                driver_version=driver or None,
                detection_sources=tuple(
                    dict.fromkeys((*gpu.detection_sources, "nvidia-smi"))
                ),
            )
            break

    return enriched


def discover_hardware() -> HardwareProfile:
    os_release = _read_os_release()
    cpu = _discover_cpu()
    gpus = _enrich_nvidia(_discover_pci_gpus())

    return HardwareProfile(
        os=OperatingSystem(
            name=os_release.get("NAME"),
            version=os_release.get("VERSION"),
            identifier=os_release.get("ID"),
            architecture=cpu.architecture,
        ),
        cpu=cpu,
        memory=_discover_memory(),
        gpus=tuple(gpus),
    )



def _normalize_pci_address(value: str) -> str:
    """Normalize PCI addresses so different tools can describe the same device."""

    value = value.strip().lower()
    parts = value.split(":")

    if len(parts) == 2:
        domain = "0000"
        bus, slot_function = parts
    elif len(parts) == 3:
        domain, bus, slot_function = parts
    else:
        return value

    try:
        domain = f"{int(domain, 16):04x}"
        bus = f"{int(bus, 16):02x}"

        slot, function = slot_function.split(".", 1)
        slot = f"{int(slot, 16):02x}"
        function = f"{int(function, 16):x}"
    except (ValueError, TypeError):
        return value

    return f"{domain}:{bus}:{slot}.{function}"



def _as_int(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _extract_bracket_id(value: str) -> str | None:
    matches = re.findall(r"\[([0-9a-fA-F]{4})\]", value)
    return matches[-1].lower() if matches else None


def _strip_ids(value: str) -> str:
    return re.sub(r"\s*\[[0-9a-fA-F]{4}\]", "", value).strip()


def _normalize_vendor(value: str) -> str:
    lowered = value.lower()
    if "nvidia" in lowered:
        return "NVIDIA"
    if "advanced micro devices" in lowered or "amd/ati" in lowered:
        return "AMD"
    if "intel" in lowered:
        return "Intel"
    return _strip_ids(value)
