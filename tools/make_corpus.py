#!/usr/bin/env python3
"""Deterministic synthetic corpus generator (docs/test-corpus.md).

Writes the fixture layers the test suite runs against. Seeded, offline,
no real identifiers: 555-01xx phones, example.com addresses, SSNs in
ranges SSA never issued (000/900) or the CONTRIBUTING-blessed document
example 123-45-6789. Run once; commit the output.

    python tools/make_corpus.py            # writes every implemented layer
    python tools/make_corpus.py --layer pii-matrix

Layers:
  pii-matrix           Layer 1 of docs/test-corpus.md — one positive and one
                       negative per priors.py detection class, plus filename-hint
                       and clean controls. Plain text, KB-scale.
  format-gauntlet      Layer 2 — every offline ingest path extract.py claims:
                       all text extensions, html stripping, rtf/docx/pptx/xlsx,
                       a hand-assembled text-layer PDF, a benign zip with junk
                       entries, unreadable dummies, and filename quirks.
  format-gauntlet-ocr  Layer 2 continuation — image-only scan PDF + PNG in
                       their own folder so offline CI can skip OCR cleanly.
"""

from __future__ import annotations

import argparse
import io
import zipfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
FIXTURES = PROJECT / "burling" / "tests" / "fixtures"

# ---------------------------------------------------------------------------
# Layer 1: PII / severity matrix. Each file isolates exactly one behavior in
# burling/priors.py. Expectations are mirrored in test_pii_matrix.py — keep
# the two in sync when editing content here.
# ---------------------------------------------------------------------------

PII_MATRIX: dict[str, str] = {
    # HIGH severity: formatted SSN (CONTRIBUTING.md-blessed example).
    "pii-ssn-formatted.txt": (
        "New hire onboarding checklist for Alex Rivera.\n"
        "SSN: 123-45-6789\n"
        "Badge photo attached to the personnel file.\n"
    ),
    # HIGH: bare 9-digit block INSIDE the SSN keyword window.
    "pii-ssn-keyword-blob.txt": (
        "HR note: the applicant's social security number is 447038211\n"
        "per the signed verification form.\n"
    ),
    # Negative control: same 9 digits, no keyword anywhere near it.
    "pii-neg-order-number.txt": (
        "Facilities log: order number 447038211 shipped Tuesday.\n"
        "Pallet went to the loading dock without incident.\n"
    ),
    # HIGH: Luhn-valid card (industry-standard test PAN).
    "pii-cc-luhn-valid.txt": (
        "Procurement memo. Corporate card on file:\n"
        "4111 1111 1111 1111\n"
        "Expires next fiscal year; limit unchanged.\n"
    ),
    # Negative control: same shape, fails the Luhn checksum.
    "pii-cc-luhn-invalid.txt": (
        "Draft entry from the expense workshop demo:\n"
        "4111 1111 1111 1112\n"
        "Not a real card; typing practice only.\n"
    ),
    # MEDIUM: DOB requires its keyword prefix.
    "pii-dob-keyword.txt": (
        "Benefits enrollment worksheet.\n"
        "Date of birth: 04/12/1988\n"
        "Plan tier unchanged from last year.\n"
    ),
    # Negative control: identical date, no keyword prefix.
    "pii-neg-bare-date.txt": (
        "Calendar note: the audit kickoff moved to 04/12/1988.\n"
        "Room booked; dial-in unchanged.\n"
    ),
    # MEDIUM: three phone formats the regex must all catch.
    "pii-phone-formats.txt": (
        "Emergency contact card for the front office.\n"
        "Primary: (214) 555-0142\n"
        "Mobile: +1 214-555-0142\n"
        "Fax line: 2145550142\n"
    ),
    # MEDIUM: street-suffix address match.
    "pii-address-street.txt": (
        "Delivery instructions left by the previous coordinator:\n"
        "Ring the bell at 3505 Mockingbird Lane.\n"
    ),
    # MEDIUM: PO box plus state+ZIP both land in the address bucket.
    "pii-address-po-box.txt": (
        "Mail routing card.\n"
        "P.O. Box 1234, Dallas, TX 75201\n"
    ),
    # MEDIUM: email with a plus tag survives the regex.
    "pii-email-plus.txt": (
        "Newsletter signup used alex+signup@example.com\n"
        "Unsubscribe handled at the list level.\n"
    ),
    # MEDIUM: sensitive keywords only — no identifier shapes at all.
    "pii-keywords-confidential.txt": (
        "Sticky note found in the top drawer:\n"
        "api key rotated quarterly; password hint is the usual one.\n"
        "Treat this page as confidential.\n"
    ),
    # Filename-hint path: body is clean, the NAME carries tax_financial.
    "hint-filename-w2.txt": (
        "Scanned cover sheet. The interesting numbers live in the\n"
        "attached payroll packet, not on this page.\n"
    ),
    # Global negative control: nothing fires, file still queues cleanly.
    "pii-neg-clean-meeting.md": (
        "# Curriculum planning\n\n"
        "- Draft the fall schedule\n"
        "- Confirm the guest speaker\n"
        "- Book room 204\n"
    ),
}

# ---------------------------------------------------------------------------
# Layer 2: format gauntlet. Every ingest bucket extract.py documents, plus
# the quirks. Expectations mirrored in test_format_gauntlet.py.
# ---------------------------------------------------------------------------

MARKER = "FORMAT GAUNTLET MARKER alpha bravo charlie"
TEXT_EXTS = ("txt", "text", "md", "markdown", "csv", "log", "rst", "json", "xml", "yml", "yaml")


def _marker(note: str) -> str:
    return f"{MARKER} via {note}.\n"


def _minimal_pdf(lines: list[str]) -> bytes:
    """Hand-assembled one-page PDF with a real Helvetica text layer."""
    escaped = [l.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for l in lines]
    content = "\n".join(
        f"BT /F1 14 Tf 72 {720 - i * 22} Td ({line}) Tj ET" for i, line in enumerate(escaped)
    ).encode("latin-1")
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R"
        b"/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length " + str(len(content)).encode() + b">>stream\n" + content + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for num, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{num} 0 obj".encode() + body + b"endobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer<</Size {len(objects) + 1}/Root 1 0 R>>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    )
    return bytes(out)


def _office_zip(members: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, xml in members.items():
            zi = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            zi.external_attr = 0o644 << 16
            zf.writestr(zi, xml)
    return buf.getvalue()


def _build_format_gauntlet(out: Path) -> None:
    text_exts_dir = out / "text-exts"
    text_exts_dir.mkdir(parents=True, exist_ok=True)
    for ext in TEXT_EXTS:
        (text_exts_dir / f"sample.{ext}").write_text(_marker(f"the .{ext} reader"), encoding="utf-8")

    (out / "page.html").write_text(
        "<!doctype html><html><head><title>Dashboard</title>"
        "<style>.noise{color:red}</style>"
        "<script>var leak = 'SCRIPT_NOISE_MUST_NOT_SURVIVE';</script></head>"
        "<body><nav>Home About Contact</nav>"
        f"<main><p>{MARKER} in the body copy.</p></main></body></html>",
        encoding="utf-8",
    )

    (out / "doc.min.rtf").write_text(
        "{\\rtf1\\ansi FORMAT GAUNTLET MARKER alpha bravo charlie in rich text.\\par}",
        encoding="utf-8",
    )
    w_ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    (out / "doc.min.docx").write_bytes(
        _office_zip(
            {
                "[Content_Types].xml": "<?xml version='1.0'?><Types/>",
                "word/document.xml": (
                    f"<?xml version='1.0'?><w:document {w_ns}><w:body>"
                    f"<w:p><w:r><w:t>{MARKER} in word body.</w:t></w:r></w:p>"
                    "</w:body></w:document>"
                ),
            }
        )
    )
    (out / "doc.min.pptx").write_bytes(
        _office_zip(
            {
                "ppt/slides/slide1.xml": (
                    "<?xml version='1.0'?><slides xmlns:a='http://schemas.openxmlformats.org/drawingml/2006/main'>"
                    f"<body><a:p><a:r><a:t>{MARKER} on slide one.</a:t></a:r></a:p></body></slides>"
                ),
            }
        )
    )
    (out / "doc.min.xlsx").write_bytes(
        _office_zip(
            {
                "xl/sharedStrings.xml": (
                    "<?xml version='1.0'?><sst>"
                    f"<si><t>{MARKER} in shared strings.</t></si></sst>"
                ),
            }
        )
    )

    (out / "text-layer.pdf").write_bytes(
        _minimal_pdf([MARKER, "Second line for the pypdf reader."])
    )

    with zipfile.ZipFile(out / "benign.zip", "w") as zf:
        def add(name: str, data: bytes) -> None:
            zi = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            zi.external_attr = 0o644 << 16
            zf.writestr(zi, data)

        add("benign/a/b/one.txt", MARKER.encode())
        add("benign/two.txt", b"second queued member\n")
        add("benign/.DS_Store", b"")              # finder junk: never written
        add("__MACOSX/benign_two.txt", b"junk")   # resource fork: never written

    unreadable = out / "unreadable"
    unreadable.mkdir(exist_ok=True)
    for name, magic in (
        ("dummy.gif", b"GIF89a\x01"),
        ("dummy.mp3", b"ID3\x03\x00"),
        ("dummy.exe", b"MZ\x90\x00"),
    ):
        (unreadable / name).write_bytes(magic + b"\x00" * 4)

    quirk = out / "quirk"
    (quirk / "deep" / "a" / "b" / "c" / "d" / "e" / "f").mkdir(parents=True, exist_ok=True)
    (quirk / "deep" / "a" / "b" / "c" / "d" / "e" / "f" / "leaf.txt").write_text(
        _marker("six-deep nesting"), encoding="utf-8"
    )
    (quirk / "caf\u00e9-menu-\u00e9clair.txt").write_text(
        _marker("unicode filenames"), encoding="utf-8"
    )
    (quirk / "report. pdf").write_bytes(b"%PDF-not-really\x00garbage")

    site = out / "site"
    (site / "dashboard_files").mkdir(parents=True, exist_ok=True)
    (site / "dashboard.html").write_text(_marker("saved web page"), encoding="utf-8")
    (site / "dashboard_files" / "style.css").write_text(".x{color:red}", encoding="utf-8")
    (site / "dashboard_files" / "app.js").write_text("console.log(1);", encoding="utf-8")


def _build_format_gauntlet_ocr(out: Path) -> bool:
    """Image-only scan PDF + its source PNG. Needs pymupdf to render."""
    try:
        import pymupdf
    except ImportError:
        print("format-gauntlet-ocr: pymupdf unavailable, scan fixtures skipped")
        return False
    out.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_textbox(
        pymupdf.Rect(72, 72, 540, 500),
        "FORMAT GAUNTLET\nSCAN ONLY PAGE\nNO TEXT LAYER HERE",
        fontname="helv",
        fontsize=30,
    )
    png = out / "scan-page.png"
    page.get_pixmap(dpi=150).save(str(png))
    doc.close()
    sdoc = pymupdf.open()
    spage = sdoc.new_page(width=612, height=792)
    spage.insert_image(spage.rect, filename=str(png))
    sdoc.save(str(out / "scanned-no-text-layer.pdf"))
    sdoc.close()
    return True


LAYERS = {
    "pii-matrix": (PII_MATRIX, FIXTURES / "pii-matrix"),
}


def write_layer(files: dict[str, str], out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (out / name).write_text(content, encoding="utf-8")
    return len(files)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--layer",
        choices=["all", "pii-matrix", "format-gauntlet", "format-gauntlet-ocr"],
        help="write one layer only (default: all)",
    )
    args = parser.parse_args()

    if args.layer in (None, "all", "pii-matrix"):
        n = write_layer(PII_MATRIX, FIXTURES / "pii-matrix")
        print(f"pii-matrix: wrote {n} file(s) → burling/tests/fixtures/pii-matrix")
    if args.layer in (None, "all", "format-gauntlet"):
        _build_format_gauntlet(FIXTURES / "format-gauntlet")
        print("format-gauntlet: wrote → burling/tests/fixtures/format-gauntlet")
    if args.layer in (None, "all", "format-gauntlet-ocr"):
        if _build_format_gauntlet_ocr(FIXTURES / "format-gauntlet-ocr"):
            print("format-gauntlet-ocr: wrote → burling/tests/fixtures/format-gauntlet-ocr")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
