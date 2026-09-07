from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from scripts.verify_deployment import verify_file


class DeploymentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.site = Path(self.directory.name)
        self.path = self.site / "paper" / "index.html"
        self.path.parent.mkdir()
        self.path.write_bytes(b"expected page")

    def check(self, attempts: int = 1) -> str | None:
        return verify_file(self.path, site=self.site, origin="https://example.org/qr", attempts=attempts)

    def response(self, body: bytes) -> MagicMock:
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = body
        return response

    @patch("scripts.verify_deployment.urlopen")
    def test_checks_the_public_directory_route_under_the_base_path(self, fetch) -> None:
        fetch.return_value = self.response(b"expected page")
        self.assertIsNone(self.check())
        self.assertEqual(fetch.call_args.args[0].full_url, "https://example.org/qr/paper/")

    @patch("scripts.verify_deployment.urlopen")
    def test_http_200_with_a_wrong_or_stale_page_is_a_failure(self, fetch) -> None:
        fetch.return_value = self.response(b"unrelated page")
        self.assertIn("content differs", self.check())

    @patch("scripts.verify_deployment.time.sleep")
    @patch("scripts.verify_deployment.urlopen")
    def test_retries_a_propagation_404_then_verifies_the_page(self, fetch, sleep) -> None:
        fetch.side_effect = [HTTPError("https://example.org/qr/paper/", 404, "missing", {}, None), self.response(b"expected page")]
        self.assertIsNone(self.check(attempts=2))
        self.assertEqual(fetch.call_count, 2)
        sleep.assert_called_once_with(5)
