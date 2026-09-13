"""Command-line interface for LionGateOS Model Advisor."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from .discovery import discover_hardware
from .manual import enter_hardware_manually


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="liongateos-model-advisor",
        description="Know what AI your machine should run.",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="enter hardware information manually instead of auto-detecting it",
    )
    args = parser.parse_args(argv)

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
