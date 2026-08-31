"""Dependency-light QR decoding helpers for committed PNG and SVG artwork."""

from __future__ import annotations

from pathlib import Path

import png
import resvg_py
import zxingcpp


def rasterize_svg(path: Path) -> bytes:
    """Rasterize an SVG with the pinned resvg binding."""

    return resvg_py.svg_to_bytes(svg_string=path.read_text(encoding="utf-8"))


def decode_qr_png(content: bytes) -> list[zxingcpp.Barcode]:
    """Decode PNG bytes to raw grayscale pixels, then scan them with ZXing."""

    width, height, rows, _metadata = png.Reader(bytes=content).asRGBA8()
    grayscale = bytearray(width * height)
    pixel_index = 0
    for row in rows:
        channels = bytes(row)
        for red, green, blue, alpha in zip(
            channels[0::4],
            channels[1::4],
            channels[2::4],
            channels[3::4],
            strict=True,
        ):
            red = (red * alpha + 255 * (255 - alpha) + 127) // 255
            green = (green * alpha + 255 * (255 - alpha) + 127) // 255
            blue = (blue * alpha + 255 * (255 - alpha) + 127) // 255
            grayscale[pixel_index] = (299 * red + 587 * green + 114 * blue + 500) // 1000
            pixel_index += 1
    if pixel_index != width * height:
        raise AssertionError("decoded PNG row length did not match its dimensions")

    image = memoryview(grayscale).cast("B", shape=(height, width))
    return [
        result
        for result in zxingcpp.read_barcodes(
            image,
            formats=zxingcpp.BarcodeFormat.QRCode,
        )
        if result.format == zxingcpp.BarcodeFormat.QRCode
    ]
