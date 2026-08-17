"""GOLDEN RULE: one file must never kill the run.

A timeout, a weird Unicode filename, a corrupt PDF, or a model JSON glitch
is a note on that document — not a reason to abandon the other 993. The
operator can still stop the job (Ctrl+C / SystemExit). Everything else is
caught, written to the ledger + decision sidecar, and the loop continues.

Call ``note_file_failure`` from every per-file loop. Do not ``except Exception``
at the process top level and exit; that hides the rule.
"""

from __future__ import annotations

from burling.ledger import save_ledger
from burling.progress import console_safe
from burling.trace import utc_now, write_decision

# These are the operator, not a bad file.
OPERATOR_STOP = (KeyboardInterrupt, SystemExit)


def note_file_failure(
    cfg: dict,
    ledger: dict | None,
    row: dict | None,
    *,
    stage: str,
    exc: BaseException,
    rel_path: str | None = None,
) -> dict:
    """Record the failure and keep going. Never re-raise."""
    rel = rel_path or (row or {}).get("rel_path") or "(unknown path)"
    err = f"{type(exc).__name__}: {exc}"
    print(console_safe(f"  NOTED [{stage}] {rel}: {err}"), flush=True)

    if row is None:
        row = {"rel_path": rel, "doc_id": "unknown"}
    if not row.get("doc_id"):
        row["doc_id"] = f"fail-{abs(hash(rel)) % 10**12}"
    row["queue_status"] = f"{stage}_skipped"
    note = {
        "status": "skipped",
        "error": err,
        "at": utc_now(),
        "code_override": "one_file_must_not_kill_the_run",
    }
    if stage in {"pass1", "pass2", "queue", "extract", "stream"}:
        if stage == "pass2":
            row["pass2"] = {
                **note,
                "custody": "unclear",
                "recommendation": "review",
                "reasons": ["needs_human_review"],
                "rationale": f"Skipped after error: {err}",
                "confidence": "low",
            }
        elif stage == "pass1":
            row["pass1"] = note
        else:
            row.setdefault("extraction", {})
            row["extraction"] = {
                "ok": False,
                "method": "failed",
                "error": err,
            }
            row["pass1"] = row.get("pass1")
    try:
        if ledger is not None:
            # Queue failures arrive as a throwaway dict. Put it in the ledger
            # so REVIEW-QUEUE.md still lists the file after the run.
            ledger.setdefault("documents", {})[row["doc_id"]] = row
            save_ledger(cfg, ledger)
        write_decision(cfg, row)
    except Exception as inner:
        print(console_safe(f"  NOTED [{stage}] also failed to write sidecar: {inner}"), flush=True)
    return row
