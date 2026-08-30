from __future__ import annotations

from pathlib import Path, PurePosixPath
import tempfile
import unittest
from unittest import mock

import zxingcpp

from scripts.generate import (
    GenerationError,
    build_outputs,
    compare_tree,
    render_png,
    render_svg,
    write_tree,
)
from scripts.inventory import require_valid_inventory
from tests.helpers import PUBLIC_PAYLOAD, valid_inventory
from tests.qr_decode import decode_qr_png


class GenerationTests(unittest.TestCase):
    def test_svg_and_png_generation_is_byte_deterministic_and_decodable(self) -> None:
        first_svg = render_svg(PUBLIC_PAYLOAD)
        second_svg = render_svg(PUBLIC_PAYLOAD)
        first_png = render_png(PUBLIC_PAYLOAD)
        second_png = render_png(PUBLIC_PAYLOAD)
        self.assertEqual(first_svg, second_svg)
        self.assertEqual(first_png, second_png)
        self.assertIn(b'fill="#67236C"', first_svg)
        self.assertIn(b'fill="#FFFFFF"', first_svg)
        self.assertNotIn(b"<script", first_svg.lower())
        results = decode_qr_png(first_png)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].text, PUBLIC_PAYLOAD)
        self.assertEqual(results[0].format, zxingcpp.BarcodeFormat.QRCode)

    def test_build_outputs_contains_only_eligible_qr_and_first_party_site(self) -> None:
        outputs = build_outputs(require_valid_inventory(valid_inventory()))
        self.assertEqual(
            set(outputs.qr),
            {PurePosixPath("social-hub.svg"), PurePosixPath("social-hub.png")},
        )
        self.assertEqual(
            set(outputs.site),
            {
                PurePosixPath("assets/style.css"),
                PurePosixPath("assets/qr/social-hub.svg"),
                PurePosixPath("index.html"),
                PurePosixPath("social-hub/index.html"),
            },
        )

    def test_generated_html_escapes_inventory_and_has_early_strict_csp(self) -> None:
        outputs = build_outputs(require_valid_inventory(valid_inventory()))
        page = outputs.site[PurePosixPath("social-hub/index.html")].decode("utf-8")
        self.assertLess(
            page.index('http-equiv="Content-Security-Policy"'),
            page.index('rel="stylesheet"'),
        )
        self.assertIn("default-src &#x27;none&#x27;", page)
        self.assertNotIn("unsafe-inline", page)
        self.assertNotIn("unsafe-eval", page)
        self.assertNotIn("<script", page.casefold())
        self.assertNotIn("javascript:", page.casefold())
        self.assertNotIn("<social>", page)
        self.assertIn("&lt;social&gt;", page)
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;alert", page)
        self.assertNotIn("fonts.googleapis.com", page)
        self.assertIn('target="_blank" rel="noopener noreferrer"', page)
        self.assertNotIn("Public links", page)
        self.assertIn("First-party route", page)
        index = outputs.site[PurePosixPath("index.html")].decode("utf-8")
        self.assertNotIn("Public links", index)
        self.assertIn("First-party replacement", index)
        css = outputs.site[PurePosixPath("assets/style.css")].decode("utf-8")
        self.assertIn(
            'font-family: "Iowan Old Style", Baskerville, Georgia, serif', css
        )
        self.assertIn(
            'font-family: "Avenir Next", "Trebuchet MS", sans-serif', css
        )
        self.assertIn("@keyframes settle-in", css)
        self.assertIn(
            "transition: border-color 300ms ease, transform 300ms ease", css
        )
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)

    def test_write_then_check_detects_no_drift_and_reports_mutation(self) -> None:
        outputs = build_outputs(require_valid_inventory(valid_inventory()))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            qr_root = root / "current" / "account"
            site_root = root / "site"
            write_tree(outputs.qr, qr_root)
            write_tree(outputs.site, site_root)
            self.assertEqual(compare_tree(outputs.qr, qr_root), [])
            self.assertEqual(compare_tree(outputs.site, site_root), [])
            (qr_root / "social-hub.svg").write_text("changed", encoding="utf-8")
            self.assertTrue(
                any(
                    "generated content differs" in error
                    for error in compare_tree(outputs.qr, qr_root)
                )
            )

    def test_generator_refuses_unexpected_files_instead_of_pruning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "generated"
            root.mkdir()
            (root / "human-note.txt").write_text("keep me", encoding="utf-8")
            with self.assertRaisesRegex(GenerationError, "refusing to prune"):
                write_tree({PurePosixPath("expected.txt"): b"expected\n"}, root)
            self.assertEqual(
                (root / "human-note.txt").read_text(encoding="utf-8"), "keep me"
            )

    def test_generator_refuses_symlinked_output_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            root = temporary / "generated"
            elsewhere = temporary / "elsewhere"
            root.mkdir()
            elsewhere.mkdir()
            (root / "nested").symlink_to(elsewhere, target_is_directory=True)
            with self.assertRaisesRegex(GenerationError, "symlink"):
                write_tree({PurePosixPath("nested/file.txt"): b"blocked\n"}, root)
            self.assertFalse((elsewhere / "file.txt").exists())

    def test_atomic_write_cleans_temporary_file_after_fsync_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "generated"
            with mock.patch(
                "scripts.generate.os.fsync",
                side_effect=OSError("injected fsync failure"),
            ):
                with self.assertRaisesRegex(OSError, "injected fsync failure"):
                    write_tree({PurePosixPath("expected.txt"): b"expected\n"}, root)
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
