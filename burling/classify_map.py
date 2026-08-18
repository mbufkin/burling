"""Taxonomy-first placement: full extracted docs → governed map facets.

Best practice (law/records pattern): the capability map exists *before*
classification. The model places each document into terms from map.yml;
it does not invent clusters and then name them.

Stores ``placement`` on each ledger row and writes:
  output/placements.json
  output/TOPIC-MAP.md
  output/topic-map.html
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import yaml

from burling.extract import extract_record
from burling.io_util import atomic_write, atomic_write_json
from burling.isolate import OPERATOR_STOP, note_file_failure
from burling.ledger import load_ledger, save_ledger
from burling.map_html import write_topic_map_html
from burling.ollama_client import chat
from burling.paths import PACKAGE_DIR, intake_dir as config_intake, output_dir
from burling.progress import Progress
from burling.trace import utc_now, write_decision

MAP_PATH = PACKAGE_DIR / "map.yml"
REQUIRED_FACETS = ("program", "function", "audience", "record_type", "lifecycle")
DOC_CAP = 10_000  # chars of body fed per call (path + priors stay outside)


def load_map(path: Path | None = None) -> dict:
    with (path or MAP_PATH).open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def allowed_terms(map_doc: dict) -> dict[str, set[str]]:
    allowed: dict[str, set[str]] = {}
    for facet, terms in (map_doc.get("facets") or {}).items():
        allowed[facet] = {t["name"] for t in terms}
        allowed[facet].add("unmapped")
    return allowed


def vocab_block(map_doc: dict) -> str:
    """Compact name + description lists for the prompt."""
    chunks: list[str] = []
    for facet, terms in (map_doc.get("facets") or {}).items():
        lines = [f"## {facet}"]
        for t in terms:
            desc = (t.get("description") or "").strip().replace("\n", " ")
            lines.append(f"- {t['name']}: {desc}")
        chunks.append("\n".join(lines))
    chunks.append(
        "## sentinel\n- unmapped: no listed term fits with reasonable confidence"
    )
    return "\n\n".join(chunks)


def _system_prompt(vocab: str) -> str:
    return (
        "You classify school CTE handover documents into a governed multi-facet "
        "taxonomy. Output ONLY a single JSON object with keys: "
        "program, function, audience, record_type, lifecycle (arrays of term names), "
        "confidence (0.0-1.0), needs_review (boolean), "
        "rationale (one sentence, no personal identifiers), "
        "handoff_note (one short sentence for a successor: why this file matters). "
        "Use ONLY term names listed in the map. Use [] when nothing fits. "
        "Use the sentinel \"unmapped\" inside a facet array when text exists but "
        "no listed term fits. Do not invent new terms. "
        "Do not quote names, emails, phones, SSNs, or street addresses.\n\n"
        f"Allowed vocabulary:\n{vocab}"
    )


def _sanitize_terms(raw: object, allowed: set[str]) -> list[str]:
    if not isinstance(raw, list):
        return ["unmapped"]
    out: list[str] = []
    for item in raw:
        name = str(item).strip()
        if name in allowed and name not in out:
            out.append(name)
    return out[:2] if out else ["unmapped"]


def _normalize(obj: dict, allowed: dict[str, set[str]]) -> dict:
    placement = {
        facet: _sanitize_terms(obj.get(facet), allowed.get(facet, {"unmapped"}))
        for facet in REQUIRED_FACETS
    }
    try:
        conf = float(obj.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    needs = bool(obj.get("needs_review")) or conf < 0.45
    if any(placement[f] == ["unmapped"] for f in ("program", "function")):
        needs = True
    rationale = str(obj.get("rationale") or "").strip()[:400]
    handoff = str(obj.get("handoff_note") or "").strip()[:400]
    if not rationale:
        rationale = "No rationale returned."
        needs = True
    placement.update(
        {
            "confidence": conf,
            "needs_review": needs,
            "rationale": rationale,
            "handoff_note": handoff,
            "status": "done",
            "at": utc_now(),
        }
    )
    return placement


def _fallback(reason: str) -> dict:
    return {
        **{f: ["unmapped"] for f in REQUIRED_FACETS},
        "confidence": 0.0,
        "needs_review": True,
        "rationale": reason,
        "handoff_note": "",
        "status": "done",
        "at": utc_now(),
    }


def place_one(cfg: dict, row: dict, extracted: dict, *, system: str, allowed: dict) -> None:
    """Run taxonomy placement on one file. Mutates ``row``."""
    if not extracted["extraction_ok"]:
        row["placement"] = {
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
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            step=f"map:{row['rel_path']}",
        )
        row["placement"] = _normalize(raw, allowed)
    except Exception as exc:
        row["placement"] = _fallback(f"Model/parse error: {exc}")


def _topic_map_md(placements: list[dict], map_doc: dict) -> str:
    by_program: dict[str, list[dict]] = defaultdict(list)
    review: list[dict] = []
    for p in placements:
        prog = (p.get("program") or ["unmapped"])[0]
        by_program[prog].append(p)
        if p.get("needs_review"):
            review.append(p)

    lines = [
        "# Topic map (taxonomy-first)",
        "",
        "Governed placement into `burling/map.yml`. Not DBSCAN clusters.",
        "",
        f"**Documents placed:** {len(placements)}",
        f"**Needs review:** {len(review)}",
        f"**Map version:** {(map_doc.get('meta') or {}).get('version', '?')}",
        "",
        "## By program",
        "",
    ]
    for prog in sorted(by_program, key=lambda k: (-len(by_program[k]), k)):
        members = by_program[prog]
        lines.append(f"### {prog} ({len(members)})")
        lines.append("")
        lines.append("| Path | Function | Audience | Lifecycle | Conf | Handoff note |")
        lines.append("|---|---|---|---|---|---|")
        for p in sorted(members, key=lambda x: x.get("rel_path") or ""):
            fn = ", ".join(p.get("function") or [])
            aud = ", ".join(p.get("audience") or [])
            life = ", ".join(p.get("lifecycle") or [])
            conf = p.get("confidence", 0)
            note = (p.get("handoff_note") or p.get("rationale") or "").replace("|", "/")
            flag = " ⚠" if p.get("needs_review") else ""
            lines.append(
                f"| `{p.get('rel_path')}`{flag} | {fn} | {aud} | {life} | {conf:.2f} | {note} |"
            )
        lines.append("")

    if review:
        lines.append("## Needs review")
        lines.append("")
        for p in review:
            lines.append(
                f"- `{p.get('rel_path')}` — {p.get('rationale') or 'low confidence / unmapped'}"
            )
        lines.append("")

    # Facet tallies
    lines.append("## Facet tallies")
    lines.append("")
    for facet in REQUIRED_FACETS:
        counts = Counter((p.get(facet) or ["unmapped"])[0] for p in placements)
        lines.append(f"### {facet}")
        lines.append("")
        lines.append("| Term | Count |")
        lines.append("|---|---|")
        for term, n in counts.most_common():
            lines.append(f"| {term} | {n} |")
        lines.append("")

    return "\n".join(lines)


def write_placement_artifacts(cfg: dict, map_doc: dict) -> dict:
    """Serialize placements from the ledger + markdown + HTML."""
    ledger = load_ledger(cfg)
    rows = sorted(
        ledger["documents"].values(),
        key=lambda r: r.get("rel_path") or "",
    )
    placements: list[dict] = []
    for r in rows:
        p = dict(r.get("placement") or {})
        if not p:
            continue
        placements.append(
            {
                "doc_id": r.get("doc_id"),
                "rel_path": r.get("rel_path"),
                "ext": r.get("ext"),
                **{f: p.get(f) or ["unmapped"] for f in REQUIRED_FACETS},
                "confidence": p.get("confidence", 0.0),
                "needs_review": bool(p.get("needs_review")),
                "rationale": p.get("rationale") or "",
                "handoff_note": p.get("handoff_note") or "",
                "status": p.get("status"),
            }
        )

    out = output_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "map_id": (map_doc.get("meta") or {}).get("id"),
        "map_version": (map_doc.get("meta") or {}).get("version"),
        "count": len(placements),
        "placements": placements,
    }
    atomic_write_json(out / "placements.json", payload)
    atomic_write(out / "TOPIC-MAP.md", _topic_map_md(placements, map_doc))
    write_topic_map_html(out / "topic-map.html", payload)
    return {
        "documents": len(placements),
        "needs_review": sum(1 for p in placements if p.get("needs_review")),
    }


def run_map(cfg: dict, *, limit: int | None = None, force: bool = False) -> int:
    """Place every queued document on the governed map. Returns count placed."""
    map_doc = load_map()
    allowed = allowed_terms(map_doc)
    system = _system_prompt(vocab_block(map_doc))

    ledger = load_ledger(cfg)
    rows = sorted(
        ledger["documents"].values(),
        key=lambda r: r.get("rel_path") or "",
    )
    todo = []
    for r in rows:
        existing = r.get("placement") or {}
        if force or existing.get("status") not in {"done", "skipped"}:
            todo.append(r)
    if limit is not None:
        todo = todo[:limit]

    intake = Path(ledger.get("intake") or config_intake(cfg))
    done = 0
    progress = Progress(cfg, "map", len(todo))
    for i, row in enumerate(todo, start=1):
        try:
            path = intake / row["rel_path"]
            progress.tick(i, row["rel_path"])
            extracted = extract_record(path, intake)
            place_one(cfg, row, extracted, system=system, allowed=allowed)
            save_ledger(cfg, ledger)
            write_decision(cfg, row)
            if (row.get("placement") or {}).get("status") in {"done", "skipped"}:
                done += 1
        except OPERATOR_STOP:
            raise
        except Exception as exc:
            note_file_failure(cfg, ledger, row, stage="map", exc=exc)

    progress.finish(done)
    stats = write_placement_artifacts(cfg, map_doc)
    print(
        f"topic map: {stats['documents']} placed, "
        f"{stats['needs_review']} needs_review → {output_dir(cfg) / 'TOPIC-MAP.md'}"
    )
    return done
