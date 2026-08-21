"""Shared review ledger. Every later pass reads this instead of re-opening files.

Loom Bet 9: extract once, accumulate decisions in one table. Downstream stages
do not re-interpret raw source independently — that is how drift starts.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from burling.io_util import atomic_write_json, load_json
from burling.paths import output_dir

LEDGER_NAME = "ledger.json"
QUEUE_NAME = "queue.json"


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def file_fingerprint(path: Path) -> str:
    """Hash path + size + mtime so a replaced file with the same name is re-read."""
    st = path.stat()
    blob = f"{path.resolve()}|{st.st_size}|{st.st_mtime_ns}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def ledger_path(cfg: dict) -> Path:
    return output_dir(cfg) / LEDGER_NAME


def queue_path(cfg: dict) -> Path:
    return output_dir(cfg) / QUEUE_NAME


def load_ledger(cfg: dict) -> dict:
    data = load_json(ledger_path(cfg), {"version": 1, "documents": {}, "intake": None})
    data.setdefault("documents", {})
    return data


def save_ledger(cfg: dict, ledger: dict) -> None:
    atomic_write_json(ledger_path(cfg), ledger)


def existing_doc_id(ledger: dict, rel_path: str) -> str | None:
    """Stable identity is the file path in the dump, not the extract hash.

    Best practice: when OCR later succeeds on a scan that failed yesterday,
    keep the same ledger row. The hash tells us *whether* to re-tag, not
    *who* the document is. A new hash must not mint a second ghost record.
    """
    for row in (ledger.get("documents") or {}).values():
        if row.get("rel_path") == rel_path and row.get("doc_id"):
            return str(row["doc_id"])
    return None


def upsert(ledger: dict, doc_id: str, **fields) -> dict:
    row = ledger["documents"].setdefault(doc_id, {"doc_id": doc_id})
    row.update(fields)
    return row
