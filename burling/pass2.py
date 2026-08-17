"""Pass 2 — personal leftover vs work record.

Python already tagged PII (SSN, address, email). This pass does NOT delete
because a file has PII. Student immunization and staff travel are work even
when they contain identifiers. Tax / mortgage / TurboTax are personal leftovers.

The harness NEVER deletes files. Fail-closed only for personal-tax filenames.
"""

from __future__ import annotations

from pathlib import Path

from burling.extract import extract_record
from burling.ledger import load_ledger, save_ledger
from burling.ollama_client import chat
from burling.paths import intake_dir as config_intake
from burling.priors import looks_like_personal_tax
from burling.queue import pending
from burling.progress import Progress
from burling.isolate import OPERATOR_STOP, note_file_failure
from burling.trace import utc_now, write_decision

REASONS = [
    "personal_tax",
    "personal_mortgage",
    "personal_not_work",
    "keep_work_student_record",
    "keep_work_travel",
    "keep_work_curriculum",
    "keep_work_admin",
    "contains_pii_but_work",
    "needs_human_review",
]

PASS2_SYSTEM = """You are a records clerk. A CTE handover dump mixed leftover
PERSONAL files with legitimate WORK files. Python already flagged PII
(SSN, address, email, phone) as redacted priors. PII does not decide delete.

PERSONAL (delete_candidate): tax returns, W-2, 1099, TurboTax, mortgage,
closing docs, family finances, private life.

WORK (keep): CTE curriculum, student immunization / TB / health records the
district holds for students, staff travel for conferences, stipends, pacing,
advisory councils. These may contain SSN or addresses and still be work.

REVIEW when you cannot tell.

Do NOT quote identifiers. Do NOT invent facts.

Return JSON only:
{
  "custody": "personal" | "work" | "unclear",
  "recommendation": "keep" | "review" | "delete_candidate",
  "reasons": ["from the allowed reason list"],
  "rationale": "one or two sentences, no identifiers",
  "confidence": "high" | "medium" | "low"
}

Allowed reasons:
""" + ", ".join(REASONS)


def _force_personal_tax(row: dict, result: dict, cfg: dict) -> dict:
    """Filename W-2 / TurboTax / mortgage is personal even if the PDF is a scan."""
    if not cfg.get("policy", {}).get("fail_closed_on_personal_tax", True):
        return result
    if not looks_like_personal_tax(row.get("filename_tags") or []):
        return result
    result["recommendation"] = "delete_candidate"
    result["custody"] = "personal"
    reasons = list(result.get("reasons") or [])
    if "personal_tax" not in reasons:
        reasons.insert(0, "personal_tax")
    result["reasons"] = reasons
    result["fail_closed"] = True
    return result


def judge_one(cfg: dict, row: dict, extracted: dict) -> None:
    """Run pass 2 on one already-extracted file. Mutates ``row``."""
    if not extracted["extraction_ok"]:
        rec = "delete_candidate" if looks_like_personal_tax(row.get("filename_tags") or []) else "review"
        row["pass2"] = {
            "status": "skipped",
            "at": utc_now(),
            "model_custody": None,
            "model_recommendation": None,
            "model_reasons": [],
            "custody": "personal" if rec == "delete_candidate" else "unclear",
            "recommendation": rec,
            "reasons": ["personal_tax"] if rec == "delete_candidate" else ["needs_human_review"],
            "rationale": "Could not extract text; filename suggests personal tax."
            if rec == "delete_candidate"
            else "Could not extract text; human must open the file.",
            "confidence": "high" if rec == "delete_candidate" else "low",
            "fail_closed": rec == "delete_candidate",
            "code_override": "extract_failed_filename_tax"
            if rec == "delete_candidate"
            else "extract_failed_needs_human",
        }
        return

    pass1 = row.get("pass1") or {}
    user = (
        f"FILE: {row['rel_path']}\n"
        f"PASS1 TAGS: {pass1.get('tags')}\n"
        f"PASS1 CUSTODY: {pass1.get('custody')}\n"
        f"PASS1 SUMMARY: {pass1.get('summary')}\n"
        f"PII PRIORS (redacted, already detected): {row.get('priors')}\n"
        f"FILENAME HINTS: {row.get('filename_tags')}\n\n"
        f"DOCUMENT TEXT:\n{extracted['text'][: cfg['chunking']['chunk_chars']]}"
    )
    result = chat(
        cfg,
        [
            {"role": "system", "content": PASS2_SYSTEM},
            {"role": "user", "content": user},
        ],
        step=f"pass2:{row['rel_path']}",
    )
    rec = (result.get("recommendation") or "review").lower()
    if rec not in {"keep", "review", "delete_candidate"}:
        rec = "review"
    custody = (result.get("custody") or "").lower()
    model_rec = rec
    model_custody = custody or "unclear"
    model_reasons = list(result.get("reasons") or [])
    override = None
    if custody == "personal":
        rec = "delete_candidate"
        if model_rec != rec:
            override = "custody_personal_forces_delete_candidate"
    elif custody == "work" and rec == "delete_candidate":
        rec = "keep"
        override = "custody_work_blocks_delete"
        reasons = list(result.get("reasons") or [])
        if "contains_pii_but_work" not in reasons:
            reasons.append("contains_pii_but_work")
        result["reasons"] = reasons
    result["recommendation"] = rec
    result["custody"] = custody or "unclear"
    result = _force_personal_tax(row, result, cfg)
    if result.get("fail_closed"):
        override = "fail_closed_personal_tax_filename"
    result["model_recommendation"] = model_rec
    result["model_custody"] = model_custody
    result["model_reasons"] = model_reasons
    result["code_override"] = override
    result["status"] = "done"
    result["at"] = utc_now()
    row["pass2"] = result
    row["queue_status"] = "pass2_done"


def run_pass2(cfg: dict, *, limit: int | None = None) -> int:
    ledger = load_ledger(cfg)
    todo = pending(ledger, "pass2")
    if limit is not None:
        todo = todo[:limit]
    intake = Path(ledger.get("intake") or config_intake(cfg))
    done = 0
    progress = Progress(cfg, "pass2", len(todo))
    for i, row in enumerate(todo, start=1):
        # GOLDEN RULE: one file must not kill the run. Note it and continue.
        try:
            path = intake / row["rel_path"]
            progress.tick(i, row["rel_path"])
            extracted = extract_record(path, intake)
            judge_one(cfg, row, extracted)
            save_ledger(cfg, ledger)
            write_decision(cfg, row)
            if (row.get("pass2") or {}).get("status") == "done":
                done += 1
        except OPERATOR_STOP:
            raise
        except Exception as exc:
            note_file_failure(cfg, ledger, row, stage="pass2", exc=exc)
    progress.finish(done)
    return done
