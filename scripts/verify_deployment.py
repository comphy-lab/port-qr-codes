#!/usr/bin/env python3
"""Verify every published page and QR asset against its checked-in source."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
import time
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import zlib

import png

try:
    from .inventory import load_valid_inventory
except ImportError:
    from inventory import load_valid_inventory


ROOT = Path(__file__).resolve().parents[1]
# Cloudflare may append this beacon to HTML served through the lab domain.
# Accept only the observed empty external tag at the end of the body; the
# generated CSP and every other byte still have to match the source.
HOST_TRANSFORM_ALLOWANCE = 4096
CLOUDFLARE_BEACON = re.compile(
    rb'<script type="module" src="https://static\.cloudflareinsights\.com/beacon\.min\.js/v[0-9a-f]+" '
    rb'integrity="sha512-[A-Za-z0-9+/=]+" data-cf-beacon=\'[^\'<>\r\n]*\' '
    rb'crossorigin="anonymous"></script>\n(?=</body>\n</html>\n\Z)'
)


def matches_content(actual: bytes, expected: bytes, *, html: bool) -> bool:
    """Match exact bytes, allowing only the known host-injected HTML beacon."""
    return actual == expected or (
        html and CLOUDFLARE_BEACON.sub(b"", actual, count=1) == expected
    )


def matches_png(actual: bytes, expected: bytes) -> bool:
    """Allow lossless host recompression only when dimensions and RGBA pixels match."""
    try:
        width, height, rows, _ = png.Reader(bytes=expected).asRGBA8()
        actual_width, actual_height, actual_rows, _ = png.Reader(bytes=actual).asRGBA8()
        if (width, height) != (actual_width, actual_height):
            return False
        return all(
            bytes(left) == bytes(right)
            for left, right in zip(rows, actual_rows, strict=True)
        )
    except (png.Error, ValueError, TypeError, zlib.error):
        return False


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
                is_html = path.suffix == ".html"
                is_png = path.suffix == ".png"
                allowance = HOST_TRANSFORM_ALLOWANCE if is_html or is_png else 0
                limit = len(expected) + allowance
                actual = response.read(limit + 1)
                if response.status == 200 and len(actual) <= limit:
                    if matches_content(actual, expected, html=is_html):
                        return None
                    if is_png and matches_png(actual, expected):
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
    print(f"Verified {len(paths) - len(errors)}/{len(paths)} deployed files against local source")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
