"""Pass B — stitch rich free-form tags into nested regions.

See docs/tag-then-stitch.md. Input is Pass A ``tags.json``; output is an
approved-style region tree plus per-document region membership (multi-home OK).
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from burling.browse_graph import graph_to_payload, induce_browse_graph
from burling.io_util import atomic_write, atomic_write_json
from burling.map_html import browse_sunburst_payload, write_topic_map_html
from burling.ollama_client import chat
from burling.paths import output_dir
from burling.tag_concepts import (
    Cluster,
    cluster_concepts,
    expand_aliases,
    normalize_concepts,
)
from burling.trace import utc_now

# Original Pass B (before A+B): one JSON tree from a capped tag-frequency list.
# Kept so we can bake-off "are we overcomplicating it" on a gold set.
STITCH_SYSTEM_COMPACT = """You are a taxonomist. You receive a TAG FREQUENCY
list from an arbitrary document collection. Stitch the frequent tags into a
NESTED region tree that follows how the material itself groups —
topic → subtopic → granular.

Do not invent a workplace, district, job-change, or onboarding story unless
those ideas are already in the tag list.

Output ONLY a single JSON object:
{
  "regions": [
    {
      "id": "kebab-case-id",
      "label": "Human label",
      "description": "one sentence",
      "tags": ["tag-strings that belong directly on this node"],
      "children": []
    }
  ],
  "synonyms": {"preferred-tag": ["alias1", "alias2"]},
  "notes": "optional short note"
}

Rules:
- Build 5–12 top-level regions that emerge from the tags (heads that are
  actually in the list — not a canned scheme).
- Split a parent only when the pile is fat enough. Thin leftovers stay
  on the parent.
- A tag may appear under only ONE node.
- Do not invent personal names or programs absent from the list.
- Keep the JSON compact and valid: no comments, no trailing commas.
- Do not emit more than ~80 tag strings total. The harness maps leftovers.
"""

# File-plan stitch: same JSON shape as compact, clerk role, ban channel/year.
# The harness also strips banned heads in code — do not rely on the prompt alone.
STITCH_SYSTEM_CLERK = """You are a records clerk proposing a FILE PLAN, not a
taxonomist inventing a story. You receive a TAG FREQUENCY list from an
arbitrary document collection. Propose 5–12 functional main types a
stranger would browse (what the paper is about), then subtypes only when
a pile is fat and mixed.

Output ONLY a single JSON object:
{
  "regions": [
    {
      "id": "kebab-case-id",
      "label": "Human label",
      "description": "one sentence classifying rule",
      "tags": ["tag-strings that belong directly on this node"],
      "children": []
    }
  ],
  "synonyms": {"preferred-tag": ["alias1", "alias2"]},
  "notes": "optional short note"
}

Rules:
- Heads are WHAT the document is about (hockey, cryptography, hardware).
- NEVER use channel, medium, or year as a head or child. No Usenet,
  Email, 1993, 1990s, newsgroup, or archive-as-type folders.
- Split a parent only when the pile is fat and mixed. Thin leftovers
  stay on the parent.
- A tag may appear under only ONE node.
- Do not invent a Needs-review dump for half the corpus. Omit leftovers;
  the harness has Unmapped.
- Do not invent personal names or programs absent from the list.
- Keep the JSON compact and valid: no comments, no trailing commas.
- Do not emit more than ~80 tag strings total. The harness maps leftovers.
"""

STITCH_SYSTEM = """You are a taxonomist. You receive CONCEPT CLUSTERS already
synonym-normalized from an arbitrary document collection. Stitch them into a
NESTED region tree that follows how the material itself groups —
topic → subtopic → granular.

Do not invent a workplace, district, job-change, or onboarding story unless
those ideas are already in the cluster list.

Output ONLY a single JSON object:
{
  "regions": [
    {
      "id": "kebab-case-id",
      "label": "Human label",
      "description": "one sentence",
      "tags": ["tag-strings that belong directly on this node"],
      "children": [
        {
          "id": "kebab-child",
          "label": "…",
          "description": "…",
          "tags": ["more-specific-tags"],
          "children": []
        }
      ]
    }
  ],
  "synonyms": {"preferred-tag": ["alias1", "alias2"]},
  "notes": "optional short note"
}

Rules:
- Build 5–12 top-level regions that emerge from the clusters (the heads
  that are actually in the list — not a canned district scheme).
- Split a parent into children only when the pile is fat enough for a real
  subtopic (roughly several distinct tags / many docs). Thin leftovers stay
  on the parent. More than one child per parent is normal.
- Under a fat parent, go topic → subtopic → granular
  (compliance → trailer-compliance → acknowledgments).
- List 3–12 representative tags per node — not every input tag.
- A tag may appear under only ONE node. Multi-homing happens at document level.
- Use ISO-style broader/narrower thinking: child scope ⊆ parent scope.
- Each input line is already one concept (preferred label + aliases). Do not split aliases into new nodes.
- Do not invent personal names. Do not invent programs absent from the cluster list.
- Prefer concrete working structure over vague buckets like "misc".
- Keep the JSON compact and valid: no comments, no trailing commas, no extra text.
- Do not emit more than ~80 tag strings total. The harness maps leftover tags.
"""

# 3515 unique tags cannot fit in one Nemotron JSON tree (the CTE-manager crash).
# Best practice: send the frequent inventory only; place the long tail locally.
STITCH_MIN_COUNT = 2
STITCH_MAX_TAGS = 180
_GENERIC_TAG_TOKENS = frozenset(
    {
        "and",
        "cte",
        "dallas",
        "disd",
        "doc",
        "document",
        "form",
        "isd",
        "or",
        "pdf",
        "school",
        "the",
        "year",
    }
)


def load_tag_records(cfg: dict, path: Path | None = None) -> list[dict]:
    p = path or (output_dir(cfg) / "tags.json")
    data = json.loads(p.read_text(encoding="utf-8"))
    return list(data.get("documents") or [])


def _tag_inventory(records: list[dict]) -> tuple[Counter[str], dict[str, list[str]]]:
    counts: Counter[str] = Counter()
    docs_by_tag: dict[str, list[str]] = defaultdict(list)
    for r in records:
        rel = r.get("rel_path") or ""
        seen: set[str] = set()
        for t in r.get("tags") or []:
            if t in seen:
                continue
            seen.add(t)
            counts[t] += 1
            docs_by_tag[t].append(rel)
    return counts, docs_by_tag


def _inventory_prompt(counts: Counter[str], records: list[dict]) -> str:
    """Legacy frequent-tag prompt. Kept so older tests still cover the cap."""
    frequent = [(t, n) for t, n in counts.most_common() if n >= STITCH_MIN_COUNT]
    shown = frequent[:STITCH_MAX_TAGS]
    omitted = len(counts) - len(shown)
    lines = [
        f"CORPUS: {len(records)} documents, {len(counts)} unique tags.",
        f"Showing the {len(shown)} most common tags (count >= {STITCH_MIN_COUNT}). "
        f"{omitted} rarer tags are omitted — do not invent a node for each of them.",
        "",
        "TAG FREQUENCY (tag → doc_count):",
    ]
    for tag, n in shown:
        lines.append(f"- {tag}: {n}")
    lines.append("")
    lines.append("SAMPLE DOCS (path → tags):")
    for r in records[:28]:
        tags = ", ".join((r.get("tags") or [])[:18])
        lines.append(f"- {r.get('rel_path')}: {tags}")
    return "\n".join(lines)


def _cluster_prompt(clusters: list[Cluster], records: list[dict]) -> str:
    """Send concept clusters, not raw tag strings.

    Best practice (TnT-LLM / Moraes): the model organizes a *short, pre-filtered*
    list. 3515 raw tags broke JSON; cluster labels are the filtered list.
    Count==1 clusters are singularities (NN/g) and stay out of the prompt.
    """
    frequent = [c for c in clusters if c.count >= STITCH_MIN_COUNT]
    shown = frequent[:STITCH_MAX_TAGS]
    omitted = len(clusters) - len(shown)
    lines = [
        f"CORPUS: {len(records)} documents, {len(clusters)} concept clusters "
        f"(synonym-normalized, then co-occurrence clustered).",
        f"Showing the {len(shown)} clusters that cover ≥{STITCH_MIN_COUNT} docs. "
        f"{omitted} singleton/rare clusters are omitted — do not invent a node for each.",
        "",
        "CLUSTERS (preferred-label → doc_count; aliases):",
    ]
    for cluster in shown:
        aliases = ", ".join(cluster.aliases[:8])
        extra = f" (+{len(cluster.aliases) - 8})" if len(cluster.aliases) > 8 else ""
        lines.append(f"- {cluster.label}: {cluster.count}  [{aliases}{extra}]")
    lines.append("")
    lines.append("SAMPLE DOCS (path → tags):")
    for r in records[:28]:
        tags = ", ".join((r.get("tags") or [])[:18])
        lines.append(f"- {r.get('rel_path')}: {tags}")
    return "\n".join(lines)


def _tag_tokens(tag: str) -> frozenset[str]:
    """Split kebab/underscore tags into tokens worth matching on."""
    parts = re.split(r"[-_/\s]+", str(tag).lower())
    return frozenset(
        p for p in parts if len(p) > 2 and p not in _GENERIC_TAG_TOKENS and not p.isdigit()
    )


def place_leftover_tags(
    counts: Counter[str], tag_to_region: dict[str, str], regions: list[dict]
) -> int:
    """Map tags the model omitted onto existing regions (or needs-review).

    Best practice: do this locally. Asking the model to list 3515 tags is what
    killed Pass B after tags had already finished.
    """
    mapped: list[tuple[frozenset[str], str]] = []
    for tag, rid in list(tag_to_region.items()):
        toks = _tag_tokens(tag)
        if toks:
            mapped.append((toks, rid))

    leftovers = [t for t in counts if t not in tag_to_region]
    needs: list[str] = []
    placed = 0
    for tag in leftovers:
        toks = _tag_tokens(tag)
        best_rid = None
        best_score = 0.0
        if toks:
            for mtoks, rid in mapped:
                overlap = len(toks & mtoks)
                if not overlap:
                    continue
                score = overlap / min(len(toks), len(mtoks))
                if score > best_score:
                    best_score = score
                    best_rid = rid
        if best_rid and best_score >= 0.5:
            tag_to_region[tag] = best_rid
            placed += 1
        else:
            needs.append(tag)

    if needs:
        if not any(isinstance(n, dict) and n.get("id") == "needs-review" for n in regions):
            regions.append(
                {
                    "id": "needs-review",
                    "label": "Needs review",
                    "description": "Singleton or unmatched tags the compact stitch did not place.",
                    "tags": needs[:40],
                    "children": [],
                }
            )
        for tag in needs:
            tag_to_region[tag] = "needs-review"
    return placed


def _walk_regions(nodes: list[dict], parent_id: str | None = None):
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        rid = str(node.get("id") or "").strip()
        if not rid:
            continue
        yield parent_id, node
        yield from _walk_regions(node.get("children") or [], rid)


def _flatten_tag_map(regions: list[dict], synonyms: dict) -> dict[str, str]:
    """Map each tag (and synonym alias) → region id."""
    tag_to_region: dict[str, str] = {}
    for _parent, node in _walk_regions(regions):
        rid = str(node.get("id"))
        for t in node.get("tags") or []:
            name = str(t).strip()
            if name and name not in tag_to_region:
                tag_to_region[name] = rid
    # synonyms: preferred → aliases; aliases point to same region as preferred if known
    for preferred, aliases in (synonyms or {}).items():
        target = tag_to_region.get(preferred)
        for alias in aliases or []:
            a = str(alias).strip()
            if not a:
                continue
            if target and a not in tag_to_region:
                tag_to_region[a] = target
            elif preferred not in tag_to_region and a in tag_to_region:
                tag_to_region[preferred] = tag_to_region[a]
    return tag_to_region


def _region_index(regions: list[dict]) -> dict[str, dict]:
    idx: dict[str, dict] = {}
    for parent_id, node in _walk_regions(regions):
        rid = str(node["id"])
        idx[rid] = {
            "id": rid,
            "label": node.get("label") or rid,
            "description": node.get("description") or "",
            "parent_id": parent_id,
            "tags": list(node.get("tags") or []),
        }
    return idx


def assign_docs(
    records: list[dict], tag_to_region: dict[str, str], region_idx: dict[str, dict]
) -> list[dict]:
    out: list[dict] = []
    for r in records:
        region_ids: list[str] = []
        matched: list[str] = []
        for t in r.get("tags") or []:
            rid = tag_to_region.get(t)
            if rid and rid not in region_ids:
                region_ids.append(rid)
                matched.append(t)
            # also climb to parents for browse breadcrumbs
        breadcrumbs: list[list[str]] = []
        for rid in region_ids:
            chain = [rid]
            cur = rid
            while region_idx.get(cur, {}).get("parent_id"):
                cur = region_idx[cur]["parent_id"]
                chain.append(cur)
            breadcrumbs.append(list(reversed(chain)))
        top_level = []
        for chain in breadcrumbs:
            if chain and chain[0] not in top_level:
                top_level.append(chain[0])
        out.append(
            {
                "doc_id": r.get("doc_id"),
                "rel_path": r.get("rel_path"),
                "region_ids": region_ids,
                "top_level_regions": top_level,
                "matched_tags": matched,
                "unmatched_tags": [
                    t for t in (r.get("tags") or []) if t not in tag_to_region
                ],
                "summary": r.get("summary") or "",
                "tag_count": len(r.get("tags") or []),
            }
        )
    return out


def stitch_to_placements(
    assignments: list[dict], region_idx: dict[str, dict]
) -> list[dict]:
    """Project Pass B membership onto the sunburst's five facets.

    Best practice: do not re-classify. The map.yml facets are a *view* of
    the stitch tree — program = top-level region, function = child (or the
    same node if there is no child). Audience / record / lifecycle stay
    ``unmapped`` until a later facet pass; inventing them here would lie.
    """
    placements: list[dict] = []
    for a in assignments:
        tops = [rid for rid in (a.get("top_level_regions") or []) if rid in region_idx]
        rids = [rid for rid in (a.get("region_ids") or []) if rid in region_idx]
        leaves = [rid for rid in rids if region_idx[rid].get("parent_id")]
        program = [_region_term(tops[0], region_idx)] if tops else ["unmapped"]
        function = (
            [_region_term(leaves[0], region_idx)]
            if leaves
            else (program if program != ["unmapped"] else ["unmapped"])
        )
        placements.append(
            {
                "doc_id": a.get("doc_id"),
                "rel_path": a.get("rel_path"),
                "program": program,
                "function": function,
                "audience": ["unmapped"],
                "record_type": ["unmapped"],
                "lifecycle": ["unmapped"],
                "confidence": 1.0 if rids else 0.0,
                "needs_review": (not rids) or "needs-review" in rids,
                "handoff_note": (a.get("summary") or "")[:280],
                "rationale": ", ".join(a.get("matched_tags") or [])[:200],
            }
        )
    return placements


def _region_term(rid: str, region_idx: dict[str, dict]) -> str:
    """Sunburst slice id: keep kebab so Plotly labels stay short and stable."""
    return rid or "unmapped"


def write_stitch_topic_map(
    out: Path,
    payload: dict,
    region_idx: dict[str, dict],
    chrome: dict | None = None,
) -> None:
    """Write topic-map.html + TOPIC-MAP.md from an already-stitched payload.

    Best practice: maps are a projection of ``regions.json``. Regenerating
    them never calls the model and never touches tags.json. ``chrome``
    swaps the masthead for a public sample map; omit it for district maps.
    """
    placements = stitch_to_placements(payload.get("assignments") or [], region_idx)
    tags_path = out / "tags.json"
    tag_records = None
    if tags_path.is_file():
        tag_records = list(
            (json.loads(tags_path.read_text(encoding="utf-8")).get("documents") or [])
        )
    graph_nodes = induce_browse_graph(payload, tag_records=tag_records)
    graph_payload = graph_to_payload(graph_nodes)
    atomic_write_json(out / "graph.json", graph_payload)
    two_way = [
        n
        for n in graph_payload["nodes"]
        if n["kind"] != "topic" and len(n.get("broader") or []) > 1
    ]
    map_payload = {
        "map_id": "stitch-c-browse",
        "map_version": "normalize-cluster-graph",
        "count": len(placements),
        "placements": placements,
        "browse_figure": browse_sunburst_payload(
            graph_nodes, payload.get("assignments") or [], chrome=chrome
        ),
    }
    if chrome:
        map_payload["chrome"] = chrome
    write_topic_map_html(out / "topic-map.html", map_payload)
    lines = [
        "# Topic map (method C browse graph)",
        "",
        "Default **Browse** tab is topic → subtopic → file. A concept with two",
        "parents (Compliance × Trailer) appears under both. Other tabs are the",
        "older `map.yml` facets (orthogonal — not a 4th tree level).",
        "",
        f"**Documents:** {len(placements)}",
        f"**Graph nodes:** {len(graph_payload['nodes'])}",
        f"**Two-parent concepts:** {len(two_way)}",
        "",
        "Two-way nodes:",
        "",
    ]
    for n in two_way:
        lines.append(
            f"- `{n['id']}` — {n['label']}  (BT: {', '.join(n['broader'])}; {n['doc_count']} docs)"
        )
    lines.append("")
    lines.append("Open `topic-map.html`. Click Compliance, then the Trailer slice.")
    lines.append("")
    atomic_write(out / "TOPIC-MAP.md", "\n".join(lines))


def _regions_md(
    regions: list[dict],
    region_idx: dict[str, dict],
    assignments: list[dict],
    coverage: dict,
) -> str:
    by_region: dict[str, list[dict]] = defaultdict(list)
    for a in assignments:
        for rid in a.get("region_ids") or []:
            by_region[rid].append(a)

    lines = [
        "# Regions (Pass B stitch)",
        "",
        "Nested groups stitched from Pass A free-form tags. Docs may appear in multiple regions.",
        "",
        f"**Documents:** {coverage.get('documents', 0)}",
        f"**Top-level regions:** {coverage.get('top_level', 0)}",
        f"**Total nodes:** {coverage.get('nodes', 0)}",
        f"**Tag coverage:** {coverage.get('tags_mapped', 0)}/{coverage.get('tags_total', 0)} "
        f"({coverage.get('tag_coverage_pct', 0)}%)",
        f"**Docs with ≥1 region:** {coverage.get('docs_mapped', 0)}",
        "",
        "## Tree",
        "",
    ]

    def render(nodes: list[dict], depth: int = 0) -> None:
        for node in nodes or []:
            rid = node.get("id")
            label = node.get("label") or rid
            n_docs = len(by_region.get(rid, []))
            indent = "  " * depth
            lines.append(f"{indent}- **{label}** (`{rid}`) — {n_docs} docs")
            tags = node.get("tags") or []
            if tags:
                shown = ", ".join(f"`{t}`" for t in tags[:12])
                more = f" (+{len(tags)-12})" if len(tags) > 12 else ""
                lines.append(f"{indent}  - tags: {shown}{more}")
            render(node.get("children") or [], depth + 1)

    render(regions)
    lines.append("")
    lines.append("## Documents by top-level region")
    lines.append("")
    top_ids = [n["id"] for n in regions if isinstance(n, dict) and n.get("id")]
    for tid in top_ids:
        members = [a for a in assignments if tid in (a.get("top_level_regions") or [])]
        label = region_idx.get(tid, {}).get("label", tid)
        lines.append(f"### {label} ({len(members)})")
        lines.append("")
        for a in sorted(members, key=lambda x: x.get("rel_path") or ""):
            kids = [r for r in (a.get("region_ids") or []) if r != tid]
            kid_s = ", ".join(f"`{k}`" for k in kids[:6]) or "—"
            lines.append(f"- `{a.get('rel_path')}` → {kid_s}")
        lines.append("")
    return "\n".join(lines)


def _simple_region_html(payload: dict, path: Path) -> None:
    """Lightweight collapsible HTML tree (no Plotly dependency)."""
    regions = payload.get("regions") or []
    assignments = payload.get("assignments") or []
    by_region: dict[str, list[dict]] = defaultdict(list)
    for a in assignments:
        for rid in a.get("region_ids") or []:
            by_region[rid].append(a)

    def node_html(node: dict) -> str:
        rid = node.get("id")
        label = node.get("label") or rid
        desc = node.get("description") or ""
        docs = by_region.get(rid, [])
        kids = "".join(node_html(c) for c in (node.get("children") or []) if isinstance(c, dict))
        doc_lis = "".join(
            f"<li><code>{_esc(a.get('rel_path'))}</code></li>"
            for a in sorted(docs, key=lambda x: x.get("rel_path") or "")[:40]
        )
        more = (
            f"<li><em>…{len(docs)-40} more</em></li>" if len(docs) > 40 else ""
        )
        return (
            f"<details open><summary><strong>{_esc(label)}</strong> "
            f"<span class='id'>{_esc(rid)}</span> "
            f"<span class='n'>{len(docs)} docs</span></summary>"
            f"<p class='desc'>{_esc(desc)}</p>"
            f"<ul class='docs'>{doc_lis}{more}</ul>"
            f"<div class='children'>{kids}</div></details>"
        )

    body = "".join(node_html(n) for n in regions if isinstance(n, dict))
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>Burling regions (Pass B)</title>
<style>
body{{font-family:ui-sans-serif,system-ui,sans-serif;margin:2rem;max-width:960px;
background:#f6f3ee;color:#1c1917}}
h1{{font-size:1.6rem;margin-bottom:.25rem}}
.meta{{color:#57534e;margin-bottom:1.5rem}}
details{{margin:.4rem 0;padding:.35rem .6rem;background:#fff;border:1px solid #e7e5e4;
border-radius:6px}}
summary{{cursor:pointer}}
.id{{color:#a8a29e;font-size:.85rem;margin-left:.4rem}}
.n{{float:right;color:#78716c;font-size:.85rem}}
.desc{{color:#44403c;font-size:.92rem}}
.docs{{font-size:.88rem}}
.children{{margin-left:.75rem}}
</style></head><body>
<h1>Browse regions</h1>
<p class="meta">Pass B stitch from free-form tags ·
{payload.get('meta',{}).get('documents',0)} docs ·
{payload.get('meta',{}).get('nodes',0)} nodes ·
tag coverage {payload.get('meta',{}).get('tag_coverage_pct',0)}%</p>
{body}
</body></html>"""
    atomic_write(path, html)


def _esc(s: object) -> str:
    return (
        str(s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def stitch_from_records(
    cfg: dict, records: list[dict], *, method: str = "ab"
) -> dict:
    """One tree call → assign documents.

    ``method="compact"`` is the original Pass B: send the 180 most common
    raw tags. ``method="ab"`` is later work: synonym-normalize, cluster,
    then send cluster labels (the model never sees 3515 raw strings).

    Use compact vs ab on the same cached ``tags.json`` when you want to
    know whether the extra machinery helped.
    """
    if method not in {"ab", "compact", "clerk"}:
        raise ValueError(f"unknown stitch method {method!r} (use ab, compact, or clerk)")

    counts, docs_by_tag = _tag_inventory(records)
    concepts: list = []
    clusters: list = []
    if method == "ab":
        concepts = normalize_concepts(counts, docs_by_tag)
        clusters = cluster_concepts(concepts)
        user = _cluster_prompt(clusters, records)
        system = STITCH_SYSTEM
        method_name = "normalize-cluster-compact"
    elif method == "clerk":
        user = _inventory_prompt(counts, records)
        system = STITCH_SYSTEM_CLERK
        method_name = "clerk-file-plan"
    else:
        user = _inventory_prompt(counts, records)
        system = STITCH_SYSTEM_COMPACT
        method_name = "compact-frequent-tags"

    # Hierarchy JSON is large; give llama.cpp room (Nemotron is fast enough).
    stitch_cfg = dict(cfg)
    ollama = dict(cfg.get("ollama") or {})
    ollama["max_tokens"] = max(int(ollama.get("max_tokens") or 2048), 8192)
    stitch_cfg["ollama"] = ollama
    raw = chat(
        stitch_cfg,
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        step="stitch:regions",
    )
    if not isinstance(raw, dict):
        raise RuntimeError("stitch model did not return a JSON object")

    regions = raw.get("regions") or []
    synonyms = raw.get("synonyms") or {}
    if not isinstance(regions, list) or not regions:
        raise RuntimeError("stitch model returned empty regions")
    if method == "clerk":
        from burling.file_plan import demote_banned_heads, ensure_unmapped

        # Prompt is not enough — Nemotron still names Usenet 1993. Strip it.
        regions = demote_banned_heads(regions)
        if not regions:
            raise RuntimeError("clerk stitch left no topical heads after the channel/year ban")
        ensure_unmapped(regions)

    tag_to_region = _flatten_tag_map(regions, synonyms if isinstance(synonyms, dict) else {})
    # SKOS altLabel expansion only when we actually built clusters.
    if clusters:
        expand_aliases(tag_to_region, clusters)
    # Place the long tail locally so stitch coverage is not limited to the
    # cluster labels we sent the model.
    place_leftover_tags(counts, tag_to_region, regions)
    region_idx = _region_index(regions)
    assignments = assign_docs(records, tag_to_region, region_idx)

    tags_mapped = sum(1 for t in counts if t in tag_to_region)
    docs_mapped = sum(1 for a in assignments if a.get("region_ids"))
    top_level = len([n for n in regions if isinstance(n, dict) and n.get("id")])
    coverage = {
        "documents": len(records),
        "top_level": top_level,
        "nodes": len(region_idx),
        "tags_total": len(counts),
        "tags_mapped": tags_mapped,
        "tag_coverage_pct": round(100 * tags_mapped / len(counts), 1) if counts else 0,
        "docs_mapped": docs_mapped,
    }

    out = output_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": {
            **coverage,
            "built_at": utc_now(),
            "notes": raw.get("notes") or "",
            "method": method_name,
            "concepts": len(concepts),
            "clusters": len(clusters),
            "clusters_sent": min(
                STITCH_MAX_TAGS,
                sum(1 for c in clusters if c.count >= STITCH_MIN_COUNT),
            )
            if clusters
            else min(STITCH_MAX_TAGS, sum(1 for _t, n in counts.items() if n >= STITCH_MIN_COUNT)),
        },
        "regions": regions,
        "synonyms": synonyms,
        "tag_to_region": tag_to_region,
        "assignments": assignments,
        "clusters": [
            {
                "label": c.label,
                "count": c.count,
                "aliases": c.aliases,
                "member_preferred": [m.preferred for m in c.members],
            }
            for c in clusters
            if c.count >= STITCH_MIN_COUNT
        ],
    }
    atomic_write_json(out / "regions.json", payload)
    atomic_write(out / "REGIONS.md", _regions_md(regions, region_idx, assignments, coverage))
    _simple_region_html(payload, out / "regions.html")
    # Same sunburst chrome as Pass 1 classify — no second model call.
    write_stitch_topic_map(out, payload, region_idx)

    # YAML-ish export for human edit (map seed)
    yaml_lines = [
        "# Auto-stitched from Pass A tags. Edit freely; this becomes the browse-map seed.",
        f"# built_at: {utc_now()}",
        "regions:",
    ]

    def dump_yaml(nodes: list[dict], indent: int = 2) -> None:
        sp = " " * indent
        for node in nodes or []:
            if not isinstance(node, dict):
                continue
            yaml_lines.append(f"{sp}- id: {node.get('id')}")
            yaml_lines.append(f"{sp}  label: {json.dumps(node.get('label') or '', ensure_ascii=False)}")
            yaml_lines.append(
                f"{sp}  description: {json.dumps(node.get('description') or '', ensure_ascii=False)}"
            )
            tags = node.get("tags") or []
            yaml_lines.append(f"{sp}  tags:")
            for t in tags:
                yaml_lines.append(f"{sp}    - {json.dumps(t, ensure_ascii=False)}")
            kids = node.get("children") or []
            if kids:
                yaml_lines.append(f"{sp}  children:")
                dump_yaml(kids, indent + 4)
            else:
                yaml_lines.append(f"{sp}  children: []")

    dump_yaml(regions)
    atomic_write(out / "regions.yml", "\n".join(yaml_lines) + "\n")
    return coverage


def run_stitch(
    cfg: dict, *, tags_path: Path | None = None, method: str = "ab"
) -> dict:
    records = load_tag_records(cfg, tags_path)
    if not records:
        raise RuntimeError(
            "No Pass A tags found. Run: python -m burling.run --tags  (need output/tags.json)"
        )
    coverage = stitch_from_records(cfg, records, method=method)
    print(
        f"stitch: {coverage['top_level']} top-level / {coverage['nodes']} nodes, "
        f"tag coverage {coverage['tag_coverage_pct']}%, "
        f"{coverage['docs_mapped']}/{coverage['documents']} docs mapped → "
        f"{output_dir(cfg) / 'REGIONS.md'}"
    )
    return coverage
