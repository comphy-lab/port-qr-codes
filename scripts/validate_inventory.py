#!/usr/bin/env python3
"""Validate the complete QR Code Generator account inventory."""

from __future__ import annotations

import argparse
from pathlib import Path

try:  # Support both ``python scripts/validate_inventory.py`` and test imports.
    from .inventory import EXPECTED_CODE_COUNT, InventoryValidationError, load_valid_inventory
except ImportError:  # pragma: no cover - exercised by the command-line entry point.
    from inventory import EXPECTED_CODE_COUNT, InventoryValidationError, load_valid_inventory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inventory",
        nargs="?",
        type=Path,
        default=Path("inventory/codes.json"),
        help="path to codes.json (default: inventory/codes.json)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        inventory = load_valid_inventory(args.inventory)
    except InventoryValidationError as exc:
        for error in exc.errors:
            print(f"ERROR: {error}")
        return 1
    print(
        f"Inventory valid: schema_version=1, "
        f"codes={len(inventory['codes'])}/{EXPECTED_CODE_COUNT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
