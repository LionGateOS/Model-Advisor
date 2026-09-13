"""Command-line interface for LionGateOS Model Advisor."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from .capability_discovery import collect_runtime_capability_evidence
from .compatibility import assess_compatibility
from .discovery import discover_hardware
from .manual import enter_hardware_manually
from .runtime_discovery import discover_runtimes


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="liongateos-model-advisor",
        description="Know what AI your machine should run.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("hardware", "runtimes", "compatibility"),
        default="hardware",
        help=(
            "inspect hardware (default), installed AI runtimes, "
            "or hardware/runtime compatibility"
        ),
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="enter hardware information manually instead of auto-detecting it",
    )
    parser.add_argument(
        "--runtime-path",
        action="append",
        default=[],
        metavar="PATH",
        help=(
            "additional directory or executable to inspect for llama.cpp; "
            "may be repeated for runtimes or compatibility"
        ),
    )

    args = parser.parse_args(argv)

    if args.command == "runtimes":
        if args.manual:
            parser.error("--manual can only be used with hardware discovery")

        profile = discover_runtimes(args.runtime_path)

    elif args.command == "compatibility":
        if args.manual:
            parser.error(
                "--manual cannot currently be combined with compatibility discovery"
            )

        hardware = discover_hardware()
        runtimes = discover_runtimes(args.runtime_path)
        evidence = collect_runtime_capability_evidence(
            runtimes,
            args.runtime_path,
        )
        profile = assess_compatibility(
            hardware,
            runtimes,
            evidence,
        )

    else:
        if args.runtime_path:
            parser.error(
                "--runtime-path can only be used with runtime or compatibility discovery"
            )

        try:
            profile = (
                enter_hardware_manually()
                if args.manual
                else discover_hardware()
            )
        except ValueError as exc:
            parser.error(str(exc))

    print(json.dumps(profile.to_dict(), indent=2))
    return 0
