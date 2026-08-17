"""Operator move: take flagged personal leftovers out of the corpus.

Burling never deletes on its own (config policy.never_delete). This module is
the human confirmation step: move delete-candidate files to a quarantine folder
so the CTE dump is not mixed with leftover tax / passport / mortgage files.

Student records stay in the corpus. Best practice for a school handover: TB /
immunization / parent-consent files are district records (FERPA), even when they
contain PII. Family leftovers (e.g. a child named Spence) are not.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from burling.isolate import OPERATOR_STOP
from burling.ledger import load_ledger, save_ledger
from burling.paths import intake_dir, load_config, output_dir
from burling.progress import console_safe
from burling.reports import write_reports
from burling.trace import utc_now, write_decision

QUARANTINE_DIR = "quarantine-not-student"
LOG_NAME = "QUARANTINE.md"


def is_student_record(row: dict) -> bool:
    """Keep district student files. Do not keep the director's own family papers."""
    rel = (row.get("rel_path") or "").replace("\\", "/")
    low = rel.lower()
    if "mackenna" in low:
        return False
    if "tb lab" in low or "tb results" in low:
        return True
    if "parent consent" in low:
        return True
    # Bare "Minor Testing Packet.pdf" looks like a campus health packet.
    # "Mackenna Spence Minor Testing..." is family and already excluded.
    name = Path(rel).name.lower()
    if name == "minor testing packet.pdf":
        return True
    return False


def _safe_dest(root: Path, rel: str) -> Path:
    dest = (root / rel).resolve()
    if not str(dest).startswith(str(root.resolve())):
        raise ValueError(f"refusing path escape: {rel!r}")
    return dest


def apply_quarantine(cfg: dict, *, intake: Path | None = None) -> dict:
    """Move non-student delete candidates out of intake. Student files stay put."""
    ledger = load_ledger(cfg)
    src_root = Path(ledger.get("intake") or intake or intake_dir(cfg))
    dest_root = output_dir(cfg) / QUARANTINE_DIR
    dest_root.mkdir(parents=True, exist_ok=True)

    moved: list[dict] = []
    kept: list[dict] = []
    missing: list[dict] = []

    rows = list(ledger["documents"].values())
    for row in rows:
        if (row.get("pass2") or {}).get("recommendation") != "delete_candidate":
            continue
        if row.get("disposition") == "quarantined":
            continue
        rel = row.get("rel_path") or ""
        if is_student_record(row):
            p2 = dict(row.get("pass2") or {})
            p2["recommendation"] = "keep"
            p2["code_override"] = "human_kept_student_record"
            p2["reasons"] = list(p2.get("reasons") or [])
            if "keep_work_student_record" not in p2["reasons"]:
                p2["reasons"].append("keep_work_student_record")
            p2["rationale"] = (
                "Human kept this as a district student record (FERPA). "
                "Not a leftover personal file."
            )
            row["pass2"] = p2
            row["queue_status"] = "kept_student_record"
            kept.append({"rel_path": rel, "reason": "student_record"})
            write_decision(cfg, row)
            continue

        src = src_root / rel
        if not src.is_file():
            missing.append({"rel_path": rel, "error": "not on disk"})
            continue
        try:
            dest = _safe_dest(dest_root, rel)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                dest = dest.with_name(dest.stem + ".dup" + dest.suffix)
            shutil.move(str(src), str(dest))
            row["disposition"] = "quarantined"
            row["quarantined_at"] = utc_now()
            row["quarantine_path"] = dest.relative_to(output_dir(cfg)).as_posix()
            row["queue_status"] = "quarantined"
            moved.append({"rel_path": rel, "dest": row["quarantine_path"]})
            write_decision(cfg, row)
        except OPERATOR_STOP:
            raise
        except Exception as exc:
            missing.append({"rel_path": rel, "error": f"{type(exc).__name__}: {exc}"})
            print(console_safe(f"  NOTED [quarantine] {rel}: {exc}"), flush=True)

    save_ledger(cfg, ledger)
    log = _log_markdown(moved, kept, missing, dest_root)
    (output_dir(cfg) / LOG_NAME).write_text(log, encoding="utf-8")
    write_reports(cfg)
    return {"moved": len(moved), "kept": len(kept), "missing": len(missing)}


def _log_markdown(moved: list[dict], kept: list[dict], missing: list[dict], dest: Path) -> str:
    lines = [
        "# Quarantine log",
        "",
        "Personal leftovers were **moved**, not shredded. Restore from this folder if a file was work.",
        "",
        f"**Destination:** `{dest}`",
        f"**Moved:** {len(moved)}",
        f"**Kept (student records):** {len(kept)}",
        f"**Missing / failed:** {len(missing)}",
        "",
        "## Kept in corpus (student records)",
        "",
    ]
    for row in kept:
        lines.append(f"- `{row['rel_path']}`")
    lines += ["", "## Moved out of corpus", "", "| Original | Now at |", "|---|---|"]
    for row in moved:
        lines.append(f"| `{row['rel_path']}` | `{row['dest']}` |")
    if missing:
        lines += ["", "## Could not move", ""]
        for row in missing:
            lines.append(f"- `{row['rel_path']}` — {row['error']}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Move non-student delete candidates to quarantine. Student files stay."
    )
    parser.add_argument("--apply", action="store_true", help="Actually move files. Required.")
    parser.add_argument("--intake", help="Corpus folder (default: ledger intake path)")
    args = parser.parse_args(argv)
    if not args.apply:
        print("Refusing to move files without --apply. This is irreversible-ish (move, not delete).")
        return 2
    cfg = load_config()
    if args.intake:
        cfg["paths"]["intake_dir"] = str(Path(args.intake).resolve())
    stats = apply_quarantine(cfg, intake=Path(args.intake) if args.intake else None)
    print(
        f"quarantine done: moved {stats['moved']}, "
        f"kept {stats['kept']} student records, "
        f"{stats['missing']} missing"
    )
    print("Files are in burling/output/quarantine-not-student/ — not permanently deleted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
