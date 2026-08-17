"""Pull plain text out of common handover file types.

Best practice: keep extraction deterministic and dependency-light. Office files
are ZIP+XML, so the stdlib is enough. PDFs try pypdf first (Windows-friendly),
then pdftotext if it is on PATH. Binary leftovers are recorded as extraction
failures so the queue still lists them for a human — we never silently drop a file.
"""

from __future__ import annotations

import re
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

TEXT_EXTENSIONS = {".txt", ".text", ".md", ".markdown", ".csv", ".log", ".rst", ".json", ".xml", ".yml", ".yaml"}
HTML_EXTENSIONS = {".html", ".htm"}
PDF_EXTENSIONS = {".pdf"}

# Images and archives still enter the queue so the map is complete, but we do
# not pretend we can read them without OCR.
UNREADABLE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".heic",
    ".mp3", ".mp4", ".wav", ".mov", ".avi",
    ".zip", ".gz", ".tar", ".7z", ".rar",
    ".exe", ".dll", ".msi", ".iso", ".dmg", ".pkg",
}

SKIP_NAMES = {".gitkeep", "README.md"}
SKIP_EXTENSIONS = {".js", ".css", ".map", ".woff", ".woff2"}


def _is_browser_sidecar(path: Path) -> bool:
    """Chrome 'Save Page' dumps a foo.pdf_files/ folder of bootstrap JS. Not a record."""
    return any(part.endswith("_files") for part in path.parts)


def iter_source_files(sources: Path) -> list[Path]:
    """Recursive inventory. Nested folders are the normal case for a handover dump."""
    if not sources.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(sources.rglob("*")):
        if not p.is_file() or p.name.startswith("."):
            continue
        if p.name in SKIP_NAMES and p.parent == sources:
            continue
        if p.suffix.lower() in SKIP_EXTENSIONS:
            continue
        if _is_browser_sidecar(p):
            continue
        out.append(p)
    return out


def _xml_texts(root: ET.Element, tag_local: str) -> list[str]:
    parts: list[str] = []
    for el in root.iter():
        if el.tag.endswith(tag_local):
            if el.text:
                parts.append(el.text)
            if el.tail:
                parts.append(el.tail)
    return parts


def _extract_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    return "\n".join(_xml_texts(root, "t"))


def _extract_pptx(path: Path) -> str:
    chunks: list[str] = []
    with zipfile.ZipFile(path) as zf:
        slide_names = sorted(
            n for n in zf.namelist()
            if n.startswith("ppt/slides/slide") and n.endswith(".xml")
        )
        for name in slide_names:
            root = ET.fromstring(zf.read(name))
            chunks.append("\n".join(_xml_texts(root, "t")))
    return "\n\n".join(chunks)


def _extract_xlsx(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        if "xl/sharedStrings.xml" not in zf.namelist():
            return ""
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    return "\n".join(_xml_texts(root, "t"))


def _enough_text(text: str) -> bool:
    """A few whitespace characters from an empty text layer do not count as a read."""
    return len((text or "").strip()) >= 30


def _extract_pdf_pypdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    # Adobe "signed" travel forms often encrypt with an empty user password.
    # Best practice: try empty, then fail with a clear error so filename
    # search still works. Do not guess other passwords.
    if getattr(reader, "is_encrypted", False):
        try:
            unlocked = reader.decrypt("")
        except Exception as exc:
            msg = str(exc).lower()
            if "cryptography" in msg:
                raise ValueError(
                    "encrypted PDF needs `pip install cryptography`"
                ) from exc
            raise ValueError("encrypted PDF (password protected)") from exc
        if unlocked == 0:
            raise ValueError("encrypted PDF (password protected)")
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def _extract_pdf(path: Path) -> tuple[str, str]:
    """Text layer first, then local OCR for scans. Never send the PDF to a cloud API."""
    text = ""
    try:
        text = _extract_pdf_pypdf(path)
        if _enough_text(text):
            return text, "pypdf"
    except ValueError:
        raise
    except ImportError:
        pass
    except Exception as exc:
        if "cryptography" in str(exc).lower():
            raise ValueError("encrypted PDF needs `pip install cryptography`") from exc
        # Fall through to PyMuPDF / OCR; some broken PDFs still rasterize.
        text = ""

    try:
        from burling.ocr import flatten_pdf

        return flatten_pdf(path)
    except Exception as ocr_exc:
        if _enough_text(text):
            return text, "pypdf"
        try:
            result = subprocess.run(
                ["pdftotext", str(path), "-"],
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            )
            if _enough_text(result.stdout):
                return result.stdout, "pdftotext"
        except FileNotFoundError:
            pass
        raise ValueError(f"no text layer and OCR failed: {ocr_exc}") from ocr_exc


def _strip_html(html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>[\s\S]*?</\1>", " ", html, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_text(path: Path) -> tuple[str, str]:
    ext = path.suffix.lower()

    if ext in UNREADABLE_EXTENSIONS:
        raise ValueError(f"binary/unreadable type {ext} — queued for human review, not model read")

    if ext in TEXT_EXTENSIONS:
        return path.read_text(encoding="utf-8", errors="replace"), "text"

    if ext in HTML_EXTENSIONS:
        return _strip_html(path.read_text(encoding="utf-8", errors="replace")), "html"

    if ext == ".docx":
        return _extract_docx(path), "docx"
    if ext == ".pptx":
        return _extract_pptx(path), "pptx"
    if ext == ".xlsx":
        return _extract_xlsx(path), "xlsx"
    if ext in PDF_EXTENSIONS:
        return _extract_pdf(path)

    if ext == ".rtf":
        raw = path.read_text(encoding="utf-8", errors="replace")
        text = re.sub(r"\\[a-z]+\d* ?", " ", raw)
        text = re.sub(r"[{}]", "", text)
        return text, "rtf-basic"

    try:
        raw = path.read_text(encoding="utf-8", errors="strict")
        if raw.strip():
            return raw, "text-fallback"
    except (UnicodeDecodeError, OSError):
        pass

    raise ValueError(f"unsupported or binary file type: {ext or '(no extension)'}")


def extract_record(path: Path, intake_root: Path) -> dict:
    """One file → extraction record. Failures stay in the queue instead of vanishing."""
    rel = path.relative_to(intake_root).as_posix()
    ext = path.suffix.lower()
    base = {
        "rel_path": rel,
        "ext": ext,
        "size_bytes": path.stat().st_size,
        "text": "",
        "extraction_ok": False,
        "extraction_method": "failed",
        "extraction_error": None,
    }
    try:
        text, method = extract_text(path)
    except Exception as exc:
        base["extraction_error"] = str(exc)
        return base
    if not text.strip():
        base["extraction_error"] = "no text extracted"
        base["extraction_method"] = method
        return base
    base.update(
        {
            "text": text,
            "extraction_ok": True,
            "extraction_method": method,
        }
    )
    return base
