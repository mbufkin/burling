"""Locked / Drive (SECURED) PDFs must fail fast — never hang the run in OCR."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from burling.extract import extract_record, extract_text
from burling.layer_plan import _doc_text


class LockedPdfFilenameStubTests(unittest.TestCase):
    def test_encrypted_error_sends_filename_not_empty_body(self) -> None:
        # Best practice: the clerk still sees the Drive name (travel form)
        # and must not invent a body we could not read.
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp)
            locked = intake / "PATIN_TIVA-GRANT TRAVEL FORM (SECURED).pdf"
            locked.write_bytes(b"%PDF-1.4\n")
            rec = {
                "text": "",
                "extraction_ok": False,
                "extraction_error": "encrypted PDF (password protected)",
            }
            with patch("burling.layer_plan.extract_record", return_value=rec):
                with patch("burling.layer_plan.config_intake", return_value=intake):
                    with patch(
                        "burling.layer_plan._resolve_intake_file",
                        return_value=locked,
                    ):
                        text = _doc_text({}, locked.name)
        self.assertIn("FILE NAME ONLY", text)
        self.assertIn("GRANT TRAVEL", text)
        self.assertIn("encrypted PDF", text)

    def test_other_extract_failures_stay_empty_so_layers_unmaps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp)
            path = intake / "notes.zip"
            path.write_bytes(b"PK\x03\x04")
            rec = {
                "text": "",
                "extraction_ok": False,
                "extraction_error": "zip unpacked; members are inventoried separately",
            }
            with patch("burling.layer_plan.extract_record", return_value=rec):
                with patch("burling.layer_plan.config_intake", return_value=intake):
                    with patch(
                        "burling.layer_plan._resolve_intake_file",
                        return_value=path,
                    ):
                        text = _doc_text({}, path.name)
        self.assertEqual(text, "")


class LockedPdfExtractTests(unittest.TestCase):
    def test_pdftotext_password_stderr_raises_encrypted(self) -> None:
        # This box often has poppler but not pypdf. Password stderr must not
        # fall through to OCR.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "travel-form.pdf"
            path.write_bytes(b"%PDF-1.4\n")
            fake = type(
                "R",
                (),
                {
                    "returncode": 1,
                    "stdout": "",
                    "stderr": "Command Line Error: Incorrect password\n",
                },
            )()
            with patch("burling.extract._pdf_lock_error", return_value=None):
                with patch(
                    "burling.extract._extract_pdf_pypdf",
                    side_effect=ImportError("no pypdf"),
                ):
                    with patch("burling.extract.subprocess.run", return_value=fake):
                        with self.assertRaises(ValueError) as ctx:
                            extract_text(path)
            self.assertIn("encrypted PDF", str(ctx.exception))

    def _write_passworded(self, dest: Path, password: str) -> None:
        try:
            from pypdf import PdfWriter
        except ImportError:
            self.skipTest("pypdf not installed")
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.encrypt(password)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as fh:
            writer.write(fh)

    def test_real_password_does_not_extract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "travel-form.pdf"
            self._write_passworded(path, "secret")
            with self.assertRaises(ValueError) as ctx:
                extract_text(path)
            self.assertIn("encrypted PDF", str(ctx.exception))
            rec = extract_record(path, Path(tmp))
            self.assertFalse(rec["extraction_ok"])
            self.assertIn("encrypted", rec["extraction_error"] or "")


if __name__ == "__main__":
    unittest.main()
