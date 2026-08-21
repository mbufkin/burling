"""Per-document decision JSON — one flat file per source file.

Best practice for a local review harness: the nested ledger is for the program;
a flat sidecar is for a human (or a later dashboard). After every step we rewrite
the same file so you can watch extract → regex → pass 1 → pass 2 without opening
ledger.json.

We do NOT copy document text into the sidecar. That would be a second PII store.
Priors stay redacted. Model summaries are already instructed not to quote identifiers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from burling.io_util import atomic_write_json
from burling.paths import output_dir

PII_KINDS = ("ssn", "credit_card", "dob", "email", "phone", "address", "sensitive_keyword")
DECISIONS_DIR = "decisions"
INDEX_NAME = "DECISIONS.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _join(values: list | None) -> str:
    return ",".join(str(v) for v in (values or []) if v not in (None, ""))


def flatten_decision(row: dict) -> dict:
    """One-level keys only. Nested dicts are the thing we are flattening away."""
    extraction = row.get("extraction") or {}
    priors = row.get("priors") or {}
    p1 = row.get("pass1") or {}
    p2 = row.get("pass2") or {}
    placement = row.get("placement") or {}
    rich = row.get("rich_tags") or {}

    steps = ["extract", "priors"]
    if p1.get("status"):
        steps.append("pass1")
    if p2.get("status"):
        steps.append("pass2")
    if placement.get("status"):
        steps.append("map")
    if rich.get("status"):
        steps.append("tags")

    flat: dict = {
        "doc_id": row.get("doc_id"),
        "rel_path": row.get("rel_path"),
        "ext": row.get("ext"),
        "size_bytes": row.get("size_bytes"),
        "char_count": row.get("char_count"),
        "content_hash": row.get("content_hash"),
        "queue_status": row.get("queue_status"),
        "steps_done": _join(steps),
        "extract_ok": extraction.get("ok"),
        "extract_method": extraction.get("method"),
        "extract_error": extraction.get("error"),
        "extract_at": row.get("queued_at"),
        "filename_tags": _join(row.get("filename_tags")),
        "prior_severity": row.get("prior_severity") or "low",
        "prior_kinds": _join([k for k in PII_KINDS if k in priors]),
        "pass1_status": p1.get("status"),
        "pass1_at": p1.get("at"),
        "pass1_chunk_count": p1.get("chunk_count"),
        "pass1_chunk_custodies": p1.get("chunk_custodies"),
        "pass1_tags": _join(p1.get("tags")),
        "pass1_primary_tag": p1.get("primary_tag"),
        "pass1_custody": p1.get("custody"),
        "pass1_work_related": p1.get("work_related"),
        "pass1_confidence": p1.get("confidence"),
        "pass1_summary": p1.get("summary"),
        "pass1_error": p1.get("error"),
        "pass2_status": p2.get("status"),
        "pass2_at": p2.get("at"),
        "pass2_model_custody": p2.get("model_custody"),
        "pass2_model_recommendation": p2.get("model_recommendation"),
        "pass2_model_reasons": _join(p2.get("model_reasons")),
        "pass2_model_rationale": p2.get("rationale"),
        "pass2_model_confidence": p2.get("confidence"),
        "pass2_code_override": p2.get("code_override"),
        "pass2_fail_closed": bool(p2.get("fail_closed")),
        "pass2_final_custody": p2.get("custody"),
        "pass2_final_recommendation": p2.get("recommendation"),
        "pass2_final_reasons": _join(p2.get("reasons")),
        # Topic-map placement (taxonomy-first). Empty until --map / full run finishes.
        "map_status": placement.get("status"),
        "map_program": _join(placement.get("program")),
        "map_function": _join(placement.get("function")),
        "map_audience": _join(placement.get("audience")),
        "map_record_type": _join(placement.get("record_type")),
        "map_lifecycle": _join(placement.get("lifecycle")),
        "map_confidence": placement.get("confidence"),
        "map_needs_review": placement.get("needs_review"),
        "map_rationale": placement.get("rationale"),
        "map_handoff_note": placement.get("handoff_note"),
        # Pass A rich tags (tag-then-stitch). Empty until --tags runs.
        "rich_tags_status": rich.get("status"),
        "rich_tags": _join(rich.get("tags")),
        "rich_tags_count": len(rich.get("tags") or []),
        "rich_summary": rich.get("summary"),
        "rich_tags_needs_review": rich.get("needs_review"),
    }

    for kind in PII_KINDS:
        bucket = priors.get(kind) or {}
        flat[f"prior_{kind}_count"] = bucket.get("count", 0)
        flat[f"prior_{kind}_samples"] = _join(bucket.get("redacted_samples"))

    return flat


def decision_path(cfg: dict, rel_path: str) -> Path:
    """Mirror the dump tree under output/decisions/, with .json on the end.

    ``Perkins Travel/form.pdf`` → ``output/decisions/Perkins Travel/form.pdf.json``
    so you can find the trail by the same path you see in the map.
    """
    rel = Path(rel_path)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"refusing unsafe decision path: {rel_path!r}")
    return output_dir(cfg) / DECISIONS_DIR / Path(*rel.parts).with_name(rel.name + ".json")


def write_decision(cfg: dict, row: dict) -> Path | None:
    """Rewrite this document's sidecar. Safe to call after every step.

    Sidecar I/O must not kill the run. A missing folder or a weird path is a
    note, not a reason to abandon the rest of the dump.
    """
    rel = row.get("rel_path")
    if not rel:
        return None
    try:
        path = decision_path(cfg, rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(path, flatten_decision(row))
        return path
    except Exception as exc:
        from burling.progress import console_safe

        print(console_safe(f"  NOTED [sidecar] {rel}: {type(exc).__name__}: {exc}"), flush=True)
        return None


def write_all_decisions(cfg: dict, rows: list[dict]) -> Path:
    """Sidecar per doc plus one index array for loading the whole run at once."""
    flats = []
    for row in rows:
        if not row.get("rel_path"):
            continue
        try:
            write_decision(cfg, row)
            flats.append(flatten_decision(row))
        except Exception as exc:
            from burling.progress import console_safe

            print(
                console_safe(
                    f"  NOTED [index] {row.get('rel_path')}: {type(exc).__name__}: {exc}"
                ),
                flush=True,
            )
    index = output_dir(cfg) / INDEX_NAME
    atomic_write_json(
        index,
        {
            "built_at": utc_now(),
            "documents": len(flats),
            "records": flats,
        },
    )
    return index
