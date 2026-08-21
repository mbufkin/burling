"""Pass A — rich free-form tags per document (tag-then-stitch pipeline).

Best practice (see docs/tag-then-stitch.md):
  Pass A describes what the document *is* with many tags + a short summary.
  Pass B later stitches that tag cloud into nested regions.
Do not force a single program primary, and do not tell the model this
folder is a job handover — that makes every summary say "for a successor"
instead of letting themes come from the text.
"""

from __future__ import annotations

import json
from pathlib import Path

from burling.extract import extract_record
from burling.io_util import atomic_write, atomic_write_json
from burling.isolate import OPERATOR_STOP, note_file_failure
from burling.ledger import load_ledger, save_ledger
from burling.ollama_client import chat
from burling.paths import intake_dir as config_intake, output_dir
from burling.progress import Progress
from burling.trace import utc_now, write_decision

DOC_CAP = 12_000
MIN_TAGS = 6
MAX_TAGS = 30

SYSTEM = """You are indexing one file from an arbitrary document dump.
Read ONE document. Describe what it actually is. Do not assume a workplace,
a school district, a job handover, or a successor packet — those words only
belong in the output if the document itself is about them.

Emit RICH multi-label tags — many useful labels, not one folder name.

Output ONLY a single JSON object:
{
  "tags": ["8-25 short kebab-case or short-phrase tags"],
  "entities": ["named programs, events, vendors, platforms — NO personal names"],
  "audiences": ["who uses this: teachers, campus-admin, central-cte, partners, vendors, …"],
  "artifact_types": ["what it is: checklist, quote, slide-deck, tracker, script, …"],
  "years": ["school years or calendar years mentioned, if any"],
  "summary": "3-6 sentences: what it is, who it is for, how it connects to other work. Do not mention a successor or handover unless the text does.",
  "focus_flags": ["optional soft hints only, e.g. contains-address-shaped-text — never quote PII"],
  "confidence": 0.0-1.0
}

Tagging rules:
- Prefer specific over generic (trailer-acknowledgment, not just document).
- Include topic family AND subtype when both fit (health AND immunization-record).
- Include purpose tags even on purchasing docs (conference-2026 AND quote).
- Do NOT invent personal names. Do not quote emails, phones, SSNs, streets.
- Do NOT add tags like handover, successor-packet, or work-handover unless the file is literally that.
- tags/entities/audiences/artifact_types may be a JSON array OR a single string (we normalize).
- More good tags beat fewer. Aim for at least 8 tags when the text supports it.
"""


def _as_str_list(raw: object, *, limit: int = MAX_TAGS) -> list[str]:
    """Accept string or list; dedupe case-insensitively while keeping first spelling."""
    items: list[str] = []
    if raw is None:
        return items
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return items
        if "," in text:
            items = [p.strip() for p in text.split(",") if p.strip()]
        else:
            items = [text]
    elif isinstance(raw, list):
        for x in raw:
            items.extend(_as_str_list(x, limit=limit))
    else:
        s = str(raw).strip()
        if s:
            items = [s]

    out: list[str] = []
    seen: set[str] = set()
    for name in items:
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
        if len(out) >= limit:
            break
    return out


def normalize_rich_tags(obj: dict) -> dict:
    """Normalize a model JSON blob into a stored rich_tags record."""
    tags = _as_str_list(obj.get("tags"))
    entities = _as_str_list(obj.get("entities"), limit=20)
    audiences = _as_str_list(obj.get("audiences"), limit=12)
    artifacts = _as_str_list(obj.get("artifact_types"), limit=12)
    years = _as_str_list(obj.get("years"), limit=8)
    focus = _as_str_list(obj.get("focus_flags"), limit=8)
    try:
        conf = float(obj.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    summary = str(obj.get("summary") or "").strip()[:2000]
    needs = conf < 0.4 or len(tags) < MIN_TAGS or not summary
    return {
        "tags": tags,
        "entities": entities,
        "audiences": audiences,
        "artifact_types": artifacts,
        "years": years,
        "summary": summary or "No summary returned.",
        "focus_flags": focus,
        "confidence": conf,
        "needs_review": needs,
        "status": "done",
        "at": utc_now(),
    }


def _fallback(reason: str) -> dict:
    return {
        "tags": [],
        "entities": [],
        "audiences": [],
        "artifact_types": [],
        "years": [],
        "summary": reason,
        "focus_flags": [],
        "confidence": 0.0,
        "needs_review": True,
        "status": "done",
        "at": utc_now(),
    }


def tag_one(cfg: dict, row: dict, extracted: dict) -> None:
    """Run rich tagging on one file. Mutates ``row['rich_tags']``."""
    if not extracted["extraction_ok"]:
        row["rich_tags"] = {
            **_fallback(f"Extract failed: {extracted.get('extraction_error')}"),
            "status": "skipped",
        }
        return

    body = (extracted.get("text") or "")[:DOC_CAP]
    if len((extracted.get("text") or "")) > DOC_CAP:
        body += "\n…[truncated for context budget]"

    user = (
        f"FILE: {row['rel_path']}\n"
        f"EXT: {row.get('ext')}\n"
        f"PASS1 PRIMARY TAG: {(row.get('pass1') or {}).get('primary_tag')}\n"
        f"PASS1 SUMMARY: {(row.get('pass1') or {}).get('summary')}\n"
        f"REGEX PRIORS (kinds only): {list((row.get('priors') or {}).keys())}\n\n"
        f"DOCUMENT TEXT:\n{body}"
    )
    try:
        raw = chat(
            cfg,
            [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
            step=f"tags:{row['rel_path']}",
        )
        row["rich_tags"] = normalize_rich_tags(raw if isinstance(raw, dict) else {})
    except Exception as exc:
        row["rich_tags"] = _fallback(f"Model/parse error: {exc}")


def write_tag_artifacts(cfg: dict) -> dict:
    """Write tags.jsonl + TAGS.md from ledger rich_tags."""
    ledger = load_ledger(cfg)
    rows = sorted(
        ledger["documents"].values(),
        key=lambda r: r.get("rel_path") or "",
    )
    records: list[dict] = []
    for r in rows:
        rt = dict(r.get("rich_tags") or {})
        if not rt:
            continue
        records.append(
            {
                "doc_id": r.get("doc_id"),
                "rel_path": r.get("rel_path"),
                "ext": r.get("ext"),
                "tags": rt.get("tags") or [],
                "entities": rt.get("entities") or [],
                "audiences": rt.get("audiences") or [],
                "artifact_types": rt.get("artifact_types") or [],
                "years": rt.get("years") or [],
                "summary": rt.get("summary") or "",
                "focus_flags": rt.get("focus_flags") or [],
                "confidence": rt.get("confidence", 0.0),
                "needs_review": bool(rt.get("needs_review")),
                "status": rt.get("status"),
            }
        )

    out = output_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    jsonl_path = out / "tags.jsonl"
    lines = [json.dumps(rec, ensure_ascii=False) for rec in records]
    atomic_write(jsonl_path, "\n".join(lines) + ("\n" if lines else ""))
    atomic_write_json(
        out / "tags.json",
        {"count": len(records), "documents": records},
    )
    atomic_write(out / "TAGS.md", _tags_md(records))
    return {
        "documents": len(records),
        "needs_review": sum(1 for r in records if r.get("needs_review")),
        "avg_tags": (
            round(sum(len(r["tags"]) for r in records) / len(records), 1) if records else 0
        ),
    }


def _tags_md(records: list[dict]) -> str:
    from collections import Counter

    tag_counts: Counter[str] = Counter()
    for r in records:
        for t in r.get("tags") or []:
            tag_counts[t] += 1

    lines = [
        "# Rich tags (Pass A)",
        "",
        "Free-form multi-label tags before Pass B stitch. See `docs/tag-then-stitch.md`.",
        "",
        f"**Documents tagged:** {len(records)}",
        f"**Needs review:** {sum(1 for r in records if r.get('needs_review'))}",
        f"**Unique tags:** {len(tag_counts)}",
        f"**Avg tags/doc:** "
        f"{(sum(len(r.get('tags') or []) for r in records) / len(records)):.1f}"
        if records
        else "**Avg tags/doc:** 0",
        "",
        "## Top tags",
        "",
        "| Tag | Docs |",
        "|---|---|",
    ]
    for tag, n in tag_counts.most_common(40):
        lines.append(f"| `{tag}` | {n} |")
    lines.append("")
    lines.append("## By document")
    lines.append("")
    for r in records:
        flag = " ⚠" if r.get("needs_review") else ""
        tags = ", ".join(f"`{t}`" for t in (r.get("tags") or [])[:20])
        lines.append(f"### `{r.get('rel_path')}`{flag}")
        lines.append("")
        lines.append(f"- **tags:** {tags or '(none)'}")
        if r.get("entities"):
            lines.append(
                "- **entities:** " + ", ".join(f"`{e}`" for e in r["entities"][:12])
            )
        if r.get("artifact_types"):
            lines.append(
                "- **artifacts:** " + ", ".join(f"`{a}`" for a in r["artifact_types"][:8])
            )
        lines.append(f"- **summary:** {r.get('summary') or ''}")
        lines.append("")
    return "\n".join(lines)


def _should_tag(row: dict, force: bool) -> bool:
    """Retry skips. A skipped extract is not a finished tag.

    Best practice: ``skipped`` means try again later (OCR was missing,
    the model timed out). Only ``status=done`` is terminal. ``force``
    re-tags completed rows after a prompt change.
    """
    if force:
        return True
    existing = row.get("rich_tags") or {}
    return existing.get("status") != "done"


def run_rich_tags(cfg: dict, *, limit: int | None = None, force: bool = False) -> int:
    """Tag every queued document richly. Returns count tagged this run."""
    ledger = load_ledger(cfg)
    rows = sorted(
        ledger["documents"].values(),
        key=lambda r: r.get("rel_path") or "",
    )
    todo = [r for r in rows if _should_tag(r, force)]
    if limit is not None:
        todo = todo[:limit]

    intake = Path(ledger.get("intake") or config_intake(cfg))
    done = 0
    progress = Progress(cfg, "tags", len(todo))
    for i, row in enumerate(todo, start=1):
        try:
            path = intake / row["rel_path"]
            progress.tick(i, row["rel_path"])
            extracted = extract_record(path, intake)
            tag_one(cfg, row, extracted)
            save_ledger(cfg, ledger)
            write_decision(cfg, row)
            if (row.get("rich_tags") or {}).get("status") in {"done", "skipped"}:
                done += 1
        except OPERATOR_STOP:
            raise
        except Exception as exc:
            note_file_failure(cfg, ledger, row, stage="tags", exc=exc)

    progress.finish(done)
    stats = write_tag_artifacts(cfg)
    print(
        f"rich tags: {stats['documents']} docs, "
        f"avg {stats['avg_tags']} tags/doc, "
        f"{stats['needs_review']} needs_review → {output_dir(cfg) / 'TAGS.md'}"
    )
    return done
