"""Pull plain text out of common office, PDF, image, and zip file types.

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
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
ARCHIVE_EXTENSIONS = {".zip"}

# Still queued, but we do not pretend to read installers or media.
UNREADABLE_EXTENSIONS = {
    ".gif", ".svg", ".ico", ".heic",
    ".mp3", ".mp4", ".wav", ".mov", ".avi",
    ".gz", ".tar", ".7z", ".rar",
    ".exe", ".dll", ".msi", ".iso", ".dmg", ".pkg",
}

# Zip-slip + zip-bomb caps. A handover zip is tens of PDFs, not gigabytes.
MAX_ZIP_MEMBERS = 200
MAX_ZIP_MEMBER_BYTES = 80 * 1024 * 1024
MAX_ZIP_TOTAL_BYTES = 400 * 1024 * 1024
UNPACK_SUFFIX = ".unpacked"

SKIP_NAMES = {".gitkeep", "README.md"}
SKIP_EXTENSIONS = {".js", ".css", ".map", ".woff", ".woff2"}


def _is_browser_sidecar(path: Path) -> bool:
    """Chrome 'Save Page' dumps a foo.pdf_files/ folder of bootstrap JS. Not a record."""
    return any(part.endswith("_files") for part in path.parts)


def _norm_ext(path: Path) -> str:
    """Lowercase suffix; treat ``file. pdf`` as ``.pdf``."""
    return path.suffix.lower().replace(" ", "")


def _unpack_dest(zip_path: Path) -> Path:
    return zip_path.with_name(zip_path.name + UNPACK_SUFFIX)


def _safe_zip_target(dest_root: Path, member_name: str) -> Path | None:
    """Resolve a zip member under dest_root, or None if it is a zip-slip path.

    Best practice: never trust ``ZipInfo.filename``. Attack zips use
    ``../`` or absolute paths to write outside the unpack folder.
    """
    name = member_name.replace("\\", "/").lstrip("/")
    if not name or name.endswith("/"):
        return None
    if name.startswith("__MACOSX/") or Path(name).name in {".DS_Store", ".DS_Store"}:
        return None
    if Path(name).name.startswith("._"):
        return None
    dest_root = dest_root.resolve()
    target = (dest_root / name).resolve()
    try:
        target.relative_to(dest_root)
    except ValueError:
        return None
    return target


def safe_unpack_zip(zip_path: Path, dest: Path | None = None) -> list[Path]:
    """Unpack a zip next to itself. Returns written member paths.

    Idempotent: a non-empty dest is reused. Members stay first-class files
    so a TB-results zip becomes 24 PDFs on the map, not one blob.
    """
    dest = dest or _unpack_dest(zip_path)
    if dest.is_dir() and any(dest.rglob("*")):
        return sorted(p for p in dest.rglob("*") if p.is_file())
    dest.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    total = 0
    with zipfile.ZipFile(zip_path) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > MAX_ZIP_MEMBERS:
            raise ValueError(f"zip has {len(infos)} members; cap is {MAX_ZIP_MEMBERS}")
        for info in infos:
            target = _safe_zip_target(dest, info.filename)
            if target is None:
                continue
            size = int(info.file_size or 0)
            if size > MAX_ZIP_MEMBER_BYTES:
                raise ValueError(f"zip member too large: {info.filename}")
            total += size
            if total > MAX_ZIP_TOTAL_BYTES:
                raise ValueError("zip uncompressed size exceeds cap")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as src, target.open("wb") as out:
                out.write(src.read())
            written.append(target)
    return written


def iter_source_files(sources: Path) -> list[Path]:
    """Recursive inventory. Nested folders are the normal case for a handover dump.

    ``.zip`` files are unpacked beside themselves (``name.zip.unpacked/``).
    Members replace the archive in the queue so each PDF inside is tagged.
    """
    if not sources.is_dir():
        return []
    for p in sorted(sources.rglob("*")):
        if not p.is_file() or _norm_ext(p) not in ARCHIVE_EXTENSIONS:
            continue
        if any(part.endswith(UNPACK_SUFFIX) for part in p.parts):
            continue
        try:
            safe_unpack_zip(p)
        except Exception:
            # Leave the zip in the inventory; extract_text records the error.
            continue
    out: list[Path] = []
    for p in sorted(sources.rglob("*")):
        if not p.is_file() or p.name.startswith("."):
            continue
        if p.name in SKIP_NAMES and p.parent == sources:
            continue
        if _norm_ext(p) in SKIP_EXTENSIONS:
            continue
        if _is_browser_sidecar(p):
            continue
        if _norm_ext(p) in ARCHIVE_EXTENSIONS:
            dest = _unpack_dest(p)
            if dest.is_dir() and any(dest.rglob("*")):
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


def _pdf_lock_error(path: Path) -> str | None:
    """If this PDF is password-locked after the empty-user-password try, say so.

    Best practice: Drive ``(SECURED)`` copies often encrypt with an empty user
    password — those we unlock. A real password must not fall through to OCR
    (rasterizing a locked file can hang the whole run).
    """
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        if getattr(reader, "is_encrypted", False):
            try:
                unlocked = reader.decrypt("")
            except Exception as exc:
                if "cryptography" in str(exc).lower():
                    return "encrypted PDF needs `pip install cryptography`"
                return "encrypted PDF (password protected)"
            if unlocked == 0:
                return "encrypted PDF (password protected)"
    except Exception:
        pass
    try:
        import pymupdf

        doc = pymupdf.open(path)
        try:
            if doc.is_encrypted and not doc.authenticate(""):
                return "encrypted PDF (password protected)"
        finally:
            doc.close()
    except Exception:
        pass
    return None


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


def _pdftotext_run(path: Path, extra_args: list[str] | None = None) -> tuple[str, str]:
    """Cheap poppler extract. Empty ``-upw`` unlocks Drive (SECURED) copies.

    Best practice: try this before OCR. Rasterizing a locked PDF is how one
    file kills an 871-file run.
    """
    args = ["pdftotext", *(extra_args or []), str(path), "-"]
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except FileNotFoundError:
        return "", ""
    except subprocess.TimeoutExpired as exc:
        raise ValueError("PDF extract timed out") from exc
    err = ((result.stderr or "") + (result.stdout or "")).lower()
    if result.returncode != 0:
        if "password" in err or "encrypted" in err:
            raise ValueError("encrypted PDF (password protected)")
        return "", err
    return result.stdout or "", ""


def _extract_pdf_pdftotext(path: Path) -> str:
    text, err = _pdftotext_run(path)
    if _enough_text(text):
        return text
    # Adobe signed / Drive (SECURED) often use an empty user password.
    text, err = _pdftotext_run(path, ["-upw", ""])
    if _enough_text(text):
        return text
    if "password" in err or "encrypted" in err:
        raise ValueError("encrypted PDF (password protected)")
    return text


def _extract_pdf(path: Path) -> tuple[str, str]:
    """Text layer first, then local OCR for scans. Never send the PDF to a cloud API.

    Locked PDFs stop here. Best practice: one passworded travel form must not
    take down an 871-file run by falling into OCR.
    """
    locked = _pdf_lock_error(path)
    if locked:
        raise ValueError(locked)

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
        # Fall through to pdftotext / OCR; some broken PDFs still rasterize.
        text = ""

    # Cheap CLI before RapidOCR. Empty-password (SECURED) copies unlock here.
    try:
        cli = _extract_pdf_pdftotext(path)
        if _enough_text(cli):
            return cli, "pdftotext"
    except ValueError:
        raise

    try:
        from burling.ocr import flatten_pdf

        return flatten_pdf(path)
    except ValueError:
        raise
    except Exception as ocr_exc:
        if _enough_text(text):
            return text, "pypdf"
        raise ValueError(f"no text layer and OCR failed: {ocr_exc}") from ocr_exc


def _strip_html(html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>[\s\S]*?</\1>", " ", html, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_text(path: Path) -> tuple[str, str]:
    ext = _norm_ext(path)

    if ext in ARCHIVE_EXTENSIONS:
        dest = _unpack_dest(path)
        if dest.is_dir() and any(dest.rglob("*")):
            raise ValueError("zip already unpacked; members are inventoried separately")
        try:
            written = safe_unpack_zip(path, dest)
        except Exception as exc:
            raise ValueError(f"zip could not be unpacked: {exc}") from exc
        if not written:
            raise ValueError("zip unpacked but contained no safe members")
        raise ValueError("zip unpacked; members are inventoried separately")

    if ext in IMAGE_EXTENSIONS:
        from burling.ocr import ocr_image

        text = ocr_image(path)
        if _enough_text(text):
            return text, "ocr-image"
        raise ValueError("image OCR produced no usable text")

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
    ext = _norm_ext(path)
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
