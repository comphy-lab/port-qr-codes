#!/usr/bin/env python3
"""Generate the standalone, branded QR assets used by the hero video."""

from __future__ import annotations

import base64
import html
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import segno


ROOT = Path(__file__).resolve().parent
OUTDIR = ROOT / "current"
COMPHY_MARK = Path(
    os.environ.get("COMPHY_QR_MARK", ROOT / "assets" / "comphy-lab-mark.png")
).expanduser()
QR_COLOUR = "#67236C"
BACKGROUND = "#FFFFFF"
SVG_SIZE = 600
PNG_SIZE = 2400


@dataclass(frozen=True)
class QRAsset:
    key: str
    stem: str
    url: str
    logo: str


ASSETS = (
    QRAsset(
        key="contact",
        stem="comphy-contact-card-qr",
        url="https://comphy-lab.org/contact-card/",
        logo="comphy",
    ),
    QRAsset(
        key="github",
        stem="bursting-bubble-github-qr",
        url="https://github.com/comphy-lab/Bursting-Bubble",
        logo="github",
    ),
    QRAsset(
        key="arxiv",
        stem="arxiv-2607.08972-qr",
        url="https://arxiv.org/abs/2607.08972",
        logo="arxiv",
    ),
    QRAsset(
        key="arxiv-singularities",
        stem="arxiv-2608.11060-qr",
        url="https://arxiv.org/pdf/2608.11060",
        logo="arxiv",
    ),
)


GITHUB_PATH = (
    "M10.226 17.284c-2.965-.36-5.054-2.493-5.054-5.256 0-1.123.404-2.336 "
    "1.078-3.144-.292-.741-.247-2.314.09-2.965.898-.112 2.111.36 2.83 1.01.853-.269 "
    "1.752-.404 2.853-.404 1.1 0 1.999.135 2.807.382.696-.629 1.932-1.1 2.83-.988.315.606 "
    ".36 2.179.067 2.942.72.854 1.101 2 1.101 3.167 0 2.763-2.089 4.852-5.098 5.234.763.494 "
    "1.28 1.572 1.28 2.807v2.336c0 .674.561 1.056 1.235.786 4.066-1.55 7.255-5.615 "
    "7.255-10.646C23.5 6.188 18.334 1 11.978 1 5.62 1 .5 6.188.5 12.545c0 4.986 "
    "3.167 9.12 7.435 10.669.606.225 1.19-.18 1.19-.786V20.63a2.9 2.9 0 0 1-1.078.224c-1.483 "
    "0-2.359-.808-2.987-2.313-.247-.607-.517-.966-1.034-1.033-.27-.023-.359-.135-.359-.27 "
    "0-.27.45-.471.898-.471.652 0 1.213.404 1.797 1.235.45.651.921.943 1.483.943.561 0 "
    ".92-.202 1.437-.719.382-.381.674-.718.944-.943"
)


# Official arXiv logomark geometry, cropped from arXiv's primary SVG asset.
ARXIV_PATHS = (
    (
        "#AA142D",
        "M127.98,55.61l-32.74,38.85c-1.29,1.37-2.08,3.78-1.36,5.5.75,1.8,2.46,2.91,4.4,2.91,"
        "1.09,0,1.99-.38,3.16-1.56l40.19-42.71c1.6-1.69,1.62-4.33.04-6.04l-13.68,3.05Z",
    ),
    (
        "#AFA497",
        "M127.98,55.61l31.19-38.27c1.49-1.99,2.2-3.03,1.49-4.72-.74-1.77-2.59-3.16-4.48-3.16h0"
        "c-1.06,0-1.72.09-3.01,1.11l-38.63,41.76c-1.72,1.84-1.71,4.7.02,6.53l47.79,51.07"
        "c1.02,1.05,2.05,1.19,3.14,1.19,1.93,0,3.19-1.14,4.03-2.82.72-1.73-.08-3.44-1.4-5.23"
        "l-40.12-47.46",
    ),
    (
        "#AA142D",
        "M141.67,52.56L95,2.13S93.29.04,91.48,0s-3.6,1.02-4.34,2.79c-.7,1.69-.2,2.88,1.35,5.1"
        "l40.09,48.42",
    ),
)


def _module_path(qr: segno.QRCode, border: int) -> str:
    commands: list[str] = []
    for row_index, row in enumerate(qr.matrix):
        start = None
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


def _logo_markup(kind: str, size: int) -> str:
    centre = size / 2

    if kind == "github":
        plaque = size * 0.218
        logo = size * 0.148
        x = centre - logo / 2
        y = centre - logo / 2
        scale = logo / 24
        return (
            f'<rect x="{centre - plaque/2:.4f}" y="{centre - plaque/2:.4f}" '
            f'width="{plaque:.4f}" height="{plaque:.4f}" rx="{plaque*0.18:.4f}" fill="#fff"/>'
            f'<path d="{GITHUB_PATH}" fill="#181717" '
            f'transform="translate({x:.5f} {y:.5f}) scale({scale:.7f})"/>'
        )

    if kind == "arxiv":
        plaque = size * 0.222
        logo_h = size * 0.158
        logo_w = logo_h * (87 / 111)
        scale = logo_h / 111
        x = centre - logo_w / 2
        y = centre - logo_h / 2
        paths = "".join(f'<path d="{path}" fill="{fill}"/>' for fill, path in ARXIV_PATHS)
        return (
            f'<rect x="{centre - plaque/2:.4f}" y="{centre - plaque/2:.4f}" '
            f'width="{plaque:.4f}" height="{plaque:.4f}" rx="{plaque*0.18:.4f}" fill="#fff"/>'
            f'<g transform="translate({x:.5f} {y:.5f}) scale({scale:.7f}) translate(-84 0)">{paths}</g>'
        )

    if kind == "comphy":
        plaque_w = size * 0.268
        plaque_h = size * 0.192
        logo_w = size * 0.224
        logo_h = logo_w
        png = base64.b64encode(COMPHY_MARK.read_bytes()).decode("ascii")
        return (
            f'<rect x="{centre - plaque_w/2:.4f}" y="{centre - plaque_h/2:.4f}" '
            f'width="{plaque_w:.4f}" height="{plaque_h:.4f}" rx="{plaque_h*0.20:.4f}" fill="#fff"/>'
            f'<image x="{centre - logo_w/2:.4f}" y="{centre - logo_h/2:.4f}" '
            f'width="{logo_w:.4f}" height="{logo_h:.4f}" preserveAspectRatio="xMidYMid meet" '
            f'href="data:image/png;base64,{png}"/>'
        )

    raise ValueError(f"Unknown logo kind: {kind}")


def _contact_label(size: int) -> tuple[float, str]:
    gap = -size * 0.032
    pill_h = size * 0.146
    bottom = size * 0.030
    pill_x = size * 0.080
    pill_w = size - 2 * pill_x
    pill_y = size + gap
    circle_x = pill_x + pill_h * 0.58
    circle_y = pill_y + pill_h / 2
    circle_r = pill_h * 0.39
    icon_w = circle_r * 1.18
    icon_h = circle_r * 0.82
    icon_x = circle_x - icon_w / 2
    icon_y = circle_y - icon_h / 2
    font_size = pill_h * 0.53
    text_x = pill_x + pill_h * 1.15
    text_y = pill_y + pill_h * 0.684
    canvas_height = pill_y + pill_h + bottom

    markup = (
        f'<rect x="{pill_x:.4f}" y="{pill_y:.4f}" width="{pill_w:.4f}" height="{pill_h:.4f}" '
        f'rx="{pill_h/2:.4f}" fill="{QR_COLOUR}"/>'
        f'<circle cx="{circle_x:.4f}" cy="{circle_y:.4f}" r="{circle_r:.4f}" fill="#fff"/>'
        f'<rect x="{icon_x:.4f}" y="{icon_y:.4f}" width="{icon_w:.4f}" height="{icon_h:.4f}" '
        f'rx="{icon_h*0.09:.4f}" fill="none" stroke="{QR_COLOUR}" stroke-width="{icon_h*0.11:.4f}"/>'
        f'<circle cx="{icon_x + icon_w*0.29:.4f}" cy="{icon_y + icon_h*0.36:.4f}" '
        f'r="{icon_h*0.14:.4f}" fill="{QR_COLOUR}"/>'
        f'<path d="M{icon_x + icon_w*0.13:.4f} {icon_y + icon_h*0.72:.4f}'
        f'c0-{icon_h*0.19:.4f} {icon_w*0.12:.4f}-{icon_h*0.28:.4f} {icon_w*0.16:.4f}-{icon_h*0.28:.4f}'
        f's{icon_w*0.16:.4f} {icon_h*0.09:.4f} {icon_w*0.16:.4f} {icon_h*0.28:.4f}z" '
        f'fill="{QR_COLOUR}"/>'
        f'<path d="M{icon_x + icon_w*0.58:.4f} {icon_y + icon_h*0.31:.4f}h{icon_w*0.25:.4f}'
        f'M{icon_x + icon_w*0.58:.4f} {icon_y + icon_h*0.52:.4f}h{icon_w*0.25:.4f}'
        f'M{icon_x + icon_w*0.58:.4f} {icon_y + icon_h*0.73:.4f}h{icon_w*0.18:.4f}" '
        f'fill="none" stroke="{QR_COLOUR}" stroke-width="{icon_h*0.09:.4f}" stroke-linecap="round"/>'
        f'<text x="{text_x:.4f}" y="{text_y:.4f}" fill="#fff" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" '
        f'font-size="{font_size:.4f}" font-weight="400" letter-spacing="0.01em">Contact</text>'
    )
    return canvas_height, markup


def _svg_for(asset: QRAsset) -> str:
    border = 4
    qr = segno.make(asset.url, error="h", micro=False, boost_error=False)
    matrix_size = len(qr.matrix)
    size = matrix_size + 2 * border
    module_path = _module_path(qr, border)
    if asset.key == "contact":
        canvas_height, label_markup = _contact_label(size)
    else:
        canvas_height, label_markup = float(size), ""
    svg_height = SVG_SIZE * canvas_height / size
    label_line = f"  {label_markup}\n" if label_markup else "\n"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {size} {canvas_height:.5f}" width="{SVG_SIZE}" height="{svg_height:.5f}" '
        'role="img" shape-rendering="geometricPrecision">\n'
        f'  <title>{html.escape(asset.url)}</title>\n'
        f'  <rect width="{size}" height="{canvas_height:.5f}" fill="{BACKGROUND}"/>\n'
        f'  <path d="{module_path}" fill="{QR_COLOUR}" shape-rendering="crispEdges"/>\n'
        f'  {_logo_markup(asset.logo, size)}\n'
        f"{label_line}"
        '</svg>\n'
    )


def _render(svg: Path) -> None:
    png = svg.with_suffix(".png")
    pdf = svg.with_suffix(".pdf")
    subprocess.run(
        ["rsvg-convert", "--width", str(PNG_SIZE), "--output", str(png), str(svg)],
        check=True,
    )
    subprocess.run(
        ["rsvg-convert", "--format", "pdf", "--output", str(pdf), str(svg)],
        check=True,
    )


def build(asset: QRAsset) -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    svg = OUTDIR / f"{asset.stem}.svg"
    svg.write_text(_svg_for(asset), encoding="utf-8")
    _render(svg)


def make_arxiv() -> None:
    for asset in ASSETS:
        if asset.logo == "arxiv":
            build(asset)


def main() -> None:
    for asset in ASSETS:
        build(asset)


if __name__ == "__main__":
    main()
