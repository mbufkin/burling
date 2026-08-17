"""Pass 1 — tag what the document contains so we can map the dump.

TAR first pass is classification, not a delete decision. The model names the
kinds of content. Regex priors are attached as evidence, not as the tag list.
"""

from __future__ import annotations

from pathlib import Path

from burling.extract import extract_record
from burling.ledger import load_ledger, save_ledger
from burling.ollama_client import chat
from burling.paths import intake_dir as config_intake
from burling.queue import pending
from burling.progress import Progress
from burling.isolate import OPERATOR_STOP, note_file_failure
from burling.trace import utc_now, write_decision

ALLOWED_TAGS = [
    "curriculum_lesson",
    "curriculum_assessment",
    "curriculum_pacing",
    "curriculum_admin",
    "student_record",
    "employee_hr",
    "tax_financial",
    "medical",
    "identity_document",
    "personal_photo_or_media",
    "personal_correspondence",
    "credentials_secrets",
    "software_code",
    "work_email_or_memo",
    "unknown",
]

PASS1_SYSTEM = """You are a records clerk mapping a school CTE handover dump.
Read ONE document. Classify what it contains. Do NOT quote names, SSNs, account
numbers, emails, phone numbers, or street addresses. Summarize in generic terms.

PII (SSN, address, email) may appear in BOTH leftover personal files AND
legitimate work files. Your job here is content type, not delete.

Return JSON only:
{
  "tags": ["one or more tags from the allowed list"],
  "primary_tag": "the single best tag",
  "custody": "personal" | "work" | "unclear",
  "work_related": true or false,
  "summary": "one or two sentences, no identifiers",
  "confidence": "high" | "medium" | "low"
}

custody:
- personal = leftover private life (tax returns, mortgage, TurboTax, family)
- work = district/CTE business (curriculum, student immunization, staff travel)
- unclear = cannot tell

Allowed tags:
""" + ", ".join(ALLOWED_TAGS)


def _chunks(text: str, cfg: dict) -> list[str]:
    """Split long files. Never truncate (Loom Bet 1). Overlap keeps a split sentence readable."""
    threshold = cfg["chunking"]["threshold_chars"]
    size = cfg["chunking"]["chunk_chars"]
    overlap = cfg["chunking"]["overlap_chars"]
    if len(text) <= threshold:
        return [text]
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i : i + size])
        i += size - overlap
    return chunks


def _merge_tags(results: list[dict]) -> dict:
    tags: list[str] = []
    for r in results:
        for t in r.get("tags") or []:
            if t in ALLOWED_TAGS and t not in tags:
                tags.append(t)
    if not tags:
        tags = ["unknown"]
    custodies = [(r.get("custody") or "").lower() for r in results]
    if "personal" in custodies:
        custody = "personal"
        work = False
    elif "work" in custodies:
        custody = "work"
        work = True
    else:
        custody = "unclear"
        work = any(bool(r.get("work_related")) for r in results)
    confs = [r.get("confidence") or "low" for r in results]
    confidence = "low" if "low" in confs else ("medium" if "medium" in confs else "high")
    summaries = [r.get("summary") or "" for r in results if r.get("summary")]
    chunk_custodies = [(r.get("custody") or "unclear").lower() for r in results]
    return {
        "tags": tags,
        "primary_tag": (results[0].get("primary_tag") if results else None) or tags[0],
        "custody": custody,
        "work_related": work,
        "summary": " ".join(summaries)[:800],
        "confidence": confidence,
        "chunk_count": len(results),
        "chunk_custodies": "|".join(chunk_custodies),
    }


def tag_one(cfg: dict, row: dict, extracted: dict) -> None:
    """Run pass 1 on one already-extracted file. Mutates ``row``."""
    if not extracted["extraction_ok"]:
        row["pass1"] = {
            "status": "skipped",
            "error": extracted["extraction_error"],
            "at": utc_now(),
        }
        row["queue_status"] = "extract_failed"
        return
    results = []
    for n, chunk in enumerate(_chunks(extracted["text"], cfg), start=1):
        prior_note = row.get("priors") or {}
        user = (
            f"FILE: {row['rel_path']}\n"
            f"REGEX PRIORS (redacted, already detected): {prior_note}\n"
            f"FILENAME HINTS: {row.get('filename_tags')}\n"
            f"CHUNK {n}\n\n{chunk}"
        )
        results.append(
            chat(
                cfg,
                [
                    {"role": "system", "content": PASS1_SYSTEM},
                    {"role": "user", "content": user},
                ],
                step=f"pass1:{row['rel_path']}:chunk{n}",
            )
        )
    merged = _merge_tags(results)
    merged["status"] = "done"
    merged["at"] = utc_now()
    row["pass1"] = merged
    row["queue_status"] = "pass1_done"


def run_pass1(cfg: dict, *, limit: int | None = None) -> int:
    ledger = load_ledger(cfg)
    todo = pending(ledger, "pass1")
    if limit is not None:
        todo = todo[:limit]
    intake = Path(ledger.get("intake") or config_intake(cfg))
    done = 0
    progress = Progress(cfg, "pass1", len(todo))
    for i, row in enumerate(todo, start=1):
        # GOLDEN RULE: one file must not kill the run. Note it and continue.
        try:
            path = intake / row["rel_path"]
            progress.tick(i, row["rel_path"])
            extracted = extract_record(path, intake)
            tag_one(cfg, row, extracted)
            save_ledger(cfg, ledger)
            write_decision(cfg, row)
            if (row.get("pass1") or {}).get("status") == "done":
                done += 1
        except OPERATOR_STOP:
            raise
        except Exception as exc:
            note_file_failure(cfg, ledger, row, stage="pass1", exc=exc)
    progress.finish(done)
    return done
