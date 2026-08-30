from __future__ import annotations

from pathlib import Path
import unittest

import make_branded_qr_codes as branded


REPO_ROOT = Path(__file__).resolve().parents[1]


class BrandedGeneratorTests(unittest.TestCase):
    def test_branded_generator_uses_portable_repository_paths(self) -> None:
        self.assertEqual(branded.OUTDIR, REPO_ROOT / "current")
        self.assertEqual(branded.COMPHY_MARK, REPO_ROOT / "assets" / "comphy-lab-mark.png")
        self.assertTrue(branded.COMPHY_MARK.is_file())

    def test_checked_in_branded_svgs_match_the_generator(self) -> None:
        for asset in branded.ASSETS:
            with self.subTest(asset=asset.stem):
                svg = branded.OUTDIR / f"{asset.stem}.svg"
                self.assertEqual(svg.read_text(encoding="utf-8"), branded._svg_for(asset))
