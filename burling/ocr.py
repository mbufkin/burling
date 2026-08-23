"""Local OCR for scanned PDFs that have no text layer.

Best practice: try cheap text extract first (pypdf / PyMuPDF). Only rasterize
and OCR when that is empty. Cache the result so a 40 MB camp packet is not
re-OCRed on every resume. Run on CPU so the 7B can keep the GPU.

We cap pages. A 200-page scan will not fit the 7B anyway; the first pages are
enough to decide personal vs work.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from burling.paths import PACKAGE_DIR

MAX_OCR_PAGES = 12
RENDER_SCALE = 2.0  # ~144 dpi. Higher is slower and rarely helps the 7B.
MIN_CHARS = 30
CACHE_DIR = PACKAGE_DIR / "output" / "ocr-cache"

_ENGINE = None


def _enough(text: str) -> bool:
    return len((text or "").strip()) >= MIN_CHARS


def _cache_key(path: Path) -> str:
    st = path.stat()
    blob = f"{path.resolve()}|{st.st_size}|{st.st_mtime_ns}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _cache_path(path: Path) -> Path:
    return CACHE_DIR / f"{_cache_key(path)}.txt"


def _engine():
    """Load RapidOCR once. Model download happens on first use, then stays on disk."""
    global _ENGINE
    if _ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR

        _ENGINE = RapidOCR()
    return _ENGINE


def pymupdf_text(path: Path) -> str:
    """Text layer via PyMuPDF. Recovers some PDFs pypdf reports as empty (CID fonts)."""
    import pymupdf

    doc = pymupdf.open(path)
    try:
        parts = [(page.get_text("text") or "") for page in doc]
    finally:
        doc.close()
    return "\n".join(parts)


def ocr_pdf(path: Path, *, max_pages: int = MAX_OCR_PAGES) -> str:
    """Rasterize pages and OCR. CPU only. Reads/writes the cache."""
    cached = _cache_path(path)
    if cached.exists():
        return cached.read_text(encoding="utf-8", errors="replace")

    import numpy as np
    import pymupdf

    engine = _engine()
    doc = pymupdf.open(path)
    lines: list[str] = []
    try:
        n = min(doc.page_count, max_pages)
        for i in range(n):
            pix = doc[i].get_pixmap(matrix=pymupdf.Matrix(RENDER_SCALE, RENDER_SCALE), alpha=False)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            result, _elapsed = engine(img)
            if not result:
                continue
            for row in result:
                if len(row) >= 2 and row[1]:
                    lines.append(str(row[1]))
            lines.append("")
        if doc.page_count > max_pages:
            lines.append(f"[ocr truncated after {max_pages} of {doc.page_count} pages]")
    finally:
        doc.close()

    text = "\n".join(lines).strip()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_text(text, encoding="utf-8")
    return text


def ocr_image(path: Path) -> str:
    """OCR a standalone photo (signage, scan, screenshot). Same engine as PDFs.

    Best practice: cache by file fingerprint so a folder of 48 PNGs is not
    re-OCRed every resume. CPU only.
    """
    cached = _cache_path(path)
    if cached.exists():
        return cached.read_text(encoding="utf-8", errors="replace")

    import cv2

    engine = _engine()
    arr = cv2.imread(str(path))
    if arr is None:
        raise ValueError(f"could not read image {path.name}")
    result, _elapsed = engine(arr)
    lines: list[str] = []
    if result:
        for row in result:
            if len(row) >= 2 and row[1]:
                lines.append(str(row[1]))
    text = "\n".join(lines).strip()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_text(text, encoding="utf-8")
    return text


def flatten_pdf(path: Path) -> tuple[str, str]:
    """Return (text, method) for a PDF, OCR-ing only when the text layer is empty."""
    try:
        layered = pymupdf_text(path)
    except Exception:
        layered = ""
    if _enough(layered):
        return layered, "pymupdf"

    try:
        ocred = ocr_pdf(path)
    except Exception as exc:
        raise ValueError(f"ocr failed: {exc}") from exc
    if _enough(ocred):
        return ocred, "ocr"
    return ocred, "ocr-empty"
