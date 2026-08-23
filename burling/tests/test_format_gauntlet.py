"""Format gauntlet: every ingest path extract.py claims, proven on fixtures.

Fixtures come from tools/make_corpus.py (docs/test-corpus.md, Layer 2).
Offline-safe by construction — the OCR scan pair lives in a separate
fixture folder with its own skip-if-unavailable test.

No model. No GPU. No network.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from burling.extract import extract_text
from burling.queue import build_queue

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GAUNTLET = FIXTURES / "format-gauntlet"
OCR_DIR = FIXTURES / "format-gauntlet-ocr"
MARKER = "FORMAT GAUNTLET MARKER alpha bravo charlie"


def _queue_over_gauntlet(tmp_root: Path):
    intake = tmp_root / "intake"
    output = tmp_root / "output"
    shutil.copytree(GAUNTLET, intake)
    cfg = {
        "paths": {"intake_dir": str(intake), "output_dir": str(output)},
    }
    build_queue(cfg, intake=intake)
    from burling.ledger import load_ledger

    ledger = load_ledger(cfg)
    return {r["rel_path"]: r for r in ledger["documents"].values()}, output


class FormatQueueTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.rows, self.output = _queue_over_gauntlet(Path(self._tmp.name))

    def test_every_text_extension_reads_as_text(self) -> None:
        for ext in ("txt", "text", "md", "markdown", "csv", "log", "rst", "json", "xml", "yml", "yaml"):
            rel = f"text-exts/sample.{ext}"
            row = self.rows.get(rel)
            with self.subTest(ext=ext):
                self.assertIsNotNone(row, f"{rel} missing from queue")
                self.assertTrue(row["extraction"]["ok"], rel)
                self.assertEqual(row["extraction"]["method"], "text", rel)

    def test_html_office_and_pdf_rows(self) -> None:
        expected = {
            "page.html": "html",
            "doc.min.rtf": "rtf-basic",
            "doc.min.docx": "docx",
            "doc.min.pptx": "pptx",
            "doc.min.xlsx": "xlsx",
            "text-layer.pdf": "pypdf",
        }
        for rel, method in expected.items():
            row = self.rows[rel]
            with self.subTest(rel=rel):
                self.assertTrue(row["extraction"]["ok"], rel)
                self.assertEqual(row["extraction"]["method"], method, rel)

    def test_zip_members_replace_archive_and_junk_is_dropped(self) -> None:
        self.assertNotIn("benign.zip", self.rows)
        one = self.rows["benign.zip.unpacked/benign/a/b/one.txt"]
        self.assertTrue(one["extraction"]["ok"])
        self.assertGreater(one["char_count"], 0)
        self.assertIn("benign.zip.unpacked/benign/two.txt", self.rows)
        # Junk never becomes a queue row.
        for junk in (
            "benign.zip.unpacked/benign/.DS_Store",
            "benign.zip.unpacked/__MACOSX/benign_two.txt",
        ):
            self.assertNotIn(junk, self.rows)

    def test_unreadable_types_queue_but_fail_cleanly(self) -> None:
        for name in ("dummy.gif", "dummy.mp3", "dummy.exe"):
            row = self.rows[f"unreadable/{name}"]
            with self.subTest(fixture=name):
                self.assertFalse(row["extraction"]["ok"])
                self.assertIn("binary/unreadable", row["extraction"]["error"])

    def test_spaced_extension_normalizes_to_pdf(self) -> None:
        row = self.rows["quirk/report. pdf"]
        self.assertEqual(row["ext"], ".pdf")
        self.assertFalse(row["extraction"]["ok"])  # not a real PDF; fails cleanly

    def test_unicode_filename_and_deep_nesting_queue(self) -> None:
        self.assertTrue(self.rows["quirk/café-menu-éclair.txt"]["extraction"]["ok"])
        self.assertTrue(
            self.rows["quirk/deep/a/b/c/d/e/f/leaf.txt"]["extraction"]["ok"]
        )

    def test_browser_sidecar_files_are_skipped_entirely(self) -> None:
        self.assertIn("site/dashboard.html", self.rows)
        for skipped in ("site/dashboard_files/style.css", "site/dashboard_files/app.js"):
            self.assertNotIn(skipped, self.rows)


class DirectExtractionTests(unittest.TestCase):
    """extract_text-level assertions the queue rows cannot express."""

    def test_html_strips_script_style_and_tags(self) -> None:
        text, method = extract_text(GAUNTLET / "page.html")
        self.assertEqual(method, "html")
        self.assertIn(MARKER, text)
        self.assertNotIn("SCRIPT_NOISE_MUST_NOT_SURVIVE", text)
        self.assertNotIn("<p>", text)
        self.assertNotIn(".noise", text)

    def test_office_markers_survive(self) -> None:
        for name in ("doc.min.docx", "doc.min.pptx", "doc.min.xlsx", "doc.min.rtf"):
            with self.subTest(fixture=name):
                text, _ = extract_text(GAUNTLET / name)
                self.assertIn(MARKER, text)


class ZipCapTests(unittest.TestCase):
    """The documented caps fire. Attack zips are built here, never committed."""

    def _zip_with(self, members: list[tuple[str, bytes]]) -> tempfile.TemporaryDirectory:
        import zipfile

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        zip_path = Path(tmp.name) / "attack.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for name, data in members:
                zf.writestr(name, data)
        return tmp

    def test_member_count_cap(self) -> None:
        import burling.extract as ex

        members = [(f"m{i}.txt", b"x") for i in range(4)]
        tmp = self._zip_with(members)
        with mock.patch.object(ex, "MAX_ZIP_MEMBERS", 3):
            with self.assertRaisesRegex(ValueError, "cap is 3"):
                ex.safe_unpack_zip(Path(tmp.name) / "attack.zip")

    def test_member_size_cap(self) -> None:
        import burling.extract as ex

        tmp = self._zip_with([("big.bin", b"y" * 20)])
        with mock.patch.object(ex, "MAX_ZIP_MEMBER_BYTES", 8):
            with self.assertRaisesRegex(ValueError, "too large"):
                ex.safe_unpack_zip(Path(tmp.name) / "attack.zip")

    def test_total_size_cap(self) -> None:
        import burling.extract as ex

        members = [("a.bin", b"z" * 10), ("b.bin", b"z" * 10)]
        tmp = self._zip_with(members)
        with mock.patch.object(ex, "MAX_ZIP_TOTAL_BYTES", 16):
            with self.assertRaisesRegex(ValueError, "exceeds cap"):
                ex.safe_unpack_zip(Path(tmp.name) / "attack.zip")


class OcrOptionalTests(unittest.TestCase):
    """Scan pair lives apart so offline CI skips instead of flaking."""

    def setUp(self):
        if not (OCR_DIR / "scanned-no-text-layer.pdf").is_file():
            self.skipTest("scan fixtures not generated")
        try:
            from burling.ocr import _engine  # noqa: F401

            _engine()
        except Exception:
            self.skipTest("OCR engine unavailable (offline or model not fetched)")

    def test_scan_pdf_recovers_via_ocr(self) -> None:
        text, method = extract_text(OCR_DIR / "scanned-no-text-layer.pdf")
        self.assertTrue(method.startswith("ocr"), method)
        self.assertGreaterEqual(len(text.strip()), 30)

    def test_standalone_png_uses_image_ocr(self) -> None:
        text, method = extract_text(OCR_DIR / "scan-page.png")
        self.assertEqual(method, "ocr-image")
        self.assertTrue(text.strip())


if __name__ == "__main__":
    unittest.main()
