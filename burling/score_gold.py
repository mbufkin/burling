"""Score a stitch tree against a public gold folder map.

Best practice: same metric for every bake-off method. Primary home is
the first ``region_ids`` entry. We also report any-home (too generous
when files have 3+ parents) and a keyword map from region labels onto
the gold L1 heads (computing, recreation, …).

Names need not match gold. ``Recreation`` vs ``Sports`` is a hit if the
label maps to the same L1 family.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

# Gold L1 (20 Newsgroups by-date groups) → tokens that mean that family.
# Conservative: channel/year words (usenet, email, 1993) are *not* a topic.
L1_LEXICON: dict[str, tuple[str, ...]] = {
    "computing": (
        "comput",
        "hardware",
        "software",
        "dos",
        "windows",
        "graphics",
        "network",
        "protocol",
        "printer",
        "retro",
        "x11",
        "ibm",
        "mac",
        "tech-support",
        "programming",
        "overclock",
        "driver",
        "bios",
        "os-",
    ),
    "recreation": (
        "sport",
        "hockey",
        "baseball",
        "auto",
        "motor",
        "recreation",
        "motorcycle",
    ),
    "science": (
        "science",
        "crypto",
        "space",
        "medic",
        "electron",
        "clipper",
        "encrypt",
        "astrophys",
    ),
    "debate": (
        "politic",
        "debate",
        "gun",
        "mideast",
        "waco",
        "military",
        "flame",
    ),
    "belief": ("atheis",),
    "society": ("christian", "theolog", "pauline", "doctrine", "apologetic"),
    "marketplace": (
        "sale",
        "commercial",
        "listing",
        "marketplace",
        "forsale",
        "classified",
    ),
}


def _walk_labels(nodes: list) -> dict[str, str]:
    labels: dict[str, str] = {}

    def walk(items: list) -> None:
        for node in items or []:
            if not isinstance(node, dict):
                continue
            rid = str(node.get("id") or "")
            if rid:
                labels[rid] = str(node.get("label") or rid)
            walk(node.get("children") or [])

    walk(nodes)
    return labels


def _hits(text: str) -> set[str]:
    s = (text or "").lower()
    found: set[str] = set()
    for topic, kws in L1_LEXICON.items():
        if any(k in s for k in kws):
            found.add(topic)
    if any(k in s for k in ("religio", "faith", "church")):
        found.add("religion")
    return found


def _gold_l1(gold: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for fn, meta in gold.items():
        paths = meta.get("paths") or []
        part = str(paths[0]).split("/")[0] if paths else "?"
        out[Path(str(fn)).name] = part
    return out


def score_regions(regions_path: Path, gold_path: Path) -> dict:
    """Return counts a bake-off table can print."""
    payload = json.loads(regions_path.read_text(encoding="utf-8"))
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    labels = _walk_labels(payload.get("regions") or [])
    gold_l1 = _gold_l1(gold)

    file_ids: dict[str, list[str]] = {}
    for row in payload.get("assignments") or []:
        fn = Path(str(row.get("rel_path") or "")).name
        file_ids[fn] = [str(r) for r in (row.get("region_ids") or [])]

    homes = [len(file_ids.get(fn) or []) for fn in gold_l1]
    ghost = sum(
        1
        for fn in gold_l1
        for rid in file_ids.get(fn) or []
        if rid not in labels
    )
    # unique files with any ghost
    ghost_files = sum(
        1
        for fn in gold_l1
        if any(rid not in labels for rid in file_ids.get(fn) or [])
    )

    def pred_of(ids: list[str]) -> str:
        if not ids:
            return "unmapped"
        blob = " ".join(ids[:1] + [labels.get(ids[0], "")])
        hits = _hits(blob)
        for topic in (
            "computing",
            "recreation",
            "science",
            "debate",
            "belief",
            "society",
            "marketplace",
        ):
            if topic in hits:
                return topic
        if "religion" in hits:
            return "religion"
        return "other"

    primary_ok = 0
    primary_rel = 0
    any_ok = 0
    unmapped = 0
    conf: Counter[tuple[str, str]] = Counter()
    by_gold: dict[str, Counter[str]] = defaultdict(Counter)

    for fn, gl1 in gold_l1.items():
        ids = file_ids.get(fn) or []
        if not ids:
            unmapped += 1
            conf[(gl1, "unmapped")] += 1
            by_gold[gl1]["unmapped"] += 1
            continue
        pred = pred_of(ids)
        all_hits: set[str] = set()
        for rid in ids:
            all_hits |= _hits(f"{rid} {labels.get(rid, '')}")
        if pred == gl1:
            primary_ok += 1
        if gl1 in {"belief", "society"} and pred in {
            "belief",
            "society",
            "religion",
        }:
            primary_rel += 1
        elif pred == gl1:
            primary_rel += 1
        if gl1 in all_hits or (
            gl1 in {"belief", "society"} and "religion" in all_hits
        ):
            any_ok += 1
        conf[(gl1, pred)] += 1
        by_gold[gl1][labels.get(ids[0], ids[0])] += 1

    n = len(gold_l1) or 1
    # Product score: did same-topic files sit together? Names may differ.
    # Weighted by group size so a 90-file computing pile dominates a 10-file one.
    purity_hits = 0
    for gl1, ctr in by_gold.items():
        if ctr:
            purity_hits += ctr.most_common(1)[0][1]
    gold_together = sum(sum(ctr.values()) for ctr in by_gold.values())
    mean_purity = round(100 * purity_hits / gold_together, 1) if gold_together else 0.0

    meta = payload.get("meta") or {}
    return {
        "method": meta.get("method") or regions_path.parent.name,
        "documents": n,
        "nodes": meta.get("nodes") or len(labels),
        "top_level": meta.get("top_level"),
        "docs_mapped": meta.get("docs_mapped"),
        "unmapped": unmapped,
        "ghost_files": ghost_files,
        "ghost_homes": ghost,
        "homes_mean": round(sum(homes) / len(homes), 2) if homes else 0,
        "homes_max": max(homes) if homes else 0,
        "primary_l1": primary_ok,
        "primary_l1_pct": round(100 * primary_ok / n, 1),
        "primary_l1_rel": primary_rel,
        "primary_l1_rel_pct": round(100 * primary_rel / n, 1),
        "any_home_l1": any_ok,
        "any_home_l1_pct": round(100 * any_ok / n, 1),
        "confusion": [(g, p, c) for (g, p), c in conf.most_common(12)],
        "majority_primary": {
            g: ctr.most_common(2) for g, ctr in sorted(by_gold.items())
        },
        "purity_hits": purity_hits,
        "mean_purity_pct": mean_purity,
    }


def format_table(rows: list[dict]) -> str:
    """Markdown table for BAKEOFF.md — one row per method."""
    lines = [
        "| Method | Nodes | Homes/file | Purity | Primary L1 | + religion≈belief/society | Any-home L1 | Unmapped | Ghost files |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['method']} | {r['nodes']} | {r['homes_mean']} "
            f"(max {r['homes_max']}) | {r.get('mean_purity_pct', 0)}% | "
            f"{r['primary_l1_pct']}% "
            f"({r['primary_l1']}/{r['documents']}) | "
            f"{r['primary_l1_rel_pct']}% | {r['any_home_l1_pct']}% | "
            f"{r['unmapped']} | {r['ghost_files']} |"
        )
    return "\n".join(lines)
