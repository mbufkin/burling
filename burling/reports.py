"""Human-readable plates: document map, delete candidates, review queue.

These are the HITL artifacts. JSON is the source of truth; Markdown is what you
read. The harness never deletes files — these lists are the work order.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from burling.io_util import atomic_write
from burling.ledger import load_ledger
from burling.paths import output_dir
from burling.trace import write_all_decisions


def _rows(ledger: dict) -> list[dict]:
    rows = list(ledger["documents"].values())
    rows.sort(key=lambda r: r.get("rel_path") or "")
    return rows


def write_reports(cfg: dict) -> dict:
    ledger = load_ledger(cfg)
    rows = _rows(ledger)
    out = output_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)

    map_md = _document_map(rows)
    queue_md = _review_queue(rows)
    delete_md = _delete_candidates(rows)
    summary_md = _summary(rows)

    pii_md = _pii_map(rows)
    atomic_write(out / "DOCUMENT-MAP.md", map_md)
    atomic_write(out / "PII-MAP.md", pii_md)
    atomic_write(out / "REVIEW-QUEUE.md", queue_md)
    atomic_write(out / "DELETE-CANDIDATES.md", delete_md)
    atomic_write(out / "SUMMARY.md", summary_md)
    write_all_decisions(cfg, rows)
    return {
        "documents": len(rows),
        "pii": sum(1 for r in rows if set(r.get("priors") or {}) & {"ssn", "address", "email", "phone", "dob", "credit_card"}),
        "delete_candidates": sum(
            1
            for r in rows
            if (r.get("pass2") or {}).get("recommendation") == "delete_candidate"
            and r.get("disposition") != "quarantined"
        ),
        "review": sum(
            1
            for r in rows
            if (r.get("pass2") or {}).get("recommendation") == "review"
            or not (r.get("extraction") or {}).get("ok")
        ),
    }


def _summary(rows: list[dict]) -> str:
    recs = Counter((r.get("pass2") or {}).get("recommendation") or "pending" for r in rows)
    tags = Counter()
    for r in rows:
        for t in (r.get("pass1") or {}).get("tags") or []:
            tags[t] += 1
    extract_fail = sum(1 for r in rows if not (r.get("extraction") or {}).get("ok"))
    ssn = sum(1 for r in rows if "ssn" in (r.get("priors") or {}))
    addr = sum(1 for r in rows if "address" in (r.get("priors") or {}))
    tag_lines = "\n".join(f"| {k} | {v} |" for k, v in tags.most_common()) or "| (none yet) | 0 |"
    return f"""# Handover review summary

**Documents in queue:** {len(rows)}
**Extract failed (human must open):** {extract_fail}
**Regex SSN hits:** {ssn}
**Regex address hits:** {addr}

Python tagged PII. The model only decided personal leftover vs work record.
Work files with PII (student immunization, travel) stay on `PII-MAP.md` but are not delete candidates.

## Pass 2 recommendations

| Recommendation | Count |
|---|---|
| delete_candidate (personal) | {recs.get("delete_candidate", 0)} |
| review | {recs.get("review", 0)} |
| keep (work) | {recs.get("keep", 0)} |
| pending | {recs.get("pending", 0)} |

## Pass 1 tag map

| Tag | Documents |
|---|---|
{tag_lines}

Nothing in this folder is deleted by the harness. Confirm `DELETE-CANDIDATES.md`
yourself, then move or delete those files by hand.
"""


def _pii_map(rows: list[dict]) -> str:
    """Inventory of identifier-shaped hits. Independent of keep/delete."""
    pii_kinds = {"ssn", "credit_card", "dob", "email", "phone", "address"}
    hits = [r for r in rows if set(r.get("priors") or {}) & pii_kinds]
    lines = [
        "# PII map",
        "",
        "Python regex hits only. Work records (immunization, travel) can appear here and still be keep.",
        "",
        f"**Files with PII-shaped text:** {len(hits)}",
        "",
    ]
    if not hits:
        lines.append("(none yet — run the Python priors pass)")
        lines.append("")
        return "\n".join(lines)
    lines.append("| Path | PII kinds | Severity | Custody / rec |")
    lines.append("|---|---|---|---|")
    for r in hits:
        kinds = ", ".join(k for k in (r.get("priors") or {}) if k in pii_kinds) or "—"
        p2 = r.get("pass2") or {}
        custody = p2.get("custody") or (r.get("pass1") or {}).get("custody") or "pending"
        rec = p2.get("recommendation") or "pending"
        lines.append(
            f"| `{r.get('rel_path')}` | {kinds} | {r.get('prior_severity')} | {custody} / {rec} |"
        )
    lines.append("")
    return "\n".join(lines)


def _document_map(rows: list[dict]) -> str:
    by_tag: dict[str, list[dict]] = defaultdict(list)
    untagged = []
    for r in rows:
        tags = (r.get("pass1") or {}).get("tags") or []
        if not tags:
            untagged.append(r)
            continue
        primary = (r.get("pass1") or {}).get("primary_tag") or tags[0]
        by_tag[primary].append(r)

    sections = ["# Document map", "", "First-pass tags. One document may have extra tags in the ledger.", ""]
    for tag in sorted(by_tag):
        sections.append(f"## {tag} ({len(by_tag[tag])})")
        sections.append("")
        for r in by_tag[tag]:
            extra = [t for t in ((r.get("pass1") or {}).get("tags") or []) if t != tag]
            extra_s = f"  extra: {', '.join(extra)}" if extra else ""
            summary = ((r.get("pass1") or {}).get("summary") or "").replace("\n", " ")
            sections.append(f"- `{r.get('rel_path')}`{extra_s}")
            if summary:
                sections.append(f"  - {summary}")
        sections.append("")
    if untagged:
        sections.append(f"## untagged / not yet pass-1 ({len(untagged)})")
        sections.append("")
        for r in untagged:
            err = (r.get("extraction") or {}).get("error")
            note = f"  — extract error: {err}" if err else ""
            sections.append(f"- `{r.get('rel_path')}`{note}")
        sections.append("")
    return "\n".join(sections)


def _delete_candidates(rows: list[dict]) -> str:
    hits = [
        r for r in rows
        if (r.get("pass2") or {}).get("recommendation") == "delete_candidate"
        and r.get("disposition") != "quarantined"
    ]
    lines = [
        "# Delete candidates",
        "",
        "The harness does **not** delete these. Check each path, then remove by hand.",
        "",
        f"**Count:** {len(hits)}",
        "",
    ]
    if not hits:
        lines.append("(none yet — run pass 2, or no personal files were found)")
        lines.append("")
        return "\n".join(lines)
    lines.append("| Path | Reasons | Priors | Fail-closed |")
    lines.append("|---|---|---|---|")
    for r in hits:
        p2 = r.get("pass2") or {}
        reasons = ", ".join(p2.get("reasons") or [])
        priors = ", ".join((r.get("priors") or {}).keys()) or "—"
        fc = "yes" if p2.get("fail_closed") else ""
        lines.append(f"| `{r.get('rel_path')}` | {reasons} | {priors} | {fc} |")
    lines.append("")
    return "\n".join(lines)


def _review_queue(rows: list[dict]) -> str:
    needs = []
    for r in rows:
        extract_ok = (r.get("extraction") or {}).get("ok")
        rec = (r.get("pass2") or {}).get("recommendation")
        if not extract_ok or rec == "review" or rec is None:
            needs.append(r)
    lines = [
        "# Review queue",
        "",
        "Human-in-the-loop leftovers: extract failures, model `review` flags, and files not yet through pass 2.",
        "",
        f"**Pending:** {len(needs)}",
        "",
    ]
    if not needs:
        lines.append("(queue empty)")
        lines.append("")
        return "\n".join(lines)
    lines.append("| Path | Why |")
    lines.append("|---|---|")
    for r in needs:
        extract_ok = (r.get("extraction") or {}).get("ok")
        p1 = r.get("pass1") or {}
        p2 = r.get("pass2") or {}
        if not extract_ok:
            why = f"extract failed: {(r.get('extraction') or {}).get('error')}"
        elif p1.get("status") == "skipped":
            why = f"pass 1 noted (run continued): {p1.get('error')}"
        elif p2.get("status") == "skipped":
            why = f"pass 2 noted (run continued): {p2.get('error') or p2.get('rationale')}"
        elif not r.get("pass1"):
            why = "waiting on pass 1"
        elif not r.get("pass2"):
            why = "waiting on pass 2"
        else:
            why = p2.get("rationale") or "model asked for review"
        lines.append(f"| `{r.get('rel_path')}` | {why} |")
    lines.append("")
    return "\n".join(lines)
