"""One-file rclone stream: download, review, delete the local copy.

The Shared Drive is the source of truth. The local file is only a scratch pad
so the 7B can read it. After pass 2 the temp folder is always removed — that is
the "download one, then delete" cycle. Nothing accumulates on disk.

Drive itself is left alone unless you pass ``--trash-personal``. Student
records and work files are never trashed even then.

GOLDEN RULE: one file must not kill the run. Ctrl+C still stops.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from burling.extract import SKIP_EXTENSIONS, extract_record
from burling.isolate import OPERATOR_STOP, note_file_failure
from burling.ledger import content_hash, file_fingerprint, load_ledger, save_ledger, upsert
from burling.pass1 import tag_one
from burling.pass2 import judge_one
from burling.paths import load_config
from burling.priors import prior_severity, scan_filename, scan_text
from burling.progress import Progress, console_safe
from burling.quarantine import is_student_record
from burling.rclone_util import copy_one, list_remote_files, trash_one
from burling.reports import write_reports
from burling.trace import write_decision


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def row_by_path(ledger: dict, rel: str) -> dict | None:
    """Find a ledger row by Drive-relative path. Hash ids change if extract fails."""
    for row in ledger["documents"].values():
        if (row.get("rel_path") or "").replace("\\", "/") == rel:
            return row
    return None


def already_reviewed(row: dict | None) -> bool:
    """Skip a second model pass when pass 2 already finished.

    Extract failures are ``skipped``, not ``done`` — those get another try
    because a Drive export can succeed where the local corpus copy failed.
    """
    if not row:
        return False
    return (row.get("pass2") or {}).get("status") == "done"


def should_trash_on_drive(row: dict) -> bool:
    """Personal leftover → Drive trash. Student / work / unclear → leave it."""
    if is_student_record(row):
        return False
    rec = (row.get("pass2") or {}).get("recommendation")
    return rec == "delete_candidate"


def ingest(ledger: dict, extracted: dict, path: Path, rel: str) -> dict:
    """Write one file into the ledger. Always store the Drive path, not scratch."""
    text = extracted["text"]
    chash = content_hash(text) if extracted["extraction_ok"] else file_fingerprint(path)
    doc_id = chash[:16]
    priors = scan_text(text) if extracted["extraction_ok"] else {}
    filename_tags = scan_filename(rel)
    existing = ledger["documents"].get(doc_id, {})
    extracted["rel_path"] = rel
    return upsert(
        ledger,
        doc_id,
        rel_path=rel,
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
        stream="rclone",
    )


def review_local(cfg: dict, ledger: dict, rel: str, local: Path) -> dict:
    """Pass 1 + pass 2 on a file that already sits on disk."""
    extracted = extract_record(local, local.parent)
    extracted["rel_path"] = rel
    row = ingest(ledger, extracted, local, rel)
    tag_one(cfg, row, extracted)
    judge_one(cfg, row, extracted)
    save_ledger(cfg, ledger)
    write_decision(cfg, row)
    return row


def maybe_trash(cfg: dict, ledger: dict, row: dict, *, trash_personal: bool) -> bool:
    if not trash_personal or not should_trash_on_drive(row):
        return False
    trash_one(cfg, row["rel_path"])
    row["disposition"] = "drive_trashed"
    row["quarantined_at"] = _now()
    save_ledger(cfg, ledger)
    print(console_safe(f"  TRASH [drive] {row['rel_path']}"), flush=True)
    return True


def run_stream(
    cfg: dict,
    *,
    limit: int | None = None,
    force: bool = False,
    trash_personal: bool = False,
) -> dict:
    ledger = load_ledger(cfg)
    print("Listing Shared Drive files (rclone lsf)...", flush=True)
    remote_files = list_remote_files(cfg)
    remote_files = [
        rel
        for rel in remote_files
        if Path(rel).suffix.lower() not in SKIP_EXTENSIONS
    ]
    stats = {
        "listed": len(remote_files),
        "reviewed": 0,
        "trashed": 0,
        "skipped": 0,
        "noted": 0,
    }
    todo: list[str] = []
    for rel in remote_files:
        existing = row_by_path(ledger, rel)
        if already_reviewed(existing) and not force:
            stats["skipped"] += 1
            # Already judged personal leftover still sitting on Drive.
            if trash_personal and existing and maybe_trash(
                cfg, ledger, existing, trash_personal=True
            ):
                stats["trashed"] += 1
            continue
        todo.append(rel)
    if limit is not None:
        todo = todo[:limit]
    print(
        console_safe(
            f"Drive has {stats['listed']} files; "
            f"{stats['skipped']} already reviewed; "
            f"{len(todo)} to stream"
        ),
        flush=True,
    )
    progress = Progress(cfg, "stream", len(todo))
    for i, rel in enumerate(todo, start=1):
        progress.tick(i, rel)
        # GOLDEN RULE: one file must not kill the run.
        try:
            with tempfile.TemporaryDirectory(prefix="burling-stream-") as tmp:
                local = copy_one(cfg, rel, Path(tmp))
                row = review_local(cfg, ledger, rel, local)
                stats["reviewed"] += 1
                rec = (row.get("pass2") or {}).get("recommendation")
                if maybe_trash(cfg, ledger, row, trash_personal=trash_personal):
                    stats["trashed"] += 1
                else:
                    print(console_safe(f"  KEEP  [drive] {rel}  {rec}"), flush=True)
            # TemporaryDirectory unlinks the scratch copy here. That is the point.
        except OPERATOR_STOP:
            save_ledger(cfg, ledger)
            raise
        except Exception as exc:
            stats["noted"] += 1
            note_file_failure(
                cfg,
                ledger,
                row_by_path(ledger, rel) or {"rel_path": rel, "doc_id": f"stream-{i}"},
                stage="stream",
                exc=exc,
                rel_path=rel,
            )
        if i % 25 == 0:
            write_reports(cfg)
    progress.finish(stats["reviewed"])
    write_reports(cfg)
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download one Drive file, review it, delete the local copy."
    )
    parser.add_argument("--limit", type=int, help="Process at most N new files this run")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-review files that already have a pass-2 decision",
    )
    parser.add_argument(
        "--trash-personal",
        action="store_true",
        help="After review, send personal leftovers to Drive trash (student records stay)",
    )
    parser.add_argument("--config", help="Optional config.yaml override")
    args = parser.parse_args(argv)
    cfg = load_config(Path(args.config) if args.config else None)
    stats = run_stream(
        cfg,
        limit=args.limit,
        force=args.force,
        trash_personal=args.trash_personal,
    )
    print(
        f"stream done: listed {stats['listed']}, "
        f"reviewed {stats['reviewed']}, "
        f"trashed {stats['trashed']}, "
        f"skipped {stats['skipped']}, "
        f"noted {stats['noted']}"
    )
    print("Local copies were deleted after each file. Drive files stay unless --trash-personal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
