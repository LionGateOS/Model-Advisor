"""Command-line interface for LionGateOS Model Advisor."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from .capability_discovery import collect_runtime_capability_evidence
from .compatibility import assess_compatibility
from .dashboard import collect_dashboard_data
from .dashboard_server import create_dashboard_server
from .discovery import discover_hardware
from .manual import enter_hardware_manually
from .model_discovery import discover_ollama_models
from .catalog_discovery import discover_huggingface_models
from .openrouter_discovery import discover_openrouter_models
from .qualification import qualification_capabilities
from .runtime_discovery import discover_runtimes


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="liongateos-model-advisor",
        description="Know what AI your machine should run.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=(
            "hardware",
            "runtimes",
            "compatibility",
            "models",
            "dashboard",
            "qualification",
            "recommend",
        ),
        default="hardware",
        help=(
            "inspect hardware (default), installed AI runtimes, "
            "hardware/runtime compatibility, local model metadata, "
            "launch the local dashboard, show qualification capabilities, "
            "or show conservative local-model recommendations"
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
            "may be repeated for runtimes, compatibility, or dashboard"
        ),
    )

    parser.add_argument(
        "--model-source",
        choices=("local", "huggingface", "openrouter"),
        default="local",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        metavar="PORT",
        help="local dashboard port (default: 8765)",
    )

    parser.add_argument(
        "--workload",
        choices=("coding", "general_chat", "reasoning"),
        help="with recommend, return only the selected workload",
    )

    parser.add_argument(
        "--passive",
        action="store_true",
        help=(
            "with compatibility, assess without running runtime capability "
            "probes; available runtimes without proven gpu evidence stay "
            "unknown"
        ),
    )

    args = parser.parse_args(argv)

    if args.command == "qualification":
        print(json.dumps(qualification_capabilities(), indent=2))
        return 0

    if args.command == "recommend":
        if args.manual:
            parser.error("--manual can only be used with hardware discovery")
        if args.model_source != "local":
            parser.error("--model-source cannot be used with recommend")

        data = collect_dashboard_data(args.runtime_path)
        recommendations = data["workload_recommendations"]
        if args.workload is not None:
            recommendations = [
                item
                for item in recommendations
                if item["workload"] == args.workload
            ]

        try:
            print(json.dumps(
                {
                    "recommendations": recommendations,
                    "conservative": True,
                    "performance_ranking": False,
                },
                indent=2,
            ))
        except BrokenPipeError:
            return 0
        return 0

    if args.workload is not None:
        parser.error("--workload can only be used with recommend")

    if args.command == "dashboard":
        if args.manual:
            parser.error("--manual can only be used with hardware discovery")

        if not 1 <= args.port <= 65535:
            parser.error("--port must be between 1 and 65535")

        server = create_dashboard_server(
            args.runtime_path,
            port=args.port,
        )
        host, port = server.server_address

        print(f"Model Advisor dashboard: http://{host}:{port}/")

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()

        return 0

    if args.command == "models":
        if args.manual:
            parser.error("--manual can only be used with hardware discovery")

        if args.runtime_path:
            parser.error(
                "--runtime-path cannot be used with local model discovery"
            )

        if args.model_source == "huggingface":
            profile = discover_huggingface_models()
        elif args.model_source == "openrouter":
            profile = discover_openrouter_models()
        else:
            profile = discover_ollama_models()

    elif args.command == "runtimes":
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
        if args.passive:
            evidence: tuple = ()
        else:
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
                "--runtime-path can only be used with runtime, compatibility, "
                "or dashboard discovery"
            )

        try:
            profile = (
                enter_hardware_manually()
                if args.manual
                else discover_hardware()
            )
        except ValueError as exc:
            parser.error(str(exc))

    try:
        print(json.dumps(profile.to_dict(), indent=2))
    except BrokenPipeError:
        return 0

    return 0
