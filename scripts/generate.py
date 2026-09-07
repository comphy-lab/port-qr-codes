#!/usr/bin/env python3
"""Generate deterministic QR artwork and the first-party static link site."""

from __future__ import annotations

import argparse
import html
import io
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

import segno

try:  # Support both ``python scripts/generate.py`` and test imports.
    from .inventory import InventoryValidationError, is_first_party_url, load_valid_inventory
except ImportError:  # pragma: no cover - exercised by the command-line entry point.
    from inventory import InventoryValidationError, is_first_party_url, load_valid_inventory


REPO_ROOT = Path(__file__).resolve().parents[1]
QR_COLOUR = "#67236C"
BACKGROUND = "#FFFFFF"
SVG_WIDTH = 600
PNG_SCALE = 12
QR_BORDER = 4
CONTENT_TYPE_LABELS = {
    "website": "Website",
    "links": "Links",
    "pdf": "PDF",
    "vcard": "Contact card",
}
CSP = "default-src 'none'; img-src 'self'; style-src 'self'; base-uri 'none'; form-action 'none'"
SAFE_ROUTE_SEGMENT_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class GenerationError(RuntimeError):
    """Raised when generated output cannot be applied or verified safely."""


@dataclass(frozen=True)
class GeneratedOutputs:
    """Byte-for-byte expected files for both generated output roots."""

    qr: dict[PurePosixPath, bytes]
    site: dict[PurePosixPath, bytes]


def _qr_for(payload: str) -> segno.QRCode:
    return segno.make(
        payload,
        error="h",
        micro=False,
        boost_error=False,
    )


def _module_path(qr: segno.QRCode, border: int) -> str:
    commands: list[str] = []
    for row_index, row in enumerate(qr.matrix):
        start: int | None = None
        for column_index, dark in enumerate((*row, False)):
            if dark and start is None:
                start = column_index
            elif not dark and start is not None:
                run = column_index - start
                x = start + border
                y = row_index + border
                commands.append(f"M{x} {y}h{run}v1h-{run}z")
                start = None
    return "".join(commands)


def render_svg(payload: str) -> bytes:
    """Render a minimal, byte-reproducible purple-on-white QR SVG."""

    qr = _qr_for(payload)
    size = len(qr.matrix) + 2 * QR_BORDER
    title = html.escape(payload, quote=True)
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {size} {size}" width="{SVG_WIDTH}" height="{SVG_WIDTH}" '
        'role="img" shape-rendering="crispEdges">\n'
        f"  <title>{title}</title>\n"
        f'  <rect width="{size}" height="{size}" fill="{BACKGROUND}"/>\n'
        f'  <path d="{_module_path(qr, QR_BORDER)}" fill="{QR_COLOUR}"/>\n'
        "</svg>\n"
    )
    return document.encode("utf-8")


def render_png(payload: str) -> bytes:
    """Render the matching lossless PNG used by portable decoder tests."""

    stream = io.BytesIO()
    _qr_for(payload).save(
        stream,
        kind="png",
        scale=PNG_SCALE,
        border=QR_BORDER,
        dark=QR_COLOUR,
        light=BACKGROUND,
    )
    return stream.getvalue()


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _page_head(
    *,
    title: str,
    description: str,
    canonical_url: str,
    css_href: str,
    redirect_url: str | None = None,
) -> str:
    redirect = (
        f'  <meta http-equiv="refresh" content="0; url={_escape(redirect_url)}">\n'
        if redirect_url is not None
        else ""
    )
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'  <meta http-equiv="Content-Security-Policy" content="{_escape(CSP)}">\n'
        '  <meta name="referrer" content="no-referrer">\n'
        + redirect
        + f"  <title>{_escape(title)}</title>\n"
        f'  <meta name="description" content="{_escape(description)}">\n'
        f'  <link rel="canonical" href="{_escape(canonical_url)}">\n'
        f'  <link rel="stylesheet" href="{_escape(css_href)}">\n'
        "</head>\n"
    )


def _first_party_route(value: str, origin: str) -> tuple[str, ...]:
    """Return a safe route relative to the configured first-party base path."""

    parsed = urlsplit(value)
    parsed_origin = urlsplit(origin)
    if (parsed.scheme, parsed.netloc.casefold()) != (
        parsed_origin.scheme,
        parsed_origin.netloc.casefold(),
    ):
        raise GenerationError(f"first-party route has a different origin: {value}")
    if parsed.query or parsed.fragment or not parsed.path.endswith("/"):
        raise GenerationError(f"unsafe first-party route: {value}")

    base_segments = tuple(segment for segment in parsed_origin.path.split("/") if segment)
    path_segments = tuple(segment for segment in parsed.path.split("/") if segment)
    if path_segments[: len(base_segments)] != base_segments:
        raise GenerationError(f"first-party route is outside configured base path: {value}")
    route = path_segments[len(base_segments) :]
    if not route or any(SAFE_ROUTE_SEGMENT_RE.fullmatch(segment) is None for segment in route):
        raise GenerationError(f"unsafe first-party route: {value}")
    return route


def _redirect_destination(code: dict[str, Any]) -> str | None:
    """Return the validated single destination eligible for automatic navigation."""

    destination = code.get("destination")
    if not isinstance(destination, str):
        return None
    parsed = urlsplit(destination)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or any(character.isspace() or ord(character) < 0x20 for character in destination)
    ):
        raise GenerationError(f"unsafe redirect destination for {code['slug']}")
    return destination


def _action_links(code: dict[str, Any]) -> list[tuple[str, str]]:
    actions: list[tuple[str, str]] = []
    destination = code.get("destination")
    if isinstance(destination, str):
        label = {
            "website": "Open website",
            "pdf": "Open PDF",
            "vcard": "Open contact card",
            "links": "Open destination",
        }[code["content_type"]]
        actions.append((label, destination))
    for link in code.get("links", []):
        actions.append((link["label"], link["url"]))
    return actions


def _code_page(code: dict[str, Any], *, origin: str, depth: int) -> str:
    payload = code["qr_payload"]
    summary = code.get("summary") or "A durable QR destination managed by CoMPhy Lab."
    prefix = "../" * depth
    actions = _action_links(code)
    destination_markup = "\n".join(
        f'          <li><a class="action" href="{_escape(url)}" '
        f'target="_blank" rel="noopener noreferrer">{_escape(label)}</a></li>'
        for label, url in actions
    )
    if not destination_markup:
        destination_markup = '          <li class="quiet">No public destination is attached yet.</li>'
    downloads = (
        f'          <li><a class="action secondary" href="{prefix}assets/qr/{_escape(code["slug"])}.svg" '
        f'download="{_escape(code["slug"])}.svg">Download SVG</a></li>\n'
        f'          <li><a class="action secondary" href="{prefix}assets/qr/{_escape(code["slug"])}.png" '
        f'download="{_escape(code["slug"])}.png">Download PNG</a></li>'
    )
    return (
        _page_head(
            title=f"{code['name']} | CoMPhy Lab QR",
            description=summary,
            canonical_url=payload,
            css_href=f"{prefix}assets/style.css",
            redirect_url=_redirect_destination(code),
        )
        + "<body>\n"
        + '  <main class="shell detail">\n'
        + f'    <a class="brand" href="{prefix}index.html" aria-label="CoMPhy Lab QR index">CoMPhy Lab <span>QR</span></a>\n'
        + '    <article class="detail-card">\n'
        + '      <div class="copy">\n'
        + f'        <p class="eyebrow">{_escape(CONTENT_TYPE_LABELS[code["content_type"]])} · First-party route</p>\n'
        + f"        <h1>{_escape(code['name'])}</h1>\n"
        + f"        <p class=\"summary\">{_escape(summary)}</p>\n"
        + '        <ul class="actions">\n'
        + destination_markup
        + "\n"
        + downloads
        + "\n        </ul>\n"
        + "      </div>\n"
        + '      <figure class="qr-panel">\n'
        + f'        <img src="{prefix}assets/qr/{_escape(code["slug"])}.svg" width="600" height="600" alt="QR code for {_escape(code["name"])}">\n'
        + "        <figcaption>First-party URL<br><code>"
        + _escape(payload)
        + "</code></figcaption>\n"
        + "      </figure>\n"
        + "    </article>\n"
        + "  </main>\n"
        + "</body>\n"
        + "</html>\n"
    )


def _index_page(codes: list[dict[str, Any]], *, origin: str) -> str:
    cards: list[str] = []
    for code in codes:
        payload = code["qr_payload"]
        if is_first_party_url(payload, origin):
            route_href = "/".join(_first_party_route(payload, origin)) + "/"
            route_label = "Open page"
            route_target = ""
        else:
            route_href = payload
            route_label = "Open target"
            route_target = ' target="_blank" rel="noopener noreferrer"'
        slug = _escape(code["slug"])
        cards.append(
            '      <li class="card">\n'
            f'        <span class="eyebrow">{_escape(CONTENT_TYPE_LABELS[code["content_type"]])}</span>\n'
            f"        <strong>{_escape(code['name'])}</strong>\n"
            '        <span class="card-links">\n'
            f'          <a href="{_escape(route_href)}"{route_target}>{route_label}</a>\n'
            f'          <a href="assets/qr/{slug}.svg" download="{slug}.svg">SVG</a>\n'
            f'          <a href="assets/qr/{slug}.png" download="{slug}.png">PNG</a>\n'
            "        </span>\n"
            "      </li>"
        )
    description = "First-party QR destinations maintained by the Computational Multiphase Physics Lab."
    return (
        _page_head(
            title="CoMPhy Lab QR destinations",
            description=description,
            canonical_url=f"{origin}/",
            css_href="assets/style.css",
        )
        + "<body>\n"
        + '  <main class="shell">\n'
        + '    <header class="hero">\n'
        + '      <p class="brand">CoMPhy Lab <span>QR</span></p>\n'
        + "      <h1>Useful links, without the rented QR plumbing.</h1>\n"
        + f"      <p>{_escape(description)}</p>\n"
        + "    </header>\n"
        + '    <ul class="grid" aria-label="QR destinations">\n'
        + ("\n".join(cards) if cards else '      <li class="quiet">No public link pages yet.</li>')
        + "\n    </ul>\n"
        + "  </main>\n"
        + "</body>\n"
        + "</html>\n"
    )


STYLE_CSS = """\
:root {
  color-scheme: light;
  --ink: #201924;
  --muted: #6f6473;
  --purple: #67236c;
  --purple-soft: #f4eaf5;
  --paper: #fffdfb;
  --line: #e6dfe7;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  min-height: 100vh;
  color: var(--ink);
  background:
    radial-gradient(circle at 90% 4%, #f1e2f2 0, transparent 32rem),
    var(--paper);
  font-family: "Avenir Next", "Trebuchet MS", sans-serif;
  line-height: 1.55;
}

a { color: inherit; }

.shell {
  width: min(70rem, calc(100% - 2rem));
  margin: 0 auto;
  padding: clamp(2rem, 6vw, 5rem) 0;
}

.brand {
  display: inline-block;
  margin: 0 0 3rem;
  color: var(--ink);
  font-size: .86rem;
  font-weight: 800;
  letter-spacing: .08em;
  text-decoration: none;
  text-transform: uppercase;
}

.brand span { color: var(--purple); }

.hero { max-width: 50rem; }

.hero h1,
.detail h1 {
  max-width: 14ch;
  margin: 0;
  font-size: clamp(2.5rem, 7vw, 5.6rem);
  letter-spacing: -.055em;
  line-height: .96;
  font-family: "Iowan Old Style", Baskerville, Georgia, serif;
  font-weight: 700;
}

.hero > p:last-child,
.summary {
  max-width: 43rem;
  margin: 1.5rem 0 0;
  color: var(--muted);
  font-size: clamp(1.05rem, 2vw, 1.3rem);
}

.grid,
.actions {
  padding: 0;
  list-style: none;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 17rem), 1fr));
  gap: 1rem;
  margin: 4rem 0 0;
}

.hero > *,
.detail-card .copy,
.detail-card .qr-panel,
.grid .card {
  animation: settle-in 520ms cubic-bezier(.2, .72, .25, 1) both;
}

.hero > :nth-child(2),
.detail-card .qr-panel { animation-delay: 70ms; }
.hero > :nth-child(3) { animation-delay: 130ms; }
.grid .card:nth-child(2n) { animation-delay: 45ms; }
.grid .card:nth-child(3n) { animation-delay: 90ms; }

.card {
  display: grid;
  min-height: 11rem;
  padding: 1.4rem;
  border: 1px solid var(--line);
  border-radius: 1rem;
  background: rgb(255 255 255 / 78%);
  box-shadow: 0 .8rem 2rem rgb(62 31 66 / 5%);
  transition: border-color 300ms ease, transform 300ms ease;
}

.card:hover,
.card:focus-within {
  border-color: var(--purple);
  transform: translateY(-2px);
}

.card strong { margin-top: .55rem; font-size: 1.25rem; line-height: 1.2; }
.card-links { align-self: end; display: flex; flex-wrap: wrap; gap: .8rem; margin-top: 1.5rem; }
.card-links a { color: var(--purple); font-size: .9rem; font-weight: 750; }

.eyebrow {
  margin: 0;
  color: var(--purple);
  font-size: .75rem;
  font-weight: 800;
  letter-spacing: .1em;
  text-transform: uppercase;
}

.detail-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(16rem, 25rem);
  gap: clamp(2rem, 7vw, 6rem);
  align-items: center;
}

.detail h1 { margin-top: .8rem; font-size: clamp(2.4rem, 6vw, 4.8rem); }

.actions { display: flex; flex-wrap: wrap; gap: .75rem; margin: 2rem 0 0; }

.action {
  display: inline-block;
  padding: .8rem 1.1rem;
  border-radius: 999px;
  color: white;
  background: var(--purple);
  font-weight: 750;
  text-decoration: none;
}

.action:hover,
.action:focus-visible { background: #4f1554; }
.action.secondary { color: var(--purple); background: var(--purple-soft); }
.action.secondary:hover,
.action.secondary:focus-visible { background: #ead8ec; }

.qr-panel {
  margin: 0;
  padding: 1.25rem;
  border: 1px solid var(--line);
  border-radius: 1.5rem;
  background: white;
  box-shadow: 0 1.5rem 4rem rgb(62 31 66 / 10%);
}

.qr-panel img { display: block; width: 100%; height: auto; }
.qr-panel figcaption { margin-top: 1rem; color: var(--muted); font-size: .82rem; }
.qr-panel code { overflow-wrap: anywhere; color: var(--ink); }
.quiet { color: var(--muted); }

@keyframes settle-in {
  from { opacity: 0; transform: translateY(.7rem); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 47rem) {
  .detail-card { grid-template-columns: 1fr; }
  .qr-panel { max-width: 25rem; }
}

@media (prefers-reduced-motion: reduce) {
  .hero > *,
  .detail-card .copy,
  .detail-card .qr-panel,
  .grid .card { animation: none; }
  .card a { transition: none; }
}
"""


def build_outputs(inventory: dict[str, Any]) -> GeneratedOutputs:
    """Build every expected file in memory without touching the filesystem."""

    origin = inventory["first_party_origin"].rstrip("/")
    eligible = sorted(
        (
            code
            for code in inventory["codes"]
            if code["visibility"] == "public"
            and code["source_status"] != "paused"
            and isinstance(code.get("qr_payload"), str)
        ),
        key=lambda code: code["slug"],
    )

    qr_outputs: dict[PurePosixPath, bytes] = {}
    svg_by_slug: dict[str, bytes] = {}
    png_by_slug: dict[str, bytes] = {}
    for code in eligible:
        slug = code["slug"]
        payload = code["qr_payload"]
        svg = render_svg(payload)
        png = render_png(payload)
        svg_by_slug[slug] = svg
        png_by_slug[slug] = png
        qr_outputs[PurePosixPath(f"{slug}.svg")] = svg
        qr_outputs[PurePosixPath(f"{slug}.png")] = png

    catalogue_codes = sorted(
        eligible,
        key=lambda code: (code["name"].casefold(), code["slug"]),
    )
    first_party_codes = sorted(
        (
            code
            for code in eligible
            if is_first_party_url(code["qr_payload"], origin)
        ),
        key=lambda code: (code["name"].casefold(), code["slug"]),
    )
    site_outputs: dict[PurePosixPath, bytes] = {
        PurePosixPath("assets/style.css"): STYLE_CSS.encode("utf-8"),
        PurePosixPath("index.html"): _index_page(catalogue_codes, origin=origin).encode("utf-8"),
    }
    for code in catalogue_codes:
        slug = code["slug"]
        site_outputs[PurePosixPath(f"assets/qr/{slug}.svg")] = svg_by_slug[slug]
        site_outputs[PurePosixPath(f"assets/qr/{slug}.png")] = png_by_slug[slug]
    for code in first_party_codes:
        segments = _first_party_route(code["qr_payload"], origin)
        page_path = PurePosixPath(*segments, "index.html")
        site_outputs[page_path] = _code_page(
            code,
            origin=origin,
            depth=len(segments),
        ).encode("utf-8")

    return GeneratedOutputs(qr=qr_outputs, site=site_outputs)


def _actual_files(root: Path) -> set[PurePosixPath]:
    if not root.exists():
        return set()
    if root.is_symlink() or not root.is_dir():
        raise GenerationError(f"unsafe output root (expected a real directory): {root}")
    files: set[PurePosixPath] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise GenerationError(f"refusing symlink in generated tree: {path}")
        if path.is_file():
            files.add(PurePosixPath(path.relative_to(root).as_posix()))
    return files


def compare_tree(expected: dict[PurePosixPath, bytes], root: Path) -> list[str]:
    """Return missing, unexpected, and byte-drift diagnostics for one tree."""

    actual = _actual_files(root)
    expected_paths = set(expected)
    errors = [f"{root}: missing {path}" for path in sorted(expected_paths - actual)]
    errors.extend(f"{root}: unexpected {path}" for path in sorted(actual - expected_paths))
    for relative in sorted(actual & expected_paths):
        target = root.joinpath(*relative.parts)
        if target.read_bytes() != expected[relative]:
            errors.append(f"{root}: generated content differs: {relative}")
    return errors


def _safe_target(root: Path, relative: PurePosixPath) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise GenerationError(f"unsafe generated path: {relative}")
    root_resolved = root.resolve(strict=False)
    if root.exists() and (root.is_symlink() or not root.is_dir()):
        raise GenerationError(f"unsafe output root (expected a real directory): {root}")
    target = root.joinpath(*relative.parts)
    if target.exists() and target.is_symlink():
        raise GenerationError(f"refusing symlinked output file: {target}")
    current = target.parent
    while current != root and current != current.parent:
        if current.exists() and current.is_symlink():
            raise GenerationError(f"refusing symlinked output path: {current}")
        current = current.parent
    if not target.resolve(strict=False).is_relative_to(root_resolved):
        raise GenerationError(f"generated path escapes output root: {relative}")
    return target


def _atomic_write(target: Path, content: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    stream = tempfile.NamedTemporaryFile(
        dir=target.parent,
        prefix=f".{target.name}.",
        delete=False,
    )
    temporary = Path(stream.name)
    try:
        with stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def write_tree(expected: dict[PurePosixPath, bytes], root: Path) -> None:
    """Write expected files atomically, refusing to delete or overwrite extra files."""

    extras = _actual_files(root) - set(expected)
    if extras:
        rendered = ", ".join(str(path) for path in sorted(extras))
        raise GenerationError(f"{root}: refusing to prune unexpected files: {rendered}")
    for relative, content in sorted(expected.items()):
        _atomic_write(_safe_target(root, relative), content)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=REPO_ROOT / "inventory/codes.json")
    parser.add_argument("--qr-output", type=Path, default=REPO_ROOT / "current/account")
    parser.add_argument("--site-output", type=Path, default=REPO_ROOT / "site")
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare committed outputs without writing",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        inventory = load_valid_inventory(args.inventory)
        outputs = build_outputs(inventory)
        if args.check:
            errors = compare_tree(outputs.qr, args.qr_output)
            errors.extend(compare_tree(outputs.site, args.site_output))
            if errors:
                for error in errors:
                    print(f"ERROR: {error}")
                return 1
            print(
                f"Generated outputs current: QR files={len(outputs.qr)}, "
                f"site files={len(outputs.site)}"
            )
            return 0
        write_tree(outputs.qr, args.qr_output)
        write_tree(outputs.site, args.site_output)
        print(
            f"Generated QR files={len(outputs.qr)}, site files={len(outputs.site)}"
        )
        return 0
    except (GenerationError, InventoryValidationError, OSError) as exc:
        if isinstance(exc, InventoryValidationError):
            for error in exc.errors:
                print(f"ERROR: {error}")
        else:
            print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
