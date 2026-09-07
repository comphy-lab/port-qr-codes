from __future__ import annotations

from copy import deepcopy
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
                PurePosixPath("assets/qr/social-hub.png"),
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
        self.assertNotIn('http-equiv="refresh"', page)
        self.assertIn('download="social-hub.svg"', page)
        self.assertIn('download="social-hub.png"', page)
        self.assertNotIn("Public links", page)
        self.assertIn("First-party route", page)
        index = outputs.site[PurePosixPath("index.html")].decode("utf-8")
        self.assertNotIn("Public links", index)
        self.assertIn('href="social-hub/"', index)
        self.assertIn('href="assets/qr/social-hub.svg"', index)
        self.assertIn('href="assets/qr/social-hub.png"', index)
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

    def test_base_path_is_removed_from_site_routes_without_allowing_traversal(self) -> None:
        inventory = valid_inventory()
        inventory["first_party_origin"] = "https://comphy-lab.org/port-qr-codes"
        inventory["codes"][0]["qr_payload"] = (
            "https://comphy-lab.org/port-qr-codes/social-hub/"
        )
        outputs = build_outputs(inventory)
        self.assertIn(PurePosixPath("social-hub/index.html"), outputs.site)
        self.assertNotIn(
            PurePosixPath("port-qr-codes/social-hub/index.html"), outputs.site
        )
        index = outputs.site[PurePosixPath("index.html")].decode("utf-8")
        self.assertIn('href="social-hub/"', index)
        self.assertNotIn('href="port-qr-codes/social-hub/"', index)

        inventory["codes"][0]["qr_payload"] = (
            "https://comphy-lab.org/port-qr-codes/../escape/"
        )
        with self.assertRaisesRegex(GenerationError, "unsafe first-party route"):
            build_outputs(inventory)

    def test_catalogue_includes_downloads_for_external_static_codes(self) -> None:
        inventory = valid_inventory()
        inventory["codes"][1] = {
            "id": "public-paper",
            "slug": "public-paper",
            "name": "Public paper",
            "folder": "Papers",
            "source_kind": "static",
            "source_status": "static",
            "content_type": "pdf",
            "visibility": "public",
            "source_short_url": None,
            "destination": "https://example.org/paper.pdf",
            "qr_payload": "https://example.org/paper.pdf",
            "migration_status": "direct-static",
        }
        outputs = build_outputs(inventory)
        self.assertIn(PurePosixPath("assets/qr/public-paper.svg"), outputs.site)
        self.assertIn(PurePosixPath("assets/qr/public-paper.png"), outputs.site)
        self.assertNotIn(PurePosixPath("public-paper/index.html"), outputs.site)
        index = outputs.site[PurePosixPath("index.html")].decode("utf-8")
        self.assertIn(
            'href="https://example.org/paper.pdf" target="_blank" '
            'rel="noopener noreferrer">Open target</a>',
            index,
        )
        self.assertIn('download="public-paper.svg"', index)
        self.assertIn('download="public-paper.png"', index)

    def test_single_destination_auto_redirect_is_escaped_with_fallback(self) -> None:
        inventory = deepcopy(valid_inventory())
        code = inventory["codes"][0]
        destination = 'https://example.org/open?label="lab"&mode=full'
        code["content_type"] = "website"
        code["destination"] = destination
        code["links"] = []
        outputs = build_outputs(inventory)
        page = outputs.site[PurePosixPath("social-hub/index.html")].decode("utf-8")
        escaped = "https://example.org/open?label=&quot;lab&quot;&amp;mode=full"
        self.assertIn(
            f'<meta http-equiv="refresh" content="0; url={escaped}">', page
        )
        self.assertIn(f'href="{escaped}"', page)
        self.assertLess(
            page.index('http-equiv="Content-Security-Policy"'),
            page.index('http-equiv="refresh"'),
        )

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
