"""Method C: induce a polyhierarchical browse graph from a finished stitch.

Best practice (ISO 25964-1 / SKOS + NN/g):

- A concept may have **two** broader terms (Compliance *and* Trailer).
  It is one node, not two folders that can drift.
- Only mint a child when enough documents share the cut (NN/g
  singularities; TaxoGen / TnT recurse fat branches only).
- Do **not** attach a child to every overlapping topic. Token overlap
  is the restraint: ``trailer-compliance`` may sit under Trailer and
  Compliance; it does not also sit under PD just because some PD decks
  mention a trailer.

No model call. Input is the A+B ``regions.json`` payload (and the
cached tags already on each assignment). Depth stays 2–3.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from burling.tag_concepts import content_tokens

# Research note: start at 8; drop to 5 when the tree is too flat.
# Trailer ∩ Compliance is 6 docs on this dump — 8 would hide the
# example the handoff actually needs.
MIN_SPLIT = 5
MAX_BROADER = 2
# Needs-review is a bin, not a mental-model parent (NN/g: not Toys).
_SKIP_TOPS = frozenset({"needs-review"})

# Families that are real successor entry points but may have been
# flattened into Purchasing / Events by the compact stitch.
_PROMOTE = {
    # Distinctive tokens only — ``lab`` alone would glue Lab Results
    # onto Mobile Lab (NN/g: do not invent a second parent from a
    # three-letter collision).
    "mobile-lab": frozenset({"trailer", "mobile", "mobilelab"}),
}
# A shared token shorter than this is not a mental-model match.
_MIN_TOKEN_LEN = 5


@dataclass
class GraphNode:
    """One SKOS-style concept in the browse graph."""

    id: str
    label: str
    kind: str  # topic | subtopic | granular
    broader: list[str] = field(default_factory=list)
    docs: frozenset[str] = field(default_factory=frozenset)
    tags: list[str] = field(default_factory=list)
    description: str = ""


def _tokens(*parts: str) -> frozenset[str]:
    out: set[str] = set()
    for part in parts:
        if part:
            out.update(content_tokens(part))
    return frozenset(out)


def _docs_by_region(assignments: list[dict]) -> dict[str, set[str]]:
    by: dict[str, set[str]] = defaultdict(set)
    for a in assignments:
        rel = a.get("rel_path") or a.get("doc_id") or ""
        if not rel:
            continue
        for rid in a.get("region_ids") or []:
            by[str(rid)].add(rel)
        for rid in a.get("top_level_regions") or []:
            by[str(rid)].add(rel)
    return by


def _walk(nodes: list[dict], parent: str | None = None):
    for node in nodes or []:
        if not isinstance(node, dict) or not node.get("id"):
            continue
        yield parent, node
        yield from _walk(node.get("children") or [], str(node["id"]))


def induce_browse_graph(
    payload: dict,
    *,
    min_split: int = MIN_SPLIT,
    tag_records: list[dict] | None = None,
) -> list[GraphNode]:
    """Build topic → subtopic nodes with at most two broader terms.

    Best practice: reuse the A+B tree as the *canonical* parent, then
    add a second BT only when (shared docs ≥ min_split) **and** the
    child shares a content token with that topic. Promote a missing
    topic (mobile-lab) when its tag-family covers enough files.
    """
    regions = payload.get("regions") or []
    assignments = payload.get("assignments") or []
    by_region = _docs_by_region(assignments)
    tag_docs = (
        _tag_docs_from_records(tag_records)
        if tag_records
        else _tag_docs_from_assignments(assignments)
    )

    nodes: dict[str, GraphNode] = {}
    tops: list[str] = []
    for _parent, raw in _walk(regions):
        rid = str(raw["id"])
        if _parent is None:
            tops.append(rid)
        nodes[rid] = GraphNode(
            id=rid,
            label=str(raw.get("label") or rid),
            kind="topic" if _parent is None else "subtopic",
            broader=[] if _parent is None else [str(_parent)],
            docs=frozenset(by_region.get(rid) or []),
            tags=[str(t) for t in (raw.get("tags") or [])],
            description=str(raw.get("description") or ""),
        )

    # Promote a real entry point the compact stitch buried (Trailer).
    for fam_id, fam_toks in _PROMOTE.items():
        if fam_id in nodes:
            continue
        docs = _docs_for_tokens(tag_docs, fam_toks)
        if len(docs) < min_split:
            continue
        if any(_tokens(t, nodes[t].label) & fam_toks for t in tops if t not in _SKIP_TOPS):
            continue
        nodes[fam_id] = GraphNode(
            id=fam_id,
            label="Mobile Lab / Trailer",
            kind="topic",
            broader=[],
            docs=frozenset(docs),
            tags=sorted(t for t in tag_docs if content_tokens(t) & fam_toks),
            description="Promoted topic: successor mental model that the compact stitch flattened.",
        )
        tops.append(fam_id)
        by_region[fam_id] = set(docs)

    browse_tops = [t for t in tops if t not in _SKIP_TOPS]
    # Id + label only. Member tags would leak ``trailer-compliance``
    # onto the Mobile Lab topic and then match every compliance child.
    top_tokens = {t: _tokens(t, nodes[t].label) for t in browse_tops}
    if "mobile-lab" in top_tokens:
        top_tokens["mobile-lab"] = frozenset(top_tokens["mobile-lab"] | _PROMOTE["mobile-lab"])

    # Second BT on existing children (restrained polyhierarchy).
    for node in list(nodes.values()):
        if node.kind == "topic" or node.id in _SKIP_TOPS:
            continue
        child_toks = _tokens(node.id, node.label, *node.tags)
        scored: list[tuple[int, str]] = []
        for tid in browse_tops:
            if tid in node.broader:
                continue
            shared = len(node.docs & (by_region.get(tid) or set()))
            if shared < min_split:
                continue
            if not _distinctive_overlap(child_toks, top_tokens[tid]):
                continue
            scored.append((shared, tid))
        scored.sort(reverse=True)
        for _n, tid in scored:
            if len(node.broader) >= MAX_BROADER:
                break
            node.broader.append(tid)

    # Compound NT from tag families that hit two topics (trailer ∧ compliance).
    _add_compound_nodes(nodes, browse_tops, top_tokens, tag_docs, by_region, min_split)

    # Drop empty / skipped topics from the browse list; keep needs-review
    # as a topic so unmapped files still have a home.
    return sorted(nodes.values(), key=lambda n: (0 if n.kind == "topic" else 1, -len(n.docs), n.id))


def _tag_docs_from_records(records: list[dict]) -> dict[str, set[str]]:
    """Pass A tags.json — preferred. Every raw tag, not just stitch matches."""
    out: dict[str, set[str]] = defaultdict(set)
    for r in records:
        rel = r.get("rel_path") or ""
        for t in r.get("tags") or []:
            out[str(t)].add(rel)
    return out


def _tag_docs_from_assignments(assignments: list[dict]) -> dict[str, set[str]]:
    """Prefer matched_tags on the stitch payload; fall back to empty."""
    out: dict[str, set[str]] = defaultdict(set)
    for a in assignments:
        rel = a.get("rel_path") or ""
        for t in a.get("matched_tags") or []:
            out[str(t)].add(rel)
        for t in a.get("unmatched_tags") or []:
            out[str(t)].add(rel)
    return out


def _distinctive_overlap(a: frozenset[str], b: frozenset[str]) -> bool:
    """True when two token sets share a word long enough to be a concept."""
    return any(len(tok) >= _MIN_TOKEN_LEN for tok in (a & b))


def _docs_for_tokens(tag_docs: dict[str, set[str]], family: frozenset[str]) -> set[str]:
    docs: set[str] = set()
    for tag, members in tag_docs.items():
        if _distinctive_overlap(content_tokens(tag), family):
            docs.update(members)
        elif any(fam in kebab_or_raw(tag) for fam in family):
            docs.update(members)
    return docs


def kebab_or_raw(tag: str) -> str:
    return str(tag).lower().replace("_", "-")


def _add_compound_nodes(
    nodes: dict[str, GraphNode],
    browse_tops: list[str],
    top_tokens: dict[str, frozenset[str]],
    tag_docs: dict[str, set[str]],
    by_region: dict[str, set[str]],
    min_split: int,
) -> None:
    """Mint one NT when a tag (or tag-family pair) sits inside two topics.

    Best practice: one id, two BTs. Skip if a node with those BTs already
    exists, or if the intersection is a singularity.
    """
    # Pair of topics → docs that carry tokens from both.
    for i, a in enumerate(browse_tops):
        for b in browse_tops[i + 1 :]:
            both_docs: set[str] = set()
            hit_tags: list[str] = []
            for tag, members in tag_docs.items():
                toks = content_tokens(tag)
                if _distinctive_overlap(toks, top_tokens[a]) and _distinctive_overlap(
                    toks, top_tokens[b]
                ):
                    both_docs.update(members)
                    hit_tags.append(tag)
            # Also count docs already in both topic memberships *and*
            # tagged with a token from each side (stricter than raw ∩).
            if len(both_docs) < min_split:
                continue
            cid = f"{a}--{b}" if a < b else f"{b}--{a}"
            # Prefer a human id when a hit tag already names the pair.
            for tag in sorted(hit_tags, key=lambda t: (-len(tag_docs[t]), t)):
                toks = content_tokens(tag)
                if toks & top_tokens[a] and toks & top_tokens[b]:
                    cid = tag.replace("_", "-")
                    break
            if cid in nodes:
                node = nodes[cid]
                for tid in (a, b):
                    if tid not in node.broader and len(node.broader) < MAX_BROADER:
                        node.broader.append(tid)
                node.docs = frozenset(node.docs | both_docs)
                continue
            nodes[cid] = GraphNode(
                id=cid,
                label=_compound_label(cid, nodes[a].label, nodes[b].label),
                kind="subtopic",
                broader=[a, b],
                docs=frozenset(both_docs),
                tags=sorted(set(hit_tags)),
                description=f"Polyhierarchy: NT of {nodes[a].label} and {nodes[b].label}.",
            )


def _compound_label(cid: str, a_label: str, b_label: str) -> str:
    pretty = cid.replace("-", " ").strip()
    if pretty and pretty not in {a_label.lower(), b_label.lower()}:
        return pretty.title()
    return f"{a_label} × {b_label}"


def graph_to_payload(nodes: list[GraphNode]) -> dict:
    """JSON-safe graph for graph.json / regions.json['graph']."""
    return {
        "min_split": MIN_SPLIT,
        "max_broader": MAX_BROADER,
        "nodes": [
            {
                "id": n.id,
                "label": n.label,
                "kind": n.kind,
                "broader": n.broader,
                "doc_count": len(n.docs),
                "docs": sorted(n.docs),
                "tags": n.tags,
                "description": n.description,
            }
            for n in nodes
        ],
    }
