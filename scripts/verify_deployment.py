#!/usr/bin/env python3
"""Fetch every published page and QR asset and compare it with checked-in bytes."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

try:
    from .inventory import load_valid_inventory
except ImportError:
    from inventory import load_valid_inventory


ROOT = Path(__file__).resolve().parents[1]


def verify_file(path: Path, *, site: Path, origin: str, attempts: int = 3) -> str | None:
    """Return a diagnostic on HTTP failure or stale/wrong content, else None."""
    relative = path.relative_to(site).as_posix()
    route = relative.removesuffix("index.html") if path.name == "index.html" else relative
    url = origin.rstrip("/") + "/" + quote(route, safe="/")
    expected = path.read_bytes()
    error = "no attempt made"
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": "CoMPhy-QR-deployment-check/1.0"})
            with urlopen(request, timeout=20) as response:
                # Bound reads even if a proxy returns an unrelated large document.
                actual = response.read(len(expected) + 1)
                if response.status == 200 and actual == expected:
                    return None
                error = f"HTTP {response.status}, content differs from {relative}"
        except (URLError, OSError) as exc:
            error = str(exc)
        if attempt + 1 < attempts:
            time.sleep(5)
    return f"{url}: {error}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.attempts <= 12:
        parser.error("--attempts must be between 1 and 12")
    inventory = load_valid_inventory(ROOT / "inventory/codes.json")
    site = ROOT / "site"
    paths = sorted(path for path in site.rglob("*") if path.is_file())
    if not paths:
        parser.error("no generated site files found")

    def check(path: Path) -> str | None:
        return verify_file(path, site=site, origin=inventory["first_party_origin"], attempts=args.attempts)

    with ThreadPoolExecutor(max_workers=8) as executor:
        errors = [error for error in executor.map(check, paths) if error]
    for error in errors:
        print(error)
    print(f"Verified {len(paths) - len(errors)}/{len(paths)} deployed files against local bytes")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
