"""OCR flatten for scanned PDFs. Uses a real corpus file if present; otherwise skips."""

from __future__ import annotations

import unittest
from pathlib import Path

from burling.ocr import _enough, flatten_pdf


class OcrTests(unittest.TestCase):
    def test_enough_ignores_whitespace(self) -> None:
        self.assertFalse(_enough(" \n \n"))
        self.assertTrue(_enough("Guest room, 2 Queen " * 3))

    def test_flatten_scanned_hotel_folio_if_present(self) -> None:
        # NAF Hotel.pdf is a scan pypdf reads as empty. OCR should recover stay dates.
        root = Path(__file__).resolve().parents[1] / "corpus"
        pdf = root / "NAF Hotel.pdf"
        if not pdf.exists():
            self.skipTest("corpus not on this machine")
        text, method = flatten_pdf(pdf)
        self.assertEqual(method, "ocr")
        self.assertGreater(len(text), 30)
        self.assertTrue("Gaylord" in text or "Jul" in text or "2026" in text, text[:400])


if __name__ == "__main__":
    unittest.main()
