"""Build and resume the one-file-at-a-time queue (Loom Bet 6).

Unattended runs die. The queue must restart at item 211 of 300, not from zero.
Cache key is content_hash: if the file did not change, we do not spend another
model call.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from burling.extract import extract_record, iter_source_files
from burling.io_util import atomic_write_json, load_json
from burling.ledger import (
    content_hash,
    file_fingerprint,
    load_ledger,
    queue_path,
    save_ledger,
    upsert,
)
from burling.paths import intake_dir
from burling.priors import prior_severity, scan_filename, scan_text
from burling.progress import Progress
from burling.isolate import OPERATOR_STOP, note_file_failure
from burling.trace import write_decision


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_queue(cfg: dict, intake: Path | None = None) -> dict:
    """Inventory every file under intake/. Extraction + regex priors happen here.

    Model calls are a later pass. That split is deliberate: you can map the dump
    and catch formatted SSNs even if Ollama is down.
    """
    root = intake or intake_dir(cfg)
    if not root.is_dir():
        raise FileNotFoundError(
            f"Intake folder not found: {root}\n"
            "Drop the handover files into burling/intake/ (or pass --intake)."
        )

    ledger = load_ledger(cfg)
    files = iter_source_files(root)
    items = []
    progress = Progress(cfg, "queue", len(files))

    for i, path in enumerate(files, start=1):
        rel = path.relative_to(root).as_posix()
        # GOLDEN RULE: one file must not kill the run. Note it and continue.
        try:
            progress.tick(i, rel)
            extracted = extract_record(path, root)
            text = extracted["text"]
            chash = content_hash(text) if extracted["extraction_ok"] else file_fingerprint(path)
            doc_id = chash[:16]
            priors = scan_text(text) if extracted["extraction_ok"] else {}
            filename_tags = scan_filename(extracted["rel_path"])

            existing = ledger["documents"].get(doc_id, {})
            unchanged = existing.get("content_hash") == chash

            row = upsert(
                ledger,
                doc_id,
                rel_path=extracted["rel_path"],
                ext=extracted["ext"],
                size_bytes=extracted["size_bytes"],
                content_hash=chash,
                char_count=len(text),
                extraction={
                    "ok": extracted["extraction_ok"],
                    "method": extracted["extraction_method"],
                    "error": extracted["extraction_error"],
                },
                priors=priors,
                filename_tags=filename_tags,
                prior_severity=prior_severity(priors),
                queued_at=existing.get("queued_at") or _now(),
            )
            if not unchanged:
                # File changed: invalidate model passes so they re-run.
                row["pass1"] = None
                row["pass2"] = None
                row["queue_status"] = "extracted" if extracted["extraction_ok"] else "extract_failed"
            elif not row.get("queue_status"):
                row["queue_status"] = "extracted" if extracted["extraction_ok"] else "extract_failed"

            write_decision(cfg, row)

            items.append(
                {
                    "doc_id": doc_id,
                    "rel_path": extracted["rel_path"],
                    "status": row["queue_status"],
                }
            )
        except OPERATOR_STOP:
            raise
        except Exception as exc:
            try:
                doc_id = file_fingerprint(path)
            except Exception:
                doc_id = f"fail-{i}"
            row = note_file_failure(
                cfg,
                ledger,
                ledger["documents"].get(doc_id) or {"rel_path": rel, "doc_id": doc_id},
                stage="queue",
                exc=exc,
                rel_path=rel,
            )
            items.append({"doc_id": row.get("doc_id"), "rel_path": rel, "status": "queue_skipped"})

    ledger["intake"] = str(root)
    queue = {
        "built_at": _now(),
        "intake": str(root),
        "total": len(items),
        "items": items,
    }
    save_ledger(cfg, ledger)
    atomic_write_json(queue_path(cfg), queue)
    progress.finish(len(items))
    return queue


def pending(ledger: dict, pass_name: str) -> list[dict]:
    """Documents that still need this model pass, in stable path order."""
    rows = list(ledger["documents"].values())
    rows.sort(key=lambda r: r.get("rel_path") or "")
    out = []
    for row in rows:
        if not (row.get("extraction") or {}).get("ok"):
            continue
        result = row.get(pass_name)
        # Resume retries skips. Timeouts and Windows file locks are transient;
        # leaving status=skipped forever would strand the file after a crash.
        if not result or result.get("status") == "skipped":
            out.append(row)
    return out


def load_queue(cfg: dict) -> dict:
    return load_json(queue_path(cfg), {"items": [], "total": 0})
