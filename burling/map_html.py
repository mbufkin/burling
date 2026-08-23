"""Interactive HTML sunburst from taxonomy placements (product topic map).

Best practice: sector size = document count, not importance. Facet tabs
re-slice the same documents without re-running the model. The wheel is
a custom SVG — no Plotly, no React, no build step. Open the file in a
browser.

Design: DISD navy, product-demo finish. Tokens stay in a small family
(navy, mid blue, cream, one alert red). Sharp corners and hairline
rules — no glass, no stacked shadows, no rounded-everything. Copy stays
published: no dump, no repo paths, no method names.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path, PurePosixPath
from string import Template

from burling.io_util import atomic_write

FACETS = ("program", "function", "audience", "record_type", "lifecycle")
FACET_LABELS = {
    "program": "Program",
    "function": "Function",
    "audience": "Audience",
    "record_type": "Record",
    "lifecycle": "Lifecycle",
}

# DISD family only. Largest buckets get the stronger mid-blue so the
# eye lands on volume first. Unmapped stays warm stone — never brand red.
_PALETTE = [
    "#1a6fa8",
    "#0b3a5b",
    "#3d7fa8",
    "#003366",
    "#5a93b0",
    "#164866",
    "#4a7a94",
    "#2a5a78",
    "#6b8fa3",
    "#0e4a6b",
    "#3a6a82",
    "#1c5570",
]
_ROOT = "#051c2e"
_UNMAPPED = "#6e675c"
_SLICE_LINE = "#07263d"
# File-level slices: paper tints so navy type reads at a glance.
# Dark-on-dark is why the inner ring looked unreadable.
_LEAF = [
    "#efe4ce",
    "#e4d4b8",
    "#d8c6a6",
    "#f3ead8",
    "#cfc0a0",
    "#e8d7b4",
    "#d2c2a4",
    "#c4b496",
]
_INK = "#07263d"
_CREAM = "#f3ead8"

# Boilerplate that eats the ring without adding meaning.
_PREFIXES = (
    "copy of ",
    "[external facing] ",
    "dallas isd cte ",
    "dallas isd ",
    "disd ",
    "ms cte ",
    "middle school ",
    "framework ",
    "ms ",
    "cte ",
)
_LEADING_DATE = re.compile(
    r"^(?:january|february|march|april|may|june|july|august|september|"
    r"october|november|december)\s+\d{1,2},\s+\d{4},?\s+",
    re.I,
)
# Hyphens become spaces before this runs: "2026-2027 x" → "2026 2027 x".
_YEAR_HEAD = re.compile(r"^(?:\d{2,4}\s+){1,2}")
_TRAIL_STAMP = re.compile(
    r"\s+\w+\s+\d{1,2},?\s+\d{1,2}[_:]\d{2}\s*(?:am|pm)?\s*$",
    re.I,
)
_TRAIL_YEAR = re.compile(r"\s+\d{4}\s*$")
_TRAIL_MDY = re.compile(r"\s+\d{1,2}\s+\d{1,2}\s+\d{2,4}\s*$")
_YEAR_SPAN = re.compile(r"\s+\d{4}\s+\d{2}\s+to\s+\d{4}\s+\d{2}\s*$", re.I)


def _color_for(term: str, index: int) -> str:
    if term == "unmapped":
        return _UNMAPPED
    return _PALETTE[index % len(_PALETTE)]


def _leaf_color(index: int) -> str:
    return _LEAF[index % len(_LEAF)]


def _ring_label(path: str, limit: int = 26) -> str:
    """Short slice text. Full filename stays in the brief.

    Best practice: strip shared prefixes (Copy of, DISD, dates) and cut
    on a word boundary. A 36-character dump will never fit a wedge.
    """
    stem = PurePosixPath(path).name
    if "." in stem:
        stem = stem.rsplit(".", 1)[0]
    text = re.sub(r"[\s_\-]+", " ", stem).strip()
    text = re.sub(r"\s*\(\d+\)\s*$", "", text)
    text = re.sub(r"\s*\(responses\)\s*$", "", text, flags=re.I)
    text = _LEADING_DATE.sub("", text)
    text = _YEAR_HEAD.sub("", text)
    text = _TRAIL_STAMP.sub("", text)
    text = _TRAIL_MDY.sub("", text)
    text = _YEAR_SPAN.sub("", text)
    text = _TRAIL_YEAR.sub("", text)
    lowered = text.lower()
    changed = True
    while changed:
        changed = False
        for prefix in _PREFIXES:
            if lowered.startswith(prefix):
                text = text[len(prefix) :]
                lowered = text.lower().lstrip()
                text = text.strip()
                changed = True
    text = _YEAR_HEAD.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if not text:
        text = PurePosixPath(path).stem
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut if len(cut) >= 8 else text[:limit]


def _pretty_term(term: str) -> str:
    """Published label from a kebab or slug.

    Best practice: the map stores machine ids; the page shows English.
    Keep CTE / WBL as acronyms. Leave *and* small after the first word
    so the ranked list reads like a contents page, not a dump of keys.
    """
    key = term.replace("_", "-").strip().lower()
    specials = {
        "unmapped": "Unmapped",
        "needs-review": "Needs review",
        "needs review": "Needs review",
    }
    if key in specials:
        return specials[key]
    words = key.replace("-", " ").split()
    small = {"and", "of", "the", "for"}
    out: list[str] = []
    for i, word in enumerate(words):
        if word in {"cte", "wbl"}:
            out.append(word.upper())
        elif i > 0 and word in small:
            out.append(word)
        else:
            out.append(word.capitalize())
    # Match the sunburst: "Curriculum & Instruction", not "and instruction".
    return " ".join(out).replace(" and ", " & ")


def _is_hole(term: str) -> bool:
    """Unmapped / needs-review are the two holes the masthead must call out."""
    return term.replace("_", "-").replace(" ", "-").lower() in {
        "unmapped",
        "needs-review",
    }


def _sunburst_payload(placements: list[dict], facet: str) -> dict:
    buckets: dict[str, list[dict]] = {}
    for p in placements:
        terms = p.get(facet) or ["unmapped"]
        primary = terms[0] if terms else "unmapped"
        buckets.setdefault(primary, []).append(p)

    ids: list[str] = ["root"]
    parents: list[str] = [""]
    labels: list[str] = ["CTE"]
    values: list[int] = [len(placements)]
    colors: list[str] = [_ROOT]
    text_colors: list[str] = [_CREAM]
    custom: list[str] = [
        json.dumps(
            {
                "kind": "root",
                "facet": facet,
                "count": len(placements),
                "title": f"By {facet.replace('_', ' ')}",
                "note": "Ring size is document count, not importance.",
            }
        )
    ]

    for i, term in enumerate(sorted(buckets, key=lambda t: (-len(buckets[t]), t))):
        members = buckets[term]
        term_id = f"term::{term}"
        ids.append(term_id)
        parents.append("root")
        labels.append(term.replace("-", " "))
        values.append(len(members))
        colors.append(_color_for(term, i))
        text_colors.append(_CREAM)

        file_labels: list[str] = []
        doc_rows: list[str] = []
        for j, p in enumerate(
            sorted(members, key=lambda x: (x.get("rel_path") or "").lower())
        ):
            path = p.get("rel_path") or p.get("doc_id") or "?"
            short = path.split("/")[-1]
            ring = _ring_label(path)
            file_labels.append(ring)
            ids.append(f"doc::{facet}::{path}")
            parents.append(term_id)
            labels.append(ring)
            values.append(1)
            colors.append(_leaf_color(j))
            text_colors.append(_INK)
            doc_rows.append(
                json.dumps(
                    {
                        "kind": "doc",
                        "facet": facet,
                        "term": term,
                        "title": short,
                        "ring": ring,
                        "path": path,
                        "conf": round(float(p.get("confidence") or 0), 2),
                        "program": ", ".join(p.get("program") or []),
                        "function": ", ".join(p.get("function") or []),
                        "audience": ", ".join(p.get("audience") or []),
                        "needs_review": bool(p.get("needs_review")),
                        "note": (p.get("handoff_note") or p.get("rationale") or "")[:280],
                    }
                )
            )

        custom.append(
            json.dumps(
                {
                    "kind": "term",
                    "facet": facet,
                    "term": term,
                    "count": len(members),
                    "title": term.replace("-", " "),
                    "files": file_labels,
                }
            )
        )
        custom.extend(doc_rows)

    return {
        "ids": ids,
        "parents": parents,
        "labels": labels,
        "values": values,
        "marker": {
            "colors": colors,
            "line": {"width": 2, "color": _SLICE_LINE},
        },
        "textfont": {
            "family": "Source Sans 3, sans-serif",
            "size": 15,
            "color": text_colors,
        },
        "customdata": custom,
        "branchvalues": "total",
        "hovertemplate": "<b>%{label}</b><br>%{value}<extra></extra>",
        "textinfo": "label",
        # Radial uses the depth of the ring — better than horizontal
        # on a thin wedge. uniformtext.hide drops anything too small.
        "insidetextorientation": "auto",
        "maxdepth": 2,
        "sort": False,
        "leaf": {"opacity": 1},
    }


def browse_sunburst_payload(nodes: list[object], assignments: list[dict] | None = None) -> dict:
    """Three-ring sunburst: topic → subtopic → files, with unique path ids.

    Best practice (ISO 2.42 / SKOS): ``trailer-compliance`` is one concept.
    Plotly cannot reuse an id under two parents, so we emit
    ``compliance/trailer-compliance`` and ``mobile-lab/trailer-compliance``
    and stash the same ``concept_id`` in customdata. Inventory counts a
    file once; browse may show it twice.
    """
    by_id = {n.id: n for n in nodes}
    notes = {
        (a.get("rel_path") or ""): (a.get("summary") or a.get("handoff_note") or "")[:280]
        for a in assignments or []
    }
    topics = [n for n in nodes if n.kind == "topic" and n.id != "needs-review"]
    topics.sort(key=lambda n: (-len(n.docs), n.label))
    children_of: dict[str, list] = {}
    for n in nodes:
        if n.kind == "topic":
            continue
        for bt in n.broader:
            children_of.setdefault(bt, []).append(n)

    ids = ["root"]
    parents = [""]
    labels = ["CTE"]
    values = [sum(len(t.docs) for t in topics) or 1]
    colors = [_ROOT]
    text_colors = [_CREAM]
    # Plotly needs values[0] = sum(children). The brief shows unique files
    # so a two-parent concept does not look like a 1,234-document collection.
    unique_n = len({d for t in topics for d in t.docs})
    custom = [
        json.dumps(
            {
                "kind": "root",
                "facet": "browse",
                "count": unique_n,
                "title": "Dallas ISD CTE",
                "note": "Some groups appear under more than one topic. Ring size is document count.",
            }
        )
    ]

    for i, topic in enumerate(topics):
        tid = f"topic::{topic.id}"
        kids = sorted(children_of.get(topic.id) or [], key=lambda n: (-len(n.docs), n.label))
        # Only docs that actually sit under this topic. Empty ∩ used to
        # fall through to *all* kid.docs and blow the Plotly total.
        kid_sets: list[tuple[object, list[str]]] = []
        placed: set[str] = set()
        for kid in kids:
            inter = sorted(set(kid.docs) & set(topic.docs))
            if not inter:
                continue
            kid_sets.append((kid, inter))
            placed.update(inter)
        leftovers = sorted(set(topic.docs) - placed)
        if not kid_sets and not leftovers:
            continue
        topic_idx = len(ids)
        ids.append(tid)
        parents.append("root")
        labels.append(topic.label)
        values.append(0)  # filled after children — Plotly total = sum(kids)
        colors.append(_color_for(topic.id, i))
        text_colors.append(_CREAM)
        custom.append(
            json.dumps(
                {
                    "kind": "term",
                    "facet": "browse",
                    "term": topic.id,
                    "concept_id": topic.id,
                    "count": len(placed) + len(leftovers),
                    "title": topic.label,
                    "note": topic.description or "Click a slice to open subtopics.",
                    "files": [],
                }
            )
        )
        child_sum = 0
        for kid, kid_docs in kid_sets:
            kid_id = f"{topic.id}/{kid.id}"
            ids.append(kid_id)
            parents.append(tid)
            labels.append(kid.label)
            values.append(len(kid_docs))
            child_sum += len(kid_docs)
            colors.append(_color_for(kid.id, i + 3))
            text_colors.append(_CREAM)
            other = [by_id[b].label for b in kid.broader if b != topic.id and b in by_id]
            also = f" Also under {', '.join(other)}." if other else ""
            file_labels = [_ring_label(p) for p in kid_docs]
            custom.append(
                json.dumps(
                    {
                        "kind": "term",
                        "facet": "browse",
                        "term": kid.id,
                        "concept_id": kid.id,
                        "count": len(kid_docs),
                        "title": kid.label,
                        "note": (kid.description or "") + also,
                        "files": file_labels[:40],
                    }
                )
            )
            for j, path in enumerate(kid_docs):
                short = path.split("/")[-1]
                ids.append(f"{kid_id}/{path}")
                parents.append(kid_id)
                labels.append(_ring_label(path))
                values.append(1)
                colors.append(_leaf_color(j))
                text_colors.append(_INK)
                custom.append(
                    json.dumps(
                        {
                            "kind": "doc",
                            "facet": "browse",
                            "term": kid.id,
                            "concept_id": kid.id,
                            "title": short,
                            "ring": _ring_label(path),
                            "path": path,
                            "note": notes.get(path, ""),
                        }
                    )
                )
        if leftovers:
            bin_id = f"{topic.id}/__other"
            ids.append(bin_id)
            parents.append(tid)
            labels.append("Other")
            values.append(len(leftovers))
            child_sum += len(leftovers)
            colors.append(_UNMAPPED)
            text_colors.append(_CREAM)
            custom.append(
                json.dumps(
                    {
                        "kind": "term",
                        "facet": "browse",
                        "term": f"{topic.id}-other",
                        "concept_id": topic.id,
                        "count": len(leftovers),
                        "title": f"Other · {topic.label}",
                        "note": "In this topic, not yet in a subtopic.",
                        "files": [_ring_label(p) for p in leftovers[:40]],
                    }
                )
            )
            for j, path in enumerate(leftovers):
                ids.append(f"{bin_id}/{path}")
                parents.append(bin_id)
                labels.append(_ring_label(path))
                values.append(1)
                colors.append(_leaf_color(j))
                text_colors.append(_INK)
                custom.append(
                    json.dumps(
                        {
                            "kind": "doc",
                            "facet": "browse",
                            "term": topic.id,
                            "title": path.split("/")[-1],
                            "path": path,
                            "note": notes.get(path, ""),
                        }
                    )
                )
        values[topic_idx] = child_sum

    values[0] = sum(values[i] for i, p in enumerate(parents) if p == "root")
    payload = {
        "ids": ids,
        "parents": parents,
        "labels": labels,
        "values": values,
        "marker": {
            "colors": colors,
            "line": {"width": 2, "color": _SLICE_LINE},
        },
        "textfont": {
            "family": "Source Sans 3, sans-serif",
            "size": 15,
            "color": text_colors,
        },
        "customdata": custom,
        "branchvalues": "total",
        "hovertemplate": "<b>%{label}</b><br>%{value}<extra></extra>",
        "textinfo": "label",
        "insidetextorientation": "auto",
        "maxdepth": 3,
        "sort": False,
        "leaf": {"opacity": 1},
    }
    return payload


# Template uses $placeholders so CSS/JS braces stay readable.
# Keep $ out of CSS (custom properties use --token, not $).
_HTML = Template(
    """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Dallas ISD CTE — Topic map</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;500&family=Source+Sans+3:wght@400;500;600&display=swap" rel="stylesheet" />
  <style>
    :root {
      --navy: #0b3a5b;
      --navy-deep: #07263d;
      --navy-ink: #051828;
      --blue: #003366;
      --blue-mid: #1a6fa8;
      --red: #b91c1c;
      --paper: #f3ead8;
      --paper-soft: #c4b8a0;
      --paper-muted: #8a8070;
      --rule: #1a4460;
      --alert: #e8b4b4;
      --sans: "Source Sans 3", "Segoe UI", sans-serif;
      --serif: "Newsreader", Georgia, serif;
    }

    * { box-sizing: border-box; }

    html, body { margin: 0; min-height: 100%; }

    html { color-scheme: dark; }

    body {
      font-family: var(--sans);
      background: var(--navy-deep);
      color: var(--paper);
      line-height: 1.5;
    }

    /* Paper grain: texture, not decoration. Opacity stays low so type wins. */
    body::after {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 40;
      opacity: 0.04;
      background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 400 400' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='g'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23g)'/%3E%3C/svg%3E");
      background-size: 400px 400px;
    }

    /* Edge-to-edge product chrome. Institution first, then the tool. */
    .brandbar {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 16px;
      padding: 14px clamp(20px, 3vw, 48px);
      border-bottom: 1px solid var(--rule);
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--paper-soft);
    }

    .brandbar span:last-child { color: var(--paper-muted); }

    /*
      Off the 1180px rail. The page uses the viewport; only prose
      keeps a measure. Butterick: 45–90 characters. Few: size regions
      by importance, not a rigid column.
    */
    .page {
      width: 100%;
      max-width: none;
      margin: 0;
      padding: 40px clamp(20px, 3vw, 48px) 64px;
    }

    .masthead {
      display: grid;
      grid-template-columns: minmax(20rem, 38rem) minmax(16rem, 1fr);
      column-gap: clamp(40px, 6vw, 96px);
      row-gap: 36px;
      align-items: start;
    }

    .eyebrow {
      margin: 0 0 16px;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--paper-muted);
    }

    h1 {
      margin: 0 0 24px;
      font-family: var(--serif);
      font-size: clamp(40px, 4.2vw, 64px);
      font-weight: 400;
      letter-spacing: -0.02em;
      line-height: 1.08;
    }

    h1 em {
      font-style: italic;
      color: var(--blue-mid);
    }

    /*
      Hierarchy: one fact owns the page. Brand --red fails on navy
      (~2.4:1); --alert stays readable.
    */
    .lead-stat {
      display: flex;
      align-items: baseline;
      gap: 20px;
      margin: 0 0 20px;
      padding: 0;
    }

    .lead-stat-figure {
      font-family: var(--serif);
      font-size: clamp(48px, 7vw, 72px);
      font-weight: 400;
      line-height: 0.9;
      letter-spacing: -0.03em;
      color: var(--alert);
    }

    .lead-stat-copy {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .lead-stat-copy strong {
      font-size: 18px;
      font-weight: 600;
      color: var(--paper);
    }

    .lead-stat-copy span {
      font-size: 14px;
      color: var(--paper-muted);
    }

    .lede {
      margin: 0;
      max-width: 66ch;
      font-size: 16px;
      line-height: 1.6;
      color: var(--paper-soft);
    }

    .placements {
      margin: 0;
      padding: 0;
      border: 0;
      max-width: 28rem;
      width: 100%;
      justify-self: end;
    }

    .programs {
      display: grid;
      gap: 0;
      margin: 0;
      padding: 0;
      list-style: none;
    }

    .programs li {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 16px;
      align-items: baseline;
      padding: 9px 0;
      border-bottom: 1px solid var(--rule);
      font-size: 14px;
      color: var(--paper-soft);
    }

    .programs li.is-lead { color: var(--paper); }

    .programs b {
      font-family: var(--serif);
      font-weight: 400;
      font-size: 18px;
      font-variant-numeric: tabular-nums;
    }

    .stage {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(260px, 22rem);
      gap: 32px clamp(28px, 3vw, 48px);
      margin-top: 40px;
      padding-top: 28px;
      border-top: 1px solid var(--rule);
    }

    .stage-label {
      margin: 0 0 14px;
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--paper-muted);
    }

    .facets {
      display: flex;
      flex-wrap: wrap;
      gap: 4px 28px;
      margin-bottom: 8px;
    }

    .facet {
      appearance: none;
      background: none;
      border: 0;
      border-bottom: 2px solid transparent;
      padding: 6px 0 8px;
      margin: 0;
      color: var(--paper-muted);
      font-family: var(--sans);
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      cursor: pointer;
    }

    .facet:hover { color: var(--paper); }

    .facet[aria-selected="true"] {
      color: var(--paper);
      border-bottom-color: var(--blue-mid);
    }

    .facet:focus-visible {
      outline: 2px solid var(--blue-mid);
      outline-offset: 4px;
    }

    /* Circle needs height as well as width or extra pixels just pad the plot. */
    #sunburst {
      width: 100%;
      height: clamp(560px, 78vh, 900px);
    }

    #sunburst svg {
      display: block;
      width: 100%;
      height: 100%;
    }

    #sunburst .slice {
      cursor: pointer;
      transition: opacity 160ms ease;
    }

    #sunburst .slice.is-dim { opacity: 0.28; }

    #sunburst .slice-label {
      pointer-events: none;
      font-family: var(--sans);
      font-weight: 600;
      text-anchor: middle;
      dominant-baseline: middle;
    }

    #sunburst .hub { cursor: pointer; }

    #sunburst .hub circle { fill: var(--navy-ink); }

    #sunburst .hub-title {
      font-family: var(--serif);
      font-size: 22px;
      fill: var(--paper);
      text-anchor: middle;
    }

    #sunburst .hub-sub {
      font-family: var(--sans);
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      fill: var(--paper-muted);
      text-anchor: middle;
    }

    .crumb {
      margin: 10px 0 8px;
      font-size: 12px;
      color: var(--paper-soft);
    }

    .crumb b {
      font-weight: 600;
      color: var(--paper);
    }

    .hint {
      margin: 8px 0 0;
      font-size: 12px;
      color: var(--paper-muted);
    }

    .brief { padding-top: 8px; }

    .brief-kicker {
      margin: 0 0 10px;
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--blue-mid);
    }

    .brief h2 {
      margin: 0 0 10px;
      font-family: var(--serif);
      font-size: 26px;
      font-weight: 400;
      line-height: 1.2;
    }

    .brief p {
      margin: 0 0 14px;
      font-size: 14px;
      line-height: 1.55;
      color: var(--paper-soft);
    }

    .brief dl {
      margin: 0;
      display: grid;
      gap: 10px;
    }

    .brief dt {
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--paper-muted);
    }

    .brief dd {
      margin: 3px 0 0;
      font-size: 14px;
      color: var(--paper);
      word-break: break-word;
    }

    /* Default brief: numbered how-to so the rail is never an empty hole. */
    .guide {
      margin: 22px 0 0;
      padding: 0;
      list-style: none;
      counter-reset: guide;
      border-top: 1px solid var(--rule);
    }

    .guide li {
      counter-increment: guide;
      display: grid;
      grid-template-columns: 1.4rem 1fr;
      gap: 10px;
      padding: 12px 0;
      border-bottom: 1px solid var(--rule);
      font-size: 13px;
      line-height: 1.45;
      color: var(--paper-soft);
    }

    .guide li::before {
      content: counter(guide);
      font-family: var(--serif);
      font-size: 16px;
      color: var(--blue-mid);
    }

    .flag {
      display: inline-block;
      margin-top: 12px;
      padding: 3px 0;
      color: var(--alert);
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }

    .file-list {
      margin: 16px 0 0;
      padding: 0;
      list-style: none;
      border-top: 1px solid var(--rule);
    }

    .file-list li {
      padding: 8px 0;
      border-bottom: 1px solid var(--rule);
      font-size: 14px;
      line-height: 1.35;
      color: var(--paper);
    }

    footer {
      margin-top: 48px;
      padding-top: 20px;
      border-top: 1px solid var(--rule);
      color: var(--paper-muted);
      font-size: 12px;
    }

    footer span { margin: 0 0.4em; color: var(--rule); }

    @media (max-width: 1040px) {
      .masthead { grid-template-columns: 1fr; }
      .placements {
        justify-self: stretch;
        max-width: 36rem;
        margin-top: 4px;
        padding-top: 20px;
        border-top: 1px solid var(--rule);
      }
    }

    @media (max-width: 860px) {
      .brandbar { padding: 12px 16px; }
      .page { padding: 28px 16px 48px; }
      .lead-stat { flex-wrap: wrap; gap: 12px 16px; }
      .stage { grid-template-columns: 1fr; gap: 20px; }
      .brief { padding-top: 0; }
      #sunburst { height: 520px; }
    }
  </style>
</head>
<body>
  <div class="brandbar">
    <span>Dallas ISD</span>
    <span>Career &amp; Technical Education</span>
  </div>
  <div class="page">
    <header class="masthead">
      <div class="masthead-copy">
        <p class="eyebrow">Collection map</p>
        <h1>Topic <em>map</em></h1>
        <p class="lead-stat">
          <span class="lead-stat-figure">$n_review</span>
          <span class="lead-stat-copy">
            <strong>Flagged for review</strong>
            <span>of $n documents in the collection</span>
          </span>
        </p>
        <p class="lede">
          Every file in Career &amp; Technical Education, grouped the way
          the work actually runs. Switch a view to recut the same collection.
          Ring size is count, not importance.
        </p>
      </div>

      <div class="placements">
        <p class="stage-label">Largest groups</p>
        <ol class="programs">$program_items</ol>
      </div>
    </header>

    <section class="stage">
      <div>
        <p class="stage-label">View</p>
        <div class="facets" role="tablist" aria-label="Collection view">$facet_buttons</div>
        <p class="crumb" id="crumb"><b>Full collection</b> · hover a slice to preview</p>
        <div id="sunburst" role="img" aria-label="Topic sunburst"></div>
        <p class="hint">Click a slice to open it. Click the center to return.</p>
      </div>
      <aside class="brief" id="brief" aria-live="polite"></aside>
    </section>

    <footer>
      Dallas ISD Career and Technical Education
      <span>·</span>
      Collection map
    </footer>
  </div>
  <script>
    const FIGURES = $figures_json;
    const FACET_LABELS = $facet_labels_json;
    const DOC_COUNT = $n;
    const brief = document.getElementById("brief");
    const crumb = document.getElementById("crumb");
    let currentFacet = "$default_facet";

    function idleBrief() {
      return {
        kind: "root",
        title: "Dallas ISD CTE",
        count: DOC_COUNT,
        facet: currentFacet,
        note: "Hover a ring to preview a group. Click a slice to open it — the brief stays until you choose another.",
      };
    }

    let pinned = idleBrief();

    function parseMeta(raw) {
      if (raw && typeof raw === "object" && !Array.isArray(raw)) return raw;
      try { return JSON.parse(raw); } catch (_) { return { title: String(raw || "") }; }
    }

    function escapeHtml(s) {
      return String(s || "").replace(/[&<>"]/g, function (c) {
        return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c];
      });
    }

    function rootCrumb() {
      if (currentFacet === "browse") {
        return "<b>Full collection</b> · hover a slice to preview";
      }
      const label = (FACET_LABELS[currentFacet] || currentFacet).toLowerCase();
      return "<b>By " + escapeHtml(label) + "</b> · hover a slice to preview";
    }

    function setCrumb(meta) {
      const m = meta || idleBrief();
      if (m.kind === "doc") {
        crumb.innerHTML = "<b>" + escapeHtml((m.term || "").replace(/-/g, " ")) + "</b> · " + escapeHtml(m.ring || m.title || "");
      } else if (m.kind === "term") {
        crumb.innerHTML = "<b>" + escapeHtml(m.title || "") + "</b> · " + (m.count || 0) + " files";
      } else {
        crumb.innerHTML = rootCrumb();
      }
    }

    function renderBrief(meta) {
      const m = meta || idleBrief();
      const isRoot = m.kind === "root";
      const kicker = m.kind === "doc"
        ? "Document"
        : (m.kind === "term" ? (FACET_LABELS[m.facet] || m.facet) : "Collection");
      const countLine = m.kind === "doc"
        ? ""
        : "<p>" + (m.count || 0) + " documents" + (m.facet && !isRoot ? " · " + (FACET_LABELS[m.facet] || m.facet).toLowerCase() : "") + "</p>";
      const rows = [];
      if (m.path) rows.push(["Path", m.path]);
      if (m.program) rows.push(["Program", m.program]);
      if (m.function) rows.push(["Function", m.function]);
      if (m.audience) rows.push(["Audience", m.audience]);
      if (m.conf !== undefined && m.kind === "doc") rows.push(["Confidence", Number(m.conf).toFixed(2)]);
      const dl = rows.length
        ? "<dl>" + rows.map(function (r) { return "<div><dt>" + r[0] + "</dt><dd>" + escapeHtml(r[1]) + "</dd></div>"; }).join("") + "</dl>"
        : "";
      const flag = m.needs_review ? '<span class="flag">Needs review</span>' : "";
      const note = m.note ? "<p>" + escapeHtml(m.note) + "</p>" : "";
      const files = (m.files && m.files.length)
        ? '<ol class="file-list">' + m.files.map(function (f) { return "<li>" + escapeHtml(f) + "</li>"; }).join("") + "</ol>"
        : "";
      const guide = isRoot
        ? '<ol class="guide"><li>Ring size is document count, not importance.</li><li>The inner ring is the group. The outer ring is the next level.</li><li>Click the center to return to the full map.</li></ol>'
        : "";
      brief.innerHTML = '<p class="brief-kicker">' + escapeHtml(kicker) + "</p><h2>" + escapeHtml(m.title || "") + "</h2>" + countLine + note + dl + files + flag + guide;
      setCrumb(m);
    }

    const host = document.getElementById("sunburst");
    const NS = "http://www.w3.org/2000/svg";
    const trees = {};
    let focusId = "root";

    function prettyLabel(s) {
      return String(s || "").replace(/\bCte\b/g, "CTE").replace(/\bWbl\b/g, "WBL");
    }

    function isDoc(node) {
      return !!(node.meta && node.meta.kind === "doc");
    }

    function textColor(hex) {
      const c = String(hex || "").replace("#", "");
      if (c.length < 6) return "#f3ead8";
      const r = parseInt(c.slice(0, 2), 16);
      const g = parseInt(c.slice(2, 4), 16);
      const b = parseInt(c.slice(4, 6), 16);
      const L = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
      return L > 0.55 ? "#07263d" : "#f3ead8";
    }

    function buildTree(fig) {
      const nodes = {};
      const colors = (fig.marker && fig.marker.colors) || [];
      const custom = fig.customdata || [];
      for (let i = 0; i < fig.ids.length; i++) {
        const id = fig.ids[i];
        nodes[id] = {
          id: id,
          label: fig.labels[i],
          value: fig.values[i] || 0,
          color: colors[i] || "#1a6fa8",
          meta: parseMeta(custom[i]),
          children: [],
          parent: null,
        };
      }
      let root = null;
      for (let i = 0; i < fig.ids.length; i++) {
        const id = fig.ids[i];
        const parentId = fig.parents[i];
        if (!parentId) {
          root = nodes[id];
        } else if (nodes[parentId]) {
          nodes[id].parent = nodes[parentId];
          nodes[parentId].children.push(nodes[id]);
        }
      }
      return { root: root, nodes: nodes };
    }

    function treeFor(facet) {
      if (!trees[facet]) trees[facet] = buildTree(FIGURES[facet]);
      return trees[facet];
    }

    // Two rings from the focused node. At the collection root, file
    // leaves stay hidden — 670 slivers are texture, not a map.
    function layoutFrom(focus) {
      const drawn = [];
      const start = -Math.PI / 2;
      function rec(node, a0, a1, depth) {
        node.x0 = a0;
        node.x1 = a1;
        node.depth = depth;
        if (node !== focus) drawn.push(node);
        if (depth >= 2) return;
        let kids = node.children || [];
        // File leaves only when this node is the open group and
        // every child is a file. Otherwise they read as static.
        const showingFiles = node === focus && kids.length > 0 && kids.every(isDoc);
        if (!showingFiles) {
          kids = kids.filter(function (k) { return !isDoc(k); });
        }
        let total = 0;
        for (let i = 0; i < kids.length; i++) total += kids[i].value || 0;
        if (!total) return;
        let a = a0;
        for (let i = 0; i < kids.length; i++) {
          const span = (a1 - a0) * ((kids[i].value || 0) / total);
          rec(kids[i], a, a + span, depth + 1);
          a += span;
        }
      }
      rec(focus, start, start + Math.PI * 2, 0);
      return drawn;
    }

    function sectorPath(cx, cy, r0, r1, a0, a1) {
      const large = (a1 - a0) > Math.PI ? 1 : 0;
      function pt(r, a) {
        return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
      }
      const p0 = pt(r1, a0);
      const p1 = pt(r1, a1);
      const p2 = pt(r0, a1);
      const p3 = pt(r0, a0);
      return "M" + p0[0] + "," + p0[1]
        + " A" + r1 + "," + r1 + " 0 " + large + " 1 " + p1[0] + "," + p1[1]
        + " L" + p2[0] + "," + p2[1]
        + " A" + r0 + "," + r0 + " 0 " + large + " 0 " + p3[0] + "," + p3[1]
        + " Z";
    }

    function padded(node) {
      const span = node.x1 - node.x0;
      const pad = Math.min(0.016, span * 0.16);
      if (span - pad < 0.006) return [node.x0, node.x1];
      return [node.x0 + pad / 2, node.x1 - pad / 2];
    }

    function setHot(id) {
      const paths = host.querySelectorAll(".slice");
      if (!id) {
        for (let i = 0; i < paths.length; i++) {
          paths[i].classList.remove("is-dim", "is-hot");
        }
        return;
      }
      const hot = {};
      let n = treeFor(currentFacet).nodes[id];
      while (n) {
        hot[n.id] = true;
        n = n.parent;
      }
      for (let i = 0; i < paths.length; i++) {
        const hid = paths[i].getAttribute("data-id");
        paths[i].classList.toggle("is-hot", !!hot[hid]);
        paths[i].classList.toggle("is-dim", !hot[hid]);
      }
    }

    function addLabel(svg, node, cx, cy, r0, r1, a0, a1) {
      const span = a1 - a0;
      const r = (r0 + r1) / 2;
      const minArc = isDoc(node) ? 58 : 40;
      if (span * r < minArc) return;
      const mid = (a0 + a1) / 2;
      const x = cx + r * Math.cos(mid);
      const y = cy + r * Math.sin(mid);
      const deg = mid * 180 / Math.PI;
      const rot = (deg > 90 || deg < -90) ? deg + 180 : deg;
      const text = document.createElementNS(NS, "text");
      text.setAttribute("class", "slice-label");
      text.setAttribute("transform", "translate(" + x + "," + y + ") rotate(" + rot + ")");
      text.setAttribute("fill", textColor(node.color));
      text.setAttribute("font-size", node.depth === 1 ? "12.5" : "11");
      text.textContent = prettyLabel(node.label);
      svg.appendChild(text);
    }

    function zoomTo(node) {
      if (node && node.children && node.children.length) {
        focusId = node.id;
        pinned = node.meta && node.meta.kind ? node.meta : idleBrief();
      } else if (node) {
        pinned = node.meta || { title: node.label };
      }
      renderWheel();
      renderBrief(pinned);
    }

    function zoomOut(focus) {
      if (focus && focus.parent) {
        focusId = focus.parent.id;
        pinned = focus.parent.meta && focus.parent.meta.kind
          ? focus.parent.meta
          : idleBrief();
      } else {
        focusId = "root";
        pinned = idleBrief();
      }
      renderWheel();
      renderBrief(pinned);
    }

    function renderWheel() {
      const built = treeFor(currentFacet);
      const focus = (built.nodes[focusId] || built.root);
      if (!focus) return;
      const drawn = layoutFrom(focus);
      let maxD = 1;
      for (let i = 0; i < drawn.length; i++) {
        if (drawn[i].depth > maxD) maxD = drawn[i].depth;
      }

      const rect = host.getBoundingClientRect();
      const S = Math.max(280, Math.floor(Math.min(rect.width, rect.height)));
      const cx = S / 2;
      const cy = S / 2;
      const R = S / 2 - 6;
      const hubR = R * 0.30;
      const rings = maxD <= 1
        ? { 1: [hubR + 8, R] }
        : { 1: [hubR + 8, R * 0.62], 2: [R * 0.655, R] };

      host.innerHTML = "";
      const svg = document.createElementNS(NS, "svg");
      svg.setAttribute("viewBox", "0 0 " + S + " " + S);
      svg.setAttribute("width", "100%");
      svg.setAttribute("height", "100%");
      svg.setAttribute("aria-hidden", "true");

      for (let i = 0; i < drawn.length; i++) {
        const node = drawn[i];
        const rr = rings[node.depth];
        if (!rr) continue;
        const ang = padded(node);
        if (ang[1] - ang[0] < 0.004) continue;
        const path = document.createElementNS(NS, "path");
        path.setAttribute("class", "slice");
        path.setAttribute("data-id", node.id);
        path.setAttribute("d", sectorPath(cx, cy, rr[0], rr[1], ang[0], ang[1]));
        path.setAttribute("fill", node.color);
        path.addEventListener("pointerenter", function () {
          setHot(node.id);
          renderBrief(node.meta);
        });
        path.addEventListener("pointerleave", function () {
          setHot(null);
          renderBrief(pinned);
        });
        path.addEventListener("click", function (ev) {
          ev.stopPropagation();
          zoomTo(node);
        });
        svg.appendChild(path);
      }

      for (let i = 0; i < drawn.length; i++) {
        const node = drawn[i];
        const rr = rings[node.depth];
        if (!rr) continue;
        const ang = padded(node);
        addLabel(svg, node, cx, cy, rr[0], rr[1], ang[0], ang[1]);
      }

      const hub = document.createElementNS(NS, "g");
      hub.setAttribute("class", "hub");
      const disc = document.createElementNS(NS, "circle");
      disc.setAttribute("cx", cx);
      disc.setAttribute("cy", cy);
      disc.setAttribute("r", hubR - 4);
      hub.appendChild(disc);
      const title = document.createElementNS(NS, "text");
      title.setAttribute("class", "hub-title");
      title.setAttribute("x", cx);
      const hubLabel = focus.id === "root" ? "CTE" : prettyLabel(focus.label);
      const words = hubLabel.split(" ");
      const lines = hubLabel.length <= 14 || words.length < 2
        ? [hubLabel]
        : [words.slice(0, Math.ceil(words.length / 2)).join(" "), words.slice(Math.ceil(words.length / 2)).join(" ")];
      if (lines.join(" ").length > 16) title.setAttribute("font-size", "15");
      const lineH = lines.length > 1 ? 18 : 0;
      title.setAttribute("y", cy - 4 - (lineH ? 8 : 0));
      lines.forEach(function (line, i) {
        const tspan = document.createElementNS(NS, "tspan");
        tspan.setAttribute("x", cx);
        tspan.setAttribute("dy", i === 0 ? "0" : "18");
        tspan.textContent = line;
        title.appendChild(tspan);
      });
      hub.appendChild(title);
      const sub = document.createElementNS(NS, "text");
      sub.setAttribute("class", "hub-sub");
      sub.setAttribute("x", cx);
      sub.setAttribute("y", cy + 18);
      const count = (focus.meta && focus.meta.count) || focus.value || DOC_COUNT;
      sub.textContent = focus.parent ? "Back" : (count + " files");
      hub.appendChild(sub);
      hub.addEventListener("click", function (ev) {
        ev.stopPropagation();
        zoomOut(focus);
      });
      svg.appendChild(hub);

      host.appendChild(svg);
    }

    function draw(facet) {
      currentFacet = facet;
      focusId = "root";
      pinned = idleBrief();
      document.querySelectorAll(".facet").forEach(function (btn) {
        btn.setAttribute("aria-selected", btn.dataset.facet === facet ? "true" : "false");
      });
      renderWheel();
      renderBrief(pinned);
    }

    if (window.ResizeObserver) {
      new ResizeObserver(function () { renderWheel(); }).observe(host);
    } else {
      window.addEventListener("resize", function () { renderWheel(); });
    }

    document.querySelector(".facets").addEventListener("click", function (e) {
      const btn = e.target.closest(".facet");
      if (!btn) return;
      draw(btn.dataset.facet);
    });

    renderBrief(idleBrief());
    draw("$default_facet");
  </script>
</body>
</html>
"""
)



def build_topic_map_html(data: dict) -> str:
    placements = data.get("placements") or []
    n = len(placements)
    n_review = sum(1 for p in placements if p.get("needs_review"))
    figures = {f: _sunburst_payload(placements, f) for f in FACETS}
    extra = data.get("browse_figure")
    labels = dict(FACET_LABELS)
    default_facet = "program"
    if extra:
        figures = {"browse": extra, **figures}
        labels = {"browse": "Topics", **labels}
        default_facet = "browse"
    top_prog = Counter((p.get("program") or ["unmapped"])[0] for p in placements)
    program_items = "".join(
        (
            '<li class="is-lead">' if _is_hole(k) else "<li>"
        )
        + f"<span>{_pretty_term(k)}</span><b>{v}</b></li>"
        for k, v in top_prog.most_common(6)
    )
    facet_buttons = "".join(
        f'<button class="facet" type="button" role="tab" data-facet="{key}"'
        f' aria-selected="{"true" if key == default_facet else "false"}">{label}</button>'
        for key, label in labels.items()
    )
    return _HTML.substitute(
        n=n,
        n_review=n_review,
        program_items=program_items,
        facet_buttons=facet_buttons,
        figures_json=json.dumps(figures),
        facet_labels_json=json.dumps(labels),
        default_facet=default_facet,
    )


def write_topic_map_html(path: Path, data: dict) -> None:
    atomic_write(path, build_topic_map_html(data))
