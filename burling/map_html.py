"""Interactive HTML sunburst from taxonomy placements (handoff topic map).

Best practice: sector size = document count. Facet switcher rotates
program / function / audience / record_type / lifecycle without re-running
the model. Plotly is loaded from CDN — open the file in a browser.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from burling.io_util import atomic_write

FACETS = ("program", "function", "audience", "record_type", "lifecycle")
_PALETTE = [
    "#4e79a7",
    "#f28e2b",
    "#e15759",
    "#76b7b2",
    "#59a14f",
    "#edc948",
    "#b07aa1",
    "#ff9da7",
    "#9c755f",
    "#bab0ab",
    "#86bcb6",
    "#8cd17d",
]


def _color_for(term: str, index: int) -> str:
    if term == "unmapped":
        return "#999999"
    return _PALETTE[index % len(_PALETTE)]


def _sunburst_payload(placements: list[dict], facet: str) -> dict:
    buckets: dict[str, list[dict]] = {}
    for p in placements:
        terms = p.get(facet) or ["unmapped"]
        primary = terms[0] if terms else "unmapped"
        buckets.setdefault(primary, []).append(p)

    ids: list[str] = ["root"]
    parents: list[str] = [""]
    labels: list[str] = [f"by {facet}"]
    values: list[int] = [len(placements)]
    colors: list[str] = ["#1f2937"]
    custom: list[str] = [f"{len(placements)} documents · taxonomy placement"]

    for i, term in enumerate(sorted(buckets, key=lambda t: (-len(buckets[t]), t))):
        members = buckets[term]
        term_id = f"term::{term}"
        ids.append(term_id)
        parents.append("root")
        labels.append(term)
        values.append(len(members))
        colors.append(_color_for(term, i))
        custom.append(f"{len(members)} docs · {facet}:{term}")

        for p in sorted(members, key=lambda x: (x.get("rel_path") or "").lower()):
            path = p.get("rel_path") or p.get("doc_id") or "?"
            short = path.split("/")[-1]
            ids.append(f"doc::{facet}::{path}")
            parents.append(term_id)
            labels.append(short[:48])
            values.append(1)
            colors.append(_color_for(term, i))
            bits = [
                path,
                f"conf={float(p.get('confidence') or 0):.2f}",
                f"program={', '.join(p.get('program') or [])}",
                f"function={', '.join(p.get('function') or [])}",
                f"audience={', '.join(p.get('audience') or [])}",
            ]
            if p.get("needs_review"):
                bits.append("needs review")
            note = p.get("handoff_note") or p.get("rationale") or ""
            if note:
                bits.append(note[:180])
            custom.append(" · ".join(bits))

    return {
        "ids": ids,
        "parents": parents,
        "labels": labels,
        "values": values,
        "marker": {"colors": colors},
        "customdata": custom,
        "branchvalues": "total",
        "hovertemplate": "%{customdata}<extra></extra>",
        "textinfo": "label+value",
    }


def build_topic_map_html(data: dict) -> str:
    placements = data.get("placements") or []
    n = len(placements)
    n_review = sum(1 for p in placements if p.get("needs_review"))
    figures = {f: _sunburst_payload(placements, f) for f in FACETS}
    top_prog = Counter((p.get("program") or ["unmapped"])[0] for p in placements)
    top_bits = ", ".join(f"{k} ({v})" for k, v in top_prog.most_common(6))
    figures_json = json.dumps(figures)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Burling topic map — CTE handoff</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root {{
      --bg: #0b1220;
      --panel: #141c2b;
      --ink: #e8eef7;
      --muted: #9aa8bc;
      --accent: #76b7b2;
      --line: #243044;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      background: radial-gradient(1100px 520px at 8% -12%, #1a2740, var(--bg));
      color: var(--ink);
      line-height: 1.45;
    }}
    header, footer {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 24px 28px 8px;
    }}
    footer {{ padding-bottom: 36px; color: var(--muted); font-size: 0.85rem; }}
    header h1 {{
      margin: 0 0 8px;
      font-size: 1.65rem;
      letter-spacing: -0.02em;
    }}
    header p {{ margin: 0; color: var(--muted); max-width: 72ch; }}
    .meta {{ margin-top: 12px; font-size: 0.92rem; color: var(--accent); }}
    .panel {{
      max-width: 1100px;
      margin: 12px auto 24px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 12px 14px 18px;
      overflow: hidden;
    }}
    .controls {{
      display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
      margin-bottom: 8px;
    }}
    .controls label {{ color: var(--muted); font-size: 0.9rem; }}
    select {{
      background: var(--bg);
      color: var(--ink);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 6px 10px;
      font-size: 0.95rem;
    }}
    #sunburst {{ width: 100%; height: 720px; }}
  </style>
</head>
<body>
  <header>
    <h1>Burling topic map</h1>
    <p>
      Taxonomy-first placement for a CTE handoff dump. Switch facets to re-slice
      the same documents. Size is document count — not importance.
    </p>
    <div class="meta">{n} documents · {n_review} needs review · top programs: {top_bits}</div>
  </header>
  <div class="panel">
    <div class="controls">
      <label for="facet">Facet</label>
      <select id="facet">
        <option value="program">program</option>
        <option value="function">function</option>
        <option value="audience">audience</option>
        <option value="record_type">record_type</option>
        <option value="lifecycle">lifecycle</option>
      </select>
    </div>
    <div id="sunburst"></div>
  </div>
  <footer>
    Vocabulary: <code>burling/map.yml</code> ·
    data: <code>placements.json</code> ·
    markdown: <code>TOPIC-MAP.md</code>
  </footer>
  <script>
    const FIGURES = {figures_json};
    const layout = {{
      margin: {{ l: 10, r: 10, t: 10, b: 10 }},
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: {{ color: '#e8eef7', size: 13 }},
    }};
    function draw(facet) {{
      const trace = Object.assign({{ type: 'sunburst' }}, FIGURES[facet]);
      Plotly.react('sunburst', [trace], layout, {{
        displayModeBar: false,
        responsive: true,
      }});
    }}
    document.getElementById('facet').addEventListener('change', (e) => draw(e.target.value));
    draw('program');
  </script>
</body>
</html>
"""


def write_topic_map_html(path: Path, data: dict) -> None:
    atomic_write(path, build_topic_map_html(data))
